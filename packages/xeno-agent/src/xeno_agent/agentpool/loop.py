"""
AgentPool Loop Implementation

This module defines the InteractionManager (AgentPoolLoop) class that orchestrates
agent execution and emits stream events.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from pydantic_ai.messages import ModelMessage, TextPart, ThinkingPart

from xeno_agent.pydantic_ai.events import (
    AgentSwitchEvent,
    ContentEvent,
    ThoughtEvent,
    ToolResultEvent,
    ToolStartEvent,
)
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from xeno_agent.agentpool.node import XenoAgentNode, XenoMessageNode
    from xeno_agent.pydantic_ai.factory import AgentFactory


class InteractionManager:
    """Manages agent interactions and emits stream events.

    This class orchestrates agent execution via XenoAgentNode and converts
    the results into a stream of AgentStreamEvent objects.

    The current implementation emits events post-execution (after the agent
    completes). Future versions may support true streaming during execution.

    Attributes:
        factory: The AgentFactory used to create agent instances.
        flow_config: The flow configuration for the agent.
        tool_manager: The tool manager for the agent.
        model: Optional model override (uses factory default if None).
    """

    def __init__(
        self,
        factory: AgentFactory,
        flow_config: FlowConfig,
        tool_manager: FlowToolManager,
        model: str | None = None,
    ):
        """Initialize InteractionManager.

        Args:
            factory: The AgentFactory used to create agent instances.
            flow_config: The flow configuration for the agent.
            tool_manager: The tool manager for the agent.
            model: Optional model override (uses factory default if None).
        """
        self.factory = factory
        self.flow_config = flow_config
        self.tool_manager = tool_manager
        self.model = model

    def _create_node(self, agent_id: str) -> XenoAgentNode:
        """Create a XenoAgentNode for the given agent ID.

        Args:
            agent_id: The ID of the agent to create a node for.

        Returns:
            A XenoAgentNode instance.
        """
        # Import here to avoid circular dependency
        from xeno_agent.agentpool.node import XenoAgentNode

        return XenoAgentNode(
            agent_id=agent_id,
            factory=self.factory,
            flow_config=self.flow_config,
            tool_manager=self.tool_manager,
            model=self.model,
        )

    async def stream(
        self,
        agent_id: str,
        message: str,
        history: list[ModelMessage] | None = None,
        session_id: str | None = None,
    ) -> AsyncIterator[AgentSwitchEvent | ContentEvent | ThoughtEvent | ToolResultEvent | ToolStartEvent]:
        """Stream events from agent execution.

        This method:
        1. Creates a XenoAgentNode for the specified agent
        2. Executes the agent with the given message
        3. Emits events representing the execution:
           - ContentEvent for text output
           - ThoughtEvent for reasoning/thinking
           - ToolStartEvent for tool calls
           - ToolResultEvent for tool returns
           - AgentSwitchEvent for delegation

        Note: Current implementation emits events post-execution.
        Future versions may support true streaming.

        Args:
            agent_id: The ID of the agent to execute.
            message: The user message to process.
            history: Optional message history for context.
            session_id: Optional session ID for tracking.

        Yields:
            AgentStreamEvent objects representing the execution flow.
        """
        # Create agent node
        node = self._create_node(agent_id)

        # Execute agent
        logger.debug(f"InteractionManager.stream(): Executing agent {agent_id}")
        result_node = await node.run(
            message=message,
            history=history,
            session_id=session_id,
        )

        # Emit events from the result
        async for event in self._emit_events_from_node(result_node, agent_id):
            yield event

    async def _emit_events_from_node(
        self,
        node: XenoMessageNode,
        agent_id: str,
    ) -> AsyncIterator[AgentSwitchEvent | ContentEvent | ThoughtEvent | ToolResultEvent | ToolStartEvent]:
        """Emit events from a XenoMessageNode.

        This method extracts information from the message node and emits
        appropriate events. It handles:
        - Tool calls (ToolStartEvent)
        - Tool returns (ToolResultEvent)
        - Text content (ContentEvent)
        - Thinking/reasoning (ThoughtEvent)
        - Agent switching (AgentSwitchEvent)

        Args:
            node: The XenoMessageNode to emit events from.
            agent_id: The current agent ID.

        Yields:
            AgentStreamEvent objects representing the node's contents.
        """
        # Emit agent switch event if this is a delegated agent
        current_agent_id = node.metadata.get("agent_id", agent_id)
        if current_agent_id != agent_id:
            # Agent delegation occurred - emit switch event
            agent_name = self.flow_config.agents.get(current_agent_id, {}).get("name", current_agent_id)
            yield AgentSwitchEvent(
                agent_id=current_agent_id,
                name=agent_name,
            )

        # First, emit tool start events
        for tool_call in node.tool_calls:
            yield ToolStartEvent(
                call_id=tool_call.get("tool_call_id", str(uuid.uuid4())),
                name=tool_call.get("tool_name", "unknown"),
                args=tool_call.get("args", {}),
            )

        # Then, emit tool result events
        for tool_return in node.tool_returns:
            yield ToolResultEvent(
                call_id=tool_return.get("tool_call_id", ""),
                result=tool_return.get("content", ""),
            )

        # Then, process message parts for content and thought events
        for part in node.parts:
            if isinstance(part, TextPart):
                # Emit content event for text parts
                yield ContentEvent(
                    delta=part.content,
                )
            elif isinstance(part, ThinkingPart) and hasattr(part, "content"):
                # Emit thought event for thinking parts
                yield ThoughtEvent(
                    delta=part.content,
                )
