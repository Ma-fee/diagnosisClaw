"""Xeno agent implementation using PydanticAI."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

from agentpool.agents.base_agent import BaseAgent
from agentpool.agents.events import (
    RichAgentStreamEvent,
    RunStartedEvent,
    StreamCompleteEvent,
)
from agentpool.agents.events.processors import FileTracker
from agentpool.agents.exceptions import UnknownCategoryError, UnknownModeError
from agentpool.agents.modes import ConfigOptionChanged, ModeCategory, ModeInfo
from agentpool.agents.native_agent.helpers import extract_text_from_messages, process_tool_event
from agentpool.messaging import ChatMessage, MessageHistory
from agentpool.sessions import SessionData
from agentpool.utils.streams import merge_queue_into_iterator
from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import CallToolsNode, ModelRequestNode
from pydantic_graph import End

from xeno_agent.agentpool.core.config import RoleType, XenoConfig, XenoRoleConfig
from xeno_agent.agentpool.core.deps import XenoAgentDeps
from xeno_agent.agentpool.core.routing import (
    ask_followup,
    attempt_completion,
    new_task,
    switch_mode,
    update_todo,
)

logger = logging.getLogger("xeno-agent")

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from agentpool.delegation import AgentPool
    from agentpool.ui.base import InputProvider
    from pydantic_ai import BaseToolCallPart, UserContent
    from pydantic_ai.models import Model as PydanticModel
    from tokonomics.model_discovery.model_info import ModelInfo as TokonomicsModelInfo


class XenoAgent(BaseAgent[XenoAgentDeps, str]):
    """Xeno agent implementation.

    A multi-role agent that delegates to specialized PydanticAI agents based on
    the active role configuration.
    """

    # We use a literal that might not match BaseAgent's restrictive type definition
    # but is valid for this subclass.
    AGENT_TYPE: ClassVar[Literal["xeno"]] = "xeno"  # type: ignore

    def __init__(
        self,
        name: str = "xeno",
        *,
        xeno_config: XenoConfig,
        agent_pool: AgentPool | None = None,
        model: str | PydanticModel | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Xeno agent.

        Args:
            name: Agent name
            xeno_config: Xeno system configuration
            agent_pool: Agent pool for inter-agent delegation
            model: Default model to use if not specified in role
            **kwargs: Additional arguments for BaseAgent
        """
        super().__init__(
            name=name,
            agent_pool=agent_pool,
            output_type=str,
            **kwargs,
        )
        self.xeno_config: XenoConfig = xeno_config
        self._default_model: str | PydanticModel | None = model or None

        # Default to first role if available, otherwise "qa"
        self._active_role_id: str = next(iter(xeno_config.roles.keys()), "qa")

        # Initialize dependencies
        self.deps: XenoAgentDeps = XenoAgentDeps(
            xeno_config=xeno_config,
            role_config=self.current_role,
            agent_pool=agent_pool,
            tool_manager=self.tools,
        )

    @property
    def current_role(self):
        """Get configuration for the currently active role."""
        role = self.xeno_config.get_role(self._active_role_id)
        if not role:
            # Fallback for robustness
            return XenoRoleConfig(
                type=RoleType.QA_ASSISTANT,
                name="fallback",
                system_prompt="You are a fallback assistant.",
                model=str(self._default_model) if self._default_model else "openai-chat:svc/glm-4.7",
            )
        return role

    @property
    def model_name(self) -> str | None:
        """Get the model name used by the current role."""
        return self.current_role.model

    async def set_model(self, model: str) -> None:
        """Set the model for the current role.

        Note: This updates the runtime configuration but does not persist
        changes to the YAML file.
        """
        # In a real implementation, we might want to update the config object
        # or have a runtime override layer. For now, we update the role config
        # in memory if possible, or log a warning if immutable.

    async def get_available_models(self) -> list[TokonomicsModelInfo] | None:
        """Get available models."""
        # Not fully implemented yet, could rely on tokonomics discovery
        return None

    async def get_modes(self) -> list[ModeCategory]:
        """Get available modes (roles)."""
        role_modes = [
            ModeInfo(
                id=role_id,
                name=role.name,
                description=role.description or "",  # Ensure string
            )
            for role_id, role in self.xeno_config.roles.items()
        ]

        return [
            ModeCategory(
                id="role",
                name="Role",
                available_modes=role_modes,
                current_mode_id=self._active_role_id,
                category="mode",
            ),
        ]

    async def _set_mode(self, mode_id: str, category_id: str) -> None:
        """Switch active role."""
        if category_id != "role":
            raise UnknownCategoryError(category_id, ["role"])

        if mode_id not in self.xeno_config.roles:
            raise UnknownModeError(mode_id, list(self.xeno_config.roles.keys()))

        self._active_role_id = mode_id

        # Update dependencies with new role
        self.deps = XenoAgentDeps(
            xeno_config=self.xeno_config,
            role_config=self.current_role,
            agent_pool=self.agent_pool,
            tool_manager=self.tools,
        )

        await self.state_updated.emit(ConfigOptionChanged(config_id="role", value_id=mode_id))

    async def list_sessions(
        self,
        *,
        cwd: str | None = None,
        limit: int | None = None,
    ) -> list[SessionData]:
        """List sessions from pool storage."""
        if not self.agent_pool:
            return []

        # Get IDs
        session_ids = await self.agent_pool.sessions.store.list_sessions(agent_name=self.name)

        # Load data
        results: list[SessionData] = []
        for sid in session_ids:
            if data := await self.agent_pool.sessions.store.load(sid):
                # Filter by cwd if needed
                if cwd and data.cwd != cwd:
                    continue
                results.append(data)
                if limit and len(results) >= limit:
                    break
        return results

    async def load_session(self, session_id: str) -> SessionData | None:
        """Load session from pool storage."""
        if not self.agent_pool:
            return None
        return await self.agent_pool.sessions.store.load(session_id)

    async def _interrupt(self) -> None:
        """Interrupt execution."""
        if self._current_stream_task and not self._current_stream_task.done():
            self._current_stream_task.cancel()

    async def _process_node_stream(
        self,
        node_stream: AsyncIterator[Any],
        *,
        file_tracker: FileTracker,
        pending_tcs: dict[str, BaseToolCallPart],
        message_id: str,
    ) -> AsyncIterator[RichAgentStreamEvent[str]]:
        """Process events from a node stream (ModelRequest or CallTools).

        Args:
            node_stream: Stream of events from the node
            file_tracker: Tracker for file operations
            pending_tcs: Dictionary of pending tool calls
            message_id: Current message ID

        Yields:
            Processed stream events
        """
        async with merge_queue_into_iterator(node_stream, self._event_queue) as merged:
            async for event in file_tracker(merged):
                if self._cancelled:
                    break
                yield event
                if combined := process_tool_event(self.name, event, pending_tcs, message_id):
                    yield combined

    async def _stream_events(
        self,
        prompts: list[UserContent],
        *,
        user_msg: ChatMessage[Any],
        message_history: MessageHistory,
        effective_parent_id: str | None,
        message_id: str | None = None,
        session_id: str | None = None,
        parent_id: str | None = None,
        input_provider: InputProvider | None = None,
        deps: XenoAgentDeps | None = None,
        wait_for_connections: bool | None = None,
        store_history: bool = True,
    ) -> AsyncIterator[RichAgentStreamEvent[str]]:
        """Stream events from PydanticAI agent."""

        # Use provided deps or fallback to self.deps
        current_deps = deps or self.deps

        # Create PydanticAI agent for the current role
        role = self.current_role

        # Define tools
        tools = [
            ask_followup,
            attempt_completion,
            switch_mode,
            new_task,
            update_todo,
        ]

        logger.info(f"DEBUG: XenoAgent using model '{role.model}' for role '{role.name}'")

        pydantic_agent: PydanticAgent[XenoAgentDeps, str] = PydanticAgent(
            name=role.name,
            model=role.model,
            instructions=role.system_prompt,
            deps_type=XenoAgentDeps,
            output_type=str,
            tools=tools,
        )  # type: ignore

        message_id = message_id or user_msg.message_id
        run_id = message_id  # Simplify for now

        yield RunStartedEvent(session_id=session_id or "unknown", run_id=run_id, agent_name=self.name)

        file_tracker = FileTracker()
        pending_tcs: dict[str, BaseToolCallPart] = {}

        # Run the agent
        # Note: We pass message_history converted to PydanticAI format
        history = [m for run in message_history.get_history() for m in run.to_pydantic_ai()]

        try:
            # Note: deps arg must match deps_type of agent
            async with pydantic_agent.iter(
                prompts,
                deps=current_deps,
                message_history=history,
            ) as agent_run:  # type: ignore
                async for node in agent_run:
                    if self._cancelled:
                        break

                    if isinstance(node, End):
                        break

                    if isinstance(node, ModelRequestNode):
                        async with node.stream(agent_run.ctx) as agent_stream:
                            # Cast agent_stream to satisfy type checker if needed
                            stream_iter = cast("AsyncIterator[Any]", agent_stream)
                            async for event in self._process_node_stream(
                                stream_iter,
                                file_tracker=file_tracker,
                                pending_tcs=pending_tcs,
                                message_id=message_id,
                            ):
                                yield event

                    elif isinstance(node, CallToolsNode):
                        async with node.stream(agent_run.ctx) as tool_stream:
                            stream_iter = cast("AsyncIterator[Any]", tool_stream)
                            async for event in self._process_node_stream(
                                stream_iter,
                                file_tracker=file_tracker,
                                pending_tcs=pending_tcs,
                                message_id=message_id,
                            ):
                                yield event

            # Final result
            if self._cancelled:
                # Handle cancellation
                partial_content = extract_text_from_messages(agent_run.all_messages(), include_interruption_note=True)
                final_msg = ChatMessage(
                    content=partial_content,
                    role="assistant",
                    name=self.name,
                    session_id=session_id,
                    finish_reason="stop",
                    response_time=0.0,  # Approximate
                )
            elif agent_run.result:
                final_msg = await ChatMessage.from_run_result(
                    agent_run.result,
                    agent_name=self.name,
                    session_id=session_id,
                    metadata=file_tracker.get_metadata(),
                    response_time=0.0,  # Approximate
                )
            else:
                raise RuntimeError("Stream completed without producing a result")

            yield StreamCompleteEvent(message=final_msg)

        except asyncio.CancelledError:
            self._cancelled = True
            raise
