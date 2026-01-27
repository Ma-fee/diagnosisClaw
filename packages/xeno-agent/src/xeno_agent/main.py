"""Xeno Agent CLI entry point."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import typer
import yaml
from acp import serve as acp_serve
from acp.agent.connection import AgentSideConnection
from acp.agent.protocol import Agent as ACPAgentProtocol
from acp.schema import (
    AgentMessageChunk,
    AuthenticateRequest,
    AuthenticateResponse,
    CancelNotification,
    ForkSessionRequest,
    ForkSessionResponse,
    InitializeRequest,
    InitializeResponse,
    ListSessionsRequest,
    ListSessionsResponse,
    LoadSessionRequest,
    LoadSessionResponse,
    NewSessionRequest,
    NewSessionResponse,
    PromptRequest,
    PromptResponse,
    ResumeSessionRequest,
    ResumeSessionResponse,
    SessionInfo,
    SessionMode,
    SessionModeState,
    SessionNotification,
    SetSessionConfigOptionRequest,
    SetSessionConfigOptionResponse,
    SetSessionModelRequest,
    SetSessionModelResponse,
    SetSessionModeRequest,
    SetSessionModeResponse,
    TextContentBlock,
)
from agentpool.agents.events import PartDeltaEvent, StreamCompleteEvent
from pydantic_ai import TextPartDelta

from xeno_agent.agentpool.core.agent import XenoAgent
from xeno_agent.agentpool.core.config import RoleType, XenoConfig, XenoRoleConfig

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("xeno-agent")

app = typer.Typer()


class XenoACPAgent(ACPAgentProtocol):
    """ACP Agent implementation for Xeno."""

    def __init__(self, xeno_config: XenoConfig, connection: AgentSideConnection):
        self.xeno_config = xeno_config
        self.connection = connection
        self.sessions: dict[str, XenoAgent] = {}
        # Default agent for stateless operations
        self.default_agent = XenoAgent(name="xeno", xeno_config=xeno_config)

    async def initialize(self, params: InitializeRequest) -> InitializeResponse:
        """Initialize the agent."""
        return InitializeResponse.create(
            name="xeno-agent",
            title="Xeno Agent",
            version="0.1.0",
            protocol_version=1,
            list_sessions=True,
            load_session=True,
        )

    async def new_session(self, params: NewSessionRequest) -> NewSessionResponse:
        """Create a new session."""
        session_id = str(uuid4())
        agent = XenoAgent(name="xeno", xeno_config=self.xeno_config)
        # Configure agent with cwd from params if supported
        # We store the agent in memory
        self.sessions[session_id] = agent

        # Build modes from config
        acp_modes = []
        current_mode_id = "qa"

        # We need to initialize agent to get modes, or get from config directly
        # agent.get_modes() is async
        try:
            modes = await agent.get_modes()
            if modes:
                category = modes[0]  # Usually role
                current_mode_id = category.current_mode_id
                acp_modes.extend(SessionMode(id=mode.id, name=mode.name, description=mode.description) for mode in category.available_modes)
        except Exception as e:
            logger.warning(f"Failed to get modes: {e}")

        mode_state = SessionModeState(available_modes=acp_modes, current_mode_id=current_mode_id)

        return NewSessionResponse(
            session_id=session_id,
            modes=mode_state,
        )

    async def load_session(self, params: LoadSessionRequest) -> LoadSessionResponse:
        # Minimal implementation
        if params.session_id not in self.sessions:
            self.sessions[params.session_id] = XenoAgent(name="xeno", xeno_config=self.xeno_config)
        return LoadSessionResponse()

    async def list_sessions(self, params: ListSessionsRequest) -> ListSessionsResponse:
        sessions = [SessionInfo(session_id=sid, title=f"Xeno Session {sid[:8]}", updated_at=None, cwd="") for sid in self.sessions]
        return ListSessionsResponse(sessions=sessions)

    async def prompt(self, params: PromptRequest) -> PromptResponse:
        agent = self.sessions.get(params.session_id)
        if not agent:
            agent = XenoAgent(name="xeno", xeno_config=self.xeno_config)
            self.sessions[params.session_id] = agent

        prompt_text = ""
        for item in params.prompt:
            if item.type == "text":
                prompt_text += item.text

        try:
            # We use run_stream to get chunks
            async for event in agent.run_stream(prompt_text):
                if isinstance(event, PartDeltaEvent):
                    # Send chunk
                    delta = event.delta
                    content_str = ""
                    if isinstance(delta, TextPartDelta):
                        content_str = delta.content_delta
                    elif isinstance(delta, str):
                        content_str = delta

                    if content_str:
                        update = AgentMessageChunk(content=TextContentBlock(text=content_str))
                        await self.connection.session_update(SessionNotification(session_id=params.session_id, update=update))
                elif isinstance(event, StreamCompleteEvent):
                    pass  # Done

        except Exception as e:
            logger.error(f"Error in prompt: {e}")
            # We should probably notify error but let's return clean stop

        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, params: CancelNotification) -> None:
        pass

    async def fork_session(self, params: ForkSessionRequest) -> ForkSessionResponse:
        return ForkSessionResponse(session_id=str(uuid4()))

    async def resume_session(self, params: ResumeSessionRequest) -> ResumeSessionResponse:
        return ResumeSessionResponse()

    async def authenticate(self, params: AuthenticateRequest) -> AuthenticateResponse | None:
        return None

    async def set_session_mode(self, params: SetSessionModeRequest) -> SetSessionModeResponse | None:
        if agent := self.sessions.get(params.session_id):
            await agent.set_mode(params.mode_id, category_id="role")
            return SetSessionModeResponse()
        return None

    async def set_session_model(self, params: SetSessionModelRequest) -> SetSessionModelResponse | None:
        return None

    async def set_session_config_option(self, params: SetSessionConfigOptionRequest) -> SetSessionConfigOptionResponse | None:
        return None

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass


@app.command()
def version():
    """Print version."""
    print("xeno-agent v0.1.0")


@app.command()
def serve(config_path: str = "config/xeno_config.yaml"):
    """Start the Xeno ACP server."""

    # Load config
    xeno_config: XenoConfig
    try:
        # Resolve config path relative to package or current dir
        path = Path(config_path)
        if not path.exists():
            # Try to look in package config dir if relative path not found
            pkg_config = Path(__file__).parent.parent.parent / "config" / "xeno_config.yaml"
            if pkg_config.exists():
                path = pkg_config

        if path.exists():
            with path.open() as f:
                config_data = yaml.safe_load(f)
            xeno_config = XenoConfig.model_validate(config_data)
            logger.info(f"Loaded config from {path}")
            logger.info(f"DEBUG: Loaded Xeno configuration with roles: {[(r_id, r.model) for r_id, r in xeno_config.roles.items()]}")
        else:
            raise FileNotFoundError(f"Config file not found: {path}")

    except Exception as e:
        logger.warning(f"Failed to load config: {e}. Using default.")
        xeno_config = XenoConfig(roles={"qa": XenoRoleConfig(type=RoleType.QA_ASSISTANT, name="qa", system_prompt="You are Xeno.", model="openai-chat:svc/glm-4.7")})

    async def run_server():
        await acp_serve(
            lambda conn: XenoACPAgent(xeno_config, conn),
            transport="stdio",
        )

    asyncio.run(run_server())


def main():
    app()


if __name__ == "__main__":
    main()
