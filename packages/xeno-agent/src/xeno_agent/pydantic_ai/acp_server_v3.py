"""
ACP Server Implementation using official ACP SDK
Uses agent-client-protocol library with `import acp` pattern
"""

import asyncio
import logging

from xeno_agent.pydantic_ai.interfaces import AgentRuntime

logger = logging.getLogger(__name__)


async def run_acp_stdio_server(runtime: AgentRuntime) -> None:
    """
    Run ACP server using Stdio transport.

    Uses official ACP SDK with `import acp` pattern.
    """
    try:
        import acp

        logger.info("Starting ACP stdio server")

        # Use ACP SDK tools
        server = acp.Server(runtime=runtime, mode="stdio")

        # Start server
        await server.serve()

    except KeyboardInterrupt:
        logger.info("ACP server stopped")
    except Exception:
        logger.exception("ACP server error")
        raise


async def run_acp_http_server(runtime: AgentRuntime, port: int = 8000) -> None:
    """
    Run ACP server using HTTP transport.

    Uses official ACP SDK with `import acp` pattern.
    """
    try:
        import acp

        logger.info(f"Starting ACP HTTP server on port {port}")

        # Use ACP SDK tools
        server = acp.Server(runtime=runtime, mode="http", port=port)

        # Start server
        await server.serve()

    except KeyboardInterrupt:
        logger.info("ACP server stopped")
    except Exception:
        logger.exception("ACP server error")
        raise


def run_acp_cli():
    """
    CLI entry point for ACP server.

    Usage: python -m xeno_agent.pydantic_ai.acp_server [mode] [options]

    Commands:
      stdio    Run ACP server with stdio transport (default)
      http       Run ACP server with HTTP transport
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="ACP Server for pydantic-ai agents",
    )
    parser.add_argument(
        "mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio or http (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport (default: 8000)",
    )

    args = parser.parse_args()

    print(f"Starting ACP server in {args.mode} mode...")

    # Import runtime
    from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime

    # Create runtime
    runtime = LocalAgentRuntime()

    # Run appropriate server
    if args.mode == "http":
        asyncio.run(run_acp_http_server(runtime, args.port))
    else:
        asyncio.run(run_acp_stdio_server(runtime))


if __name__ == "__main__":
    run_acp_cli()
