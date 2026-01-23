import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from mcp.types import ImageContent, TextContent
from pydantic_ai import RunContext, Tool
from pydantic_ai.mcp import MCPServer, MCPServerStdio, MCPServerStreamableHTTP

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

    async def initialize(self, skip_mcp: bool = False, mcp_timeout: float = 30.0):
        """
        Initialize all configured MCP servers and pre-fetch tool definitions.

        Args:
            skip_mcp: If True, skip MCP server initialization (useful for quick startup)
            mcp_timeout: Timeout in seconds for MCP server connections (default: 30s)
        """
        self._stack = AsyncExitStack()
        try:
            if skip_mcp:
                logger.info("Skipping MCP tool initialization (--skip-mcp-tools enabled)")
                return

            for server_config in self.config.mcp_servers:
                # Don't use tool_prefix here - we'll handle it manually to get {mcp_name}__{tool_name}
                # The server returns tool names with _ prefix (e.g., _search_database)
                # We'll construct the final name as: {mcp_name}__{tool_name}

                server: MCPServer
                if server_config.url:
                    # Use empty tool_prefix to get raw tool names from server
                    server = MCPServerStreamableHTTP(
                        url=server_config.url,
                        tool_prefix="",  # No prefix - we'll add {mcp_name}__ manually
                    )
                elif server_config.command:
                    server = MCPServerStdio(
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env,
                        tool_prefix="",  # No prefix - we'll add {mcp_name}__ manually
                    )
                else:
                    logger.warning(f"Skipping invalid MCP server config: {server_config.name}")
                    continue

                # Manage server lifecycle with timeout
                try:
                    server_ctx = server.__aenter__()
                    await asyncio.wait_for(server_ctx, timeout=mcp_timeout)
                    await self._stack.enter_async_context(server)
                    self._servers[server_config.name] = server
                except TimeoutError:
                    logger.exception(f"Timeout connecting to MCP server '{server_config.name}' after {mcp_timeout}s. Server will be skipped.")
                    continue

                # Pre-fetch and wrap tools
                try:
                    tools_defs = await asyncio.wait_for(server.list_tools(), timeout=mcp_timeout)
                    for tool_def in tools_defs:
                        # Construct fully qualified tool name
                        full_name = f"{server_config.name}__{tool_def.name}"

                        # Create a bound runner function
                        runner = self._create_runner(server, tool_def.name)

                        # Get input schema from ToolDefinition (using snake_case attribute)
                        input_schema = getattr(tool_def, "input_schema", None)
                        if input_schema is None:
                            logger.warning(f"No input_schema found for tool {full_name}")

                        # Create PydanticAI Tool
                        tool = Tool.from_schema(
                            function=runner,
                            name=full_name,
                            description=tool_def.description,
                            json_schema=input_schema,
                        )
                        self._all_tools[full_name] = tool
                        logger.debug(f"Registered MCP tool: {full_name}")
                except TimeoutError:
                    logger.exception(f"Timeout listing tools from MCP server '{server_config.name}' after {mcp_timeout}s. Tools from this server will be unavailable.")
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
