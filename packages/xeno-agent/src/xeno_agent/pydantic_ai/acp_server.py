import logging
import uuid
from typing import TYPE_CHECKING, Any

from acp import Agent, schema
from acp.interfaces import Client

if TYPE_CHECKING:
    from xeno_agent.pydantic_ai.tool_manager import FlowToolManager

from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.runtime import AgentFactoryProtocol, RuntimeDeps
from xeno_agent.pydantic_ai.trace import TraceID

logger = logging.getLogger(__name__)


class ACPAgent(Agent):
    """ACP Agent implementation using official agent-client-protocol SDK."""

    def __init__(self, factory: AgentFactoryProtocol, flow_config: FlowConfig, tool_manager: "FlowToolManager"):
        self.factory = factory
        self.flow_config = flow_config
        self.tool_manager = tool_manager
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
        **kwargs: Any,
    ) -> schema.NewSessionResponse:
        session_id = str(uuid.uuid4())

        # Create agent with flow-scoped tool manager
        # NOTE: MCP servers are now managed at flow level, not session level
        # The mcp_servers parameter from protocol is ignored
        agent = await self.factory.create(
            self.flow_config.entry_agent,
            self.flow_config,
            self.tool_manager,
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
                tool_manager=self.tool_manager,
                session_id=session_id,
                message_history=history,
            )
            # NOTE: No longer need async with agent.run_mcp_servers() - tools are pre-bound
            result = await agent.run(text, deps=deps, message_history=history)
            session_data["history"] = result.all_messages()
            return schema.PromptResponse(stopReason="end_turn")
        except Exception:
            logger.exception("Prompt error in session %s", session_id)
            raise
