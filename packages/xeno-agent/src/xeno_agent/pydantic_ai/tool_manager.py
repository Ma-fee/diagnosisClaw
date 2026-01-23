import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp.types import ImageContent, TextContent
from pydantic_ai import RunContext, Tool
from pydantic_ai.mcp import MCPServer, MCPServerHTTP, MCPServerStdio

from .models import FlowToolsConfig

logger = logging.getLogger(__name__)


class FlowToolManager:
    """
    Manages MCP servers and provides tools to agents.

    Handles initialization, connection management, and tool wrapping for PydanticAI agents.
    """

    def __init__(self, config: FlowToolsConfig):
        self.config = config
        self._stack: AsyncExitStack | None = None
        self._servers: dict[str, MCPServer] = {}
        self._all_tools: dict[str, Tool] = {}

    async def initialize(self):
        """
        Initialize all configured MCP servers and pre-fetch tool definitions.
        """
        self._stack = AsyncExitStack()
        try:
            for server_config in self.config.mcp_servers:
                # User requested format: {mcp_name}__{tool_name}
                tool_prefix = f"{server_config.name}__"

                server: MCPServer
                if server_config.url:
                    server = MCPServerHTTP(
                        url=server_config.url,
                        tool_prefix=tool_prefix,
                    )
                elif server_config.command:
                    server = MCPServerStdio(
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env,
                        tool_prefix=tool_prefix,
                    )
                else:
                    logger.warning(f"Skipping invalid MCP server config: {server_config.name}")
                    continue

                # Manage server lifecycle
                await self._stack.enter_async_context(server)
                self._servers[server_config.name] = server

                # Pre-fetch and wrap tools
                try:
                    tools_defs = await server.list_tools()
                    for tool_def in tools_defs:
                        # Construct the fully qualified tool name
                        full_name = f"{server_config.name}__{tool_def.name}"

                        # Create a bound runner function
                        runner = self._create_runner(server, tool_def.name)

                        # Create PydanticAI Tool
                        tool = Tool.from_schema(
                            function=runner,
                            name=full_name,
                            description=tool_def.description,
                            json_schema=tool_def.inputSchema,
                        )
                        self._all_tools[full_name] = tool
                        logger.debug(f"Registered MCP tool: {full_name}")
                except Exception:
                    logger.exception(f"Failed to list tools for server {server_config.name}")

        except Exception:
            await self.cleanup()
            raise

    def _create_runner(self, server: MCPServer, tool_name: str):
        """Creates a closure to execute the MCP tool."""

        async def runner(ctx: RunContext[Any], **kwargs: Any) -> str:
            try:
                # Call the tool on the server
                # Note: We pass the raw tool name (without prefix) to the server
                result = await server.call_tool(tool_name, kwargs)

                output = []
                if result.content:
                    for content in result.content:
                        if isinstance(content, TextContent):
                            output.append(content.text)
                        elif isinstance(content, ImageContent):
                            output.append(f"[Image: {content.mimeType}]")

                return "\n".join(output) if output else "No output returned from MCP tool."
            except Exception:
                logger.exception(f"Error calling MCP tool {tool_name}")
                return "Error executing MCP tool"

        return runner

    async def cleanup(self):
        """Close all server connections."""
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self._servers.clear()
            self._all_tools.clear()

    def get_tools(self, tool_names: list[str]) -> list[Tool]:
        """
        Get a list of PydanticAI Tools matching the requested names.

        Args:
            tool_names: List of fully qualified tool names ({mcp_name}__{tool_name})

        Returns:
            List of Tool objects. Ignores unknown tools.
        """
        return [self._all_tools[name] for name in tool_names if name in self._all_tools]
