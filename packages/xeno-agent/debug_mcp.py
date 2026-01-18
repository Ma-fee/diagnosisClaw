import asyncio
import logging

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mcp_debug")

MCP_URL = "http://10.147.254.3:7006/sse"


async def debug_mcp_connection():
    logger.info(f"Attempting to connect to MCP server at {MCP_URL}")

    try:
        # 1. Test raw HTTP connectivity first
        logger.info("Step 1: Testing raw HTTP connectivity...")
        async with httpx.AsyncClient() as client:
            try:
                # Try a GET request first to see if the endpoint exists/responds
                resp = await client.get(MCP_URL, timeout=5.0)
                logger.info(f"HTTP GET response: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                logger.error(f"HTTP GET failed: {e}")

    except Exception as e:
        logger.error(f"Step 1 failed: {e}")

    try:
        # 2. Test MCP SSE connection
        logger.info("Step 2: Testing MCP SSE connection...")
        async with sse_client(MCP_URL) as (read, write):
            logger.info("SSE Connection established.")

            async with ClientSession(read, write) as session:
                logger.info("ClientSession created. Initializing...")
                await session.initialize()
                logger.info("Session initialized successfully.")

                logger.info("Listing tools...")
                tools_result = await session.list_tools()
                logger.info(f"Tools found: {len(tools_result.tools)}")
                for tool in tools_result.tools:
                    logger.info(f" - {tool.name}: {tool.description}")

                # Optional: Try to call the search_database tool if it exists
                tool_name = "search_database"
                if any(t.name == tool_name for t in tools_result.tools):
                    logger.info(f"Attempting to call '{tool_name}'...")
                    result = await session.call_tool(tool_name, arguments={"query": "test query", "limit": 1})
                    logger.info(f"Tool call result: {result}")
                else:
                    logger.warning(f"Tool '{tool_name}' not found in list.")

    except Exception as e:
        logger.error(f"MCP Connection/Session failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(debug_mcp_connection())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
