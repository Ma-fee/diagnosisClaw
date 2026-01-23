#!/usr/bin/env python3
import argparse
import asyncio
import logging
from pathlib import Path

from acp import run_agent

from xeno_agent.pydantic_ai.acp_server import ACPAgent
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="ACPAgent CLI")
    parser.add_argument("flow_id", help="Flow ID to run")
    parser.add_argument("--model", default="openai:svc/glm-4.7", help="LLM model")
    parser.add_argument("--config-path", type=Path, help="Path to config directory")
    parser.add_argument("--skills-path", type=Path, help="Path to skills directory")
    parser.add_argument("--transport", default="stdio", choices=["stdio", "sse"], help="Transport type")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE transport")  # noqa: S104
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    args = parser.parse_args()

    base_pkg_path = Path(__file__).parents[3]
    config_path = args.config_path or base_pkg_path / "config"
    # skills_path = args.skills_path or base_pkg_path / "skills" / "pydantic_ai"

    loader = YAMLConfigLoader(base_path=config_path)
    factory = AgentFactory(config_loader=loader, model=args.model)
    flow_config = loader.load_flow_config(args.flow_id)

    acp_agent = ACPAgent(factory=factory, flow_config=flow_config)
    logger.info(f"Starting ACPAgent for flow: {args.flow_id}")
    logger.info(f"Transport: {args.transport}")
    logger.info(f"Model: {args.model}")

    if args.transport == "sse":
        logger.info(f"SSE server on {args.host}:{args.port}")
        await run_agent(acp_agent, transport="sse", host=args.host, port=args.port)
    else:
        await run_agent(acp_agent, transport="stdio")


if __name__ == "__main__":
    asyncio.run(main())
