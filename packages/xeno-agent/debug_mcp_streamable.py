import asyncio
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mcp_streamable_debug")

MCP_URL = "http://10.147.254.3:7006/mcp"


async def debug_streamable_mcp():
    logger.info(f"Connecting to {MCP_URL} using streamablehttp_client...")

    try:
        async with streamablehttp_client(MCP_URL) as (read, write, get_sid):
            logger.info("StreamableHTTP connection context entered.")

            async with ClientSession(read, write) as session:
                logger.info("ClientSession created. Initializing...")
                await session.initialize()
                logger.info("Session initialized successfully.")

                sid = get_sid()
                logger.info(f"Session ID: {sid}")

                logger.info("Listing tools...")
                tools_result = await session.list_tools()
                logger.info(f"Tools found: {len(tools_result.tools)}")
                for tool in tools_result.tools:
                    logger.info(f" - {tool.name}")

    except Exception as e:
        logger.error(f"StreamableHTTP failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_streamable_mcp())
