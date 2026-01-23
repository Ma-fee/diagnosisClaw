import logging
import uuid
from typing import TYPE_CHECKING, Any

from acp import Agent, schema
from acp.interfaces import Client

if TYPE_CHECKING:
    pass

from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.runtime import AgentFactoryProtocol, RuntimeDeps
from xeno_agent.pydantic_ai.trace import TraceID

logger = logging.getLogger(__name__)

try:
    from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP
except ImportError:
    logger.warning("pydantic_ai MCP support not available")

    class MCPServerStdio:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("pydantic_ai MCP support not available")

    class MCPServerStreamableHTTP:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("pydantic_ai MCP support not available")


class ACPAgent(Agent):
    """ACP Agent implementation using the official agent-client-protocol SDK."""

    def __init__(self, factory: AgentFactoryProtocol, flow_config: FlowConfig):
        self.factory = factory
        self.flow_config = flow_config
        self.sessions: dict[str, dict] = {}
        self._conn: Client | None = None

    def on_connect(self, conn: Client) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: str,
        capabilities: dict[str, Any],
        client_info: dict[str, Any],
        **kwargs: Any,
    ) -> schema.InitializeResponse:
        year = int(protocol_version.split("-")[0])
        return schema.InitializeResponse(
            protocol_version=year,
            agent_info={"name": "ACPAgent", "version": "0.1.0"},
            agent_capabilities=schema.AgentCapabilities(
                session_capabilities=schema.SessionCapabilities(),
            ),
        )

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any],
        **kwargs: Any,
    ) -> schema.NewSessionResponse:
        session_id = str(uuid.uuid4())

        pydantic_mcp = []
        for s in mcp_servers:
            if isinstance(s, schema.HttpMcpServer | schema.SseMcpServer):
                pydantic_mcp.append(MCPServerStreamableHTTP(s.url, headers=s.headers))
            elif isinstance(s, schema.McpServerStdio):
                pydantic_mcp.append(MCPServerStdio(s.command, args=s.args, env=s.env))

        agent = await self.factory.create(
            self.flow_config.entry_agent,
            self.flow_config,
            use_cache=False,
            extra_mcp_servers=pydantic_mcp,
        )
        self.sessions[session_id] = {"agent": agent, "history": []}
        return schema.NewSessionResponse(sessionId=session_id)

    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        **kwargs: Any,
    ) -> schema.PromptResponse:
        try:
            text = " ".join([b.text for b in prompt if hasattr(b, "text")])
            session_data = self.sessions[session_id]
            agent = session_data["agent"]
            history = session_data["history"]
            deps = RuntimeDeps(
                flow=self.flow_config,
                trace=TraceID.new(),
                factory=self.factory,
                session_id=session_id,
                message_history=history,
            )
            async with agent.run_mcp_servers():
                result = await agent.run(text, deps=deps, message_history=history)
            session_data["history"] = result.all_messages()
            return schema.PromptResponse(stopReason="end_turn")
        except Exception:
            logger.exception("Prompt error in session %s", session_id)
            raise
