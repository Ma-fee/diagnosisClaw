"""
MCP (Model Context Protocol) support for PydanticAI.
"""

import logging
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic_ai import Agent, RunContext, Tool
from mcp.types import TextContent, ImageContent

logger = logging.getLogger(__name__)


class MCPBridgeToolset:
    """Bridges tools from external MCP servers to a PydanticAI agent."""

    def __init__(self, mcp_urls: list[str]):
        self.mcp_urls = mcp_urls

    async def attach_to_agent(self, agent: Agent[Any, Any]) -> None:
        """Fetch tools from all configured MCP servers and attach them to the agent."""
        for url in self.mcp_urls:
            try:
                logger.info(f"Fetching tools from MCP server: {url}")
                async with streamablehttp_client(url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        for tool_def in tools_result.tools:
                            self._attach_tool(agent, url, tool_def)
                            logger.info(f"Attached MCP tool: {tool_def.name} from {url}")
            except Exception as e:
                logger.error(f"Failed to attach tools from MCP server {url}: {e}")

    def _attach_tool(self, agent: Agent[Any, Any], url: str, tool_def: Any) -> None:
        """Creates a wrapper for a single MCP tool and attaches it to the agent."""
        tool_name = tool_def.name
        tool_description = tool_def.description
        input_schema = tool_def.inputSchema

        async def mcp_tool_wrapper(**kwargs: Any) -> Any:
            """Wrapper for MCP tool."""
            try:
                async with streamablehttp_client(url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments=kwargs)

                        output = []
                        if result.content:
                            for content in result.content:
                                if isinstance(content, TextContent):
                                    output.append(content.text)
                                elif isinstance(content, ImageContent):
                                    output.append(f"[Image: {content.mimeType}]")

                        return "\n".join(output) if output else "No output returned from MCP tool."
            except Exception as e:
                logger.error(f"Error calling MCP tool {tool_name}: {e}")
                return f"Error executing MCP tool: {e!s}"

        # Register using from_schema for better validation support in PydanticAI
        tool = Tool.from_schema(
            function=mcp_tool_wrapper,
            name=tool_name,
            description=tool_description,
            json_schema=input_schema,
        )
        agent.tool(tool)
