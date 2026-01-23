import logging
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    update_agent_message,
    update_agent_message_text,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    Implementation,
    McpServerStdio,
    TextContentBlock,
)

from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager

logger = logging.getLogger(__name__)


class ACPAgent(Agent):
    """
    ACP Agent implementation for PydanticAI.
    Bridges the flow configuration with ACP's Agent protocol.
    """

    _conn: Client | None = None
    _sessions: set[str] = set()
    _next_session_id: int = 0

    def __init__(
        self,
        factory: AgentFactory,
        flow_config: Any,
        runtime: LocalAgentRuntime | None = None,
        tool_manager: FlowToolManager | None = None,
    ):
        self.factory = factory
        self.flow_config = flow_config
        # If runtime is not provided, create one
        if runtime:
            self.runtime = runtime
        else:
            self.runtime = LocalAgentRuntime(factory=factory, flow_config=flow_config, tool_manager=tool_manager)

    def on_connect(self, conn: Client) -> None:
        """Called when client connects."""
        self._conn = conn

    async def _send_agent_message(self, session_id: str, content: Any) -> None:
        """Helper to send messages to client."""
        if self._conn:
            if isinstance(content, str):
                update = update_agent_message_text(content)
            elif isinstance(content, AgentMessageChunk):
                update = content
            else:
                update = update_agent_message(content)
            await self._conn.session_update(session_id, update)

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        """Handle initialize request."""
        logger.info("ACP: initialize request received")
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(),
            agent_info=Implementation(
                name="xeno-agent",
                title=f"{self.flow_config.name}",
                version="1.0.0",
            ),
        )

    async def authenticate(self, method_id: str, **kwargs: Any) -> AuthenticateResponse | None:
        """Handle authenticate request."""
        logger.info(f"ACP: authenticate request {method_id}")
        return AuthenticateResponse()

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[McpServerStdio] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        """Handle new session request."""
        logger.info(f"ACP: new session request (cwd: {cwd})")
        session_id = str(self._next_session_id)
        self._next_session_id += 1
        self._sessions.add(session_id)
        logger.info(f"ACP: Created session {session_id}")
        return NewSessionResponse(session_id=session_id, modes=None)

    async def load_session(
        self,
        cwd: str,
        mcp_servers: list[McpServerStdio] | None = None,
        session_id: str | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        """Handle load session request."""
        logger.info(f"ACP: load session request (session: {session_id})")
        if session_id:
            self._sessions.add(session_id)
        return LoadSessionResponse()

    async def set_session_mode(self, mode_id: str, session_id: str, **kwargs: Any) -> Any:
        """Handle set session mode request."""
        logger.info(f"ACP: set session mode (session: {session_id}, mode: {mode_id})")

    async def prompt(
        self,
        prompt: list[TextContentBlock],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """Handle prompt request - core interaction point."""
        logger.info(f"ACP: prompt request for session {session_id}")

        if session_id not in self._sessions:
            self._sessions.add(session_id)

        # Extract text from prompt blocks
        user_message = ""
        for block in prompt:
            if isinstance(block, TextContentBlock):
                if user_message:  # Already have content from client
                    await self._send_agent_message(session_id, block)
                else:
                    user_message = block.text

        logger.info(f"ACP: Processing prompt: {user_message[:100]}...")

        try:
            # Determine entry agent
            entry_agent_id = self.flow_config.entry_agent
            if not entry_agent_id and self.flow_config.participants:
                entry_agent_id = self.flow_config.participants[0].id

            if not entry_agent_id:
                raise ValueError("No entry agent defined in flow config")

            # Use LocalAgentRuntime to invoke the entry agent
            result = await self.runtime.invoke(
                entry_agent_id,
                user_message,
                session_id=session_id,
            )

            # Extract response
            response = result.data

            # Send response to client
            if response:
                await self._send_agent_message(session_id, f"{response}")

            logger.info(f"ACP: Response sent for session {session_id}")

            return PromptResponse(stop_reason="end_turn")

        except Exception:
            logger.exception("ACP: Error processing prompt")
            error_msg = "Error processing prompt"
            await self._send_agent_message(session_id, error_msg)
            return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        """Handle cancel request."""
        logger.info(f"ACP: cancel request for session {session_id}")

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle extension method calls."""
        logger.info(f"ACP: extension method call: {method}")
        return {"error": f"Unknown method: {method}"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        """Handle extension notifications."""
        logger.info(f"ACP: extension notification: {method}")

    async def run(self, prompt: str, **kwargs: Any) -> str:
        """Convenience method for tests and direct invocation."""
        entry_agent_id = self.flow_config.entry_agent
        if not entry_agent_id and self.flow_config.participants:
            entry_agent_id = self.flow_config.participants[0].id

        if not entry_agent_id:
            raise ValueError("No entry agent defined in flow config")

        result = await self.runtime.invoke(entry_agent_id, prompt, **kwargs)
        return result.data

    async def run_stream(self, prompt: str):
        """Convenience method for streaming (mocked for now)."""
        # This is a minimal implementation to satisfy tests
        entry_agent_id = self.flow_config.entry_agent
        if not entry_agent_id and self.flow_config.participants:
            entry_agent_id = self.flow_config.participants[0].id

        if not entry_agent_id:
            raise ValueError("No entry agent defined in flow config")

        # LocalAgentRuntime doesn't support streaming yet in a standard way
        # So we just yield a user message and the final result for now
        class MockBlock:
            def __init__(self, text):
                self.text = text

        yield {"role": "user", "content": [MockBlock(prompt)]}
        result = await self.runtime.invoke(entry_agent_id, prompt)
        yield {"role": "assistant", "content": [MockBlock(result.data)]}

    @property
    def sessions(self):
        """Backwards compatibility for tests."""
        # Combine sessions from self._sessions and runtime._active_sessions
        all_sessions = {s: object() for s in self._sessions}
        all_sessions.update(self.runtime._active_sessions)
        return all_sessions
