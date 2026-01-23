#!/usr/bin/env python3
"""
ACP CLI - Agent Client Protocol CLI (v3 Implementation)

Implementation based on official agent-client-protocol examples.
Uses LocalAgentRuntime and integrates with acp.run_agent.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from acp import (
    PROTOCOL_VERSION,
    Agent,
    AuthenticateResponse,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    run_agent,
    update_agent_message,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    AgentMessageChunk,
    Implementation,
    McpServerStdio,
    TextContentBlock,
)

from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime

logger = logging.getLogger(__name__)


def setup_logging(log_file: Path | None = None, log_level: str = "INFO"):
    """Setup logging configuration with optional file logging."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    level = getattr(logging, log_level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        file_handler.setLevel(level)
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers,
        force=True,
    )


class RuntimeToAgentAdapter(Agent):
    """
    Adapter that converts LocalAgentRuntime to acp.Agent protocol.

    Bridges the flow configuration with ACP's Agent protocol.
    """

    _conn: Client | None = None
    _sessions: set[str] = set()
    _next_session_id: int = 0

    def __init__(self, factory: AgentFactory, flow_config: Any, runtime: LocalAgentRuntime):
        self.factory = factory
        self.flow_config = flow_config
        self.runtime = runtime

    def on_connect(self, conn: Client) -> None:
        """Called when client connects."""
        self._conn = conn

    async def _send_agent_message(self, session_id: str, content: Any) -> None:
        """Helper to send messages to client."""
        if self._conn:
            update = content if isinstance(content, AgentMessageChunk) else update_agent_message(content)
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
                title=f"{self.flow_config.flow_name}",
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
            # Use LocalAgentRuntime to invoke the entry agent
            result = await self.runtime.invoke(
                self.flow_config.entry_agent,
                user_message,
                session_id=session_id,
            )

            # Extract response
            response = result.get_final_response_or_raise()

            # Send response to client
            if response:
                await self._send_agent_message(session_id, f"{response}")

            logger.info(f"ACP: Response sent for session {session_id}")

            return PromptResponse(stop_reason="end_turn")

        except Exception:
            logger.exception("ACP: Error processing prompt")
            error_msg = "Error processing prompt"
            await self._send_agent_message(session_id, error_msg)
            return PromptResponse(stop_reason="error", error={"message": error_msg})

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


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ACP CLI - Agent Client Protocol Server (v3)")
    parser.add_argument("flow_id", help="Flow ID to run")
    parser.add_argument("--model", default="openai:svc/glm-4.7", help="LLM model")
    parser.add_argument("--config-path", type=Path, help="Path to config directory")
    parser.add_argument("--log-file", type=Path, help="Path to log file")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log level")
    parser.add_argument("--skip-mcp-tools", action="store_true", help="Skip MCP tool initialization (faster startup)")
    parser.add_argument("--mcp-timeout", type=float, default=30.0, help="MCP server connection timeout in seconds (default: 30)")
    args = parser.parse_args()

    # Setup logging
    setup_logging(log_file=args.log_file, log_level=args.log_level)

    base_pkg_path = Path(__file__).parents[3]
    config_path = args.config_path or base_pkg_path / "config"

    # Load configuration
    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model=args.model)
    flow_config = loader.load_flow_config(args.flow_id)

    logger.info(f"Starting ACP server v3 for flow: {args.flow_id}")
    logger.info("Transport: stdio (default)")
    logger.info(f"Model: {args.model}")

    # Create and initialize runtime
    runtime = LocalAgentRuntime(factory, flow_config)
    await runtime.tool_manager.initialize(skip_mcp=args.skip_mcp_tools, mcp_timeout=args.mcp_timeout)
    logger.info(f"Runtime '{args.flow_id}' initialized with model: {args.model}")

    try:
        # Create Agent adapter and run
        agent = RuntimeToAgentAdapter(factory, flow_config, runtime)
        logger.info("Starting ACP server...")
        await run_agent(agent)
    finally:
        await runtime.tool_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
