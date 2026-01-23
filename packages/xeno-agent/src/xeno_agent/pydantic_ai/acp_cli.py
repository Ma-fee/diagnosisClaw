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

from acp import run_agent

from xeno_agent.pydantic_ai.acp_server import ACPAgent
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
        # Create ACP Agent and run
        agent = ACPAgent(factory, flow_config, runtime=runtime)
        logger.info("Starting ACP server...")
        await run_agent(agent)
    finally:
        await runtime.tool_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
