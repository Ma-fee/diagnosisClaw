import asyncio
import logging

import httpx

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mcp_manual")

MCP_URL = "http://10.147.254.3:7006/mcp"


async def probe_mcp_headers():
    logger.info(f"Probing paths on {MCP_URL}")

    base = "http://10.147.254.3:7006"
    paths = [
        "/mcp/",
        "/mcp/sse/",
        "/sse/",
        "/mcp",
    ]

    headers = {"Accept": "text/event-stream"}

    async with httpx.AsyncClient() as client:
        for path in paths:
            url = f"{base}{path}"
            logger.info(f"--- Trying GET {url} ---")

            try:
                async with client.stream("GET", url, headers=headers, timeout=5.0) as response:
                    logger.info(f"Status: {response.status_code}")
                    if response.status_code == 200:
                        logger.info(f"SUCCESS on {path}!")
                        async for chunk in response.aiter_lines():
                            logger.info(f"First chunk: {chunk}")
                            break
                    else:
                        body = ""
                        async for chunk in response.aiter_lines():
                            body += chunk
                        logger.info(f"Error Body: {body[:200]}")
            except Exception as e:
                logger.error(f"Failed: {e}")


if __name__ == "__main__":
    asyncio.run(probe_mcp_headers())
