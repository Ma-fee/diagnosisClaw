"""
Generic MCP Tool Adapter for CrewAI.
"""

import asyncio
import io
import sys

import nest_asyncio
from crewai.tools import BaseTool
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import Field

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Install global error suppression for benign async cleanup errors
# This is required because httpcore/anyio objects are often GC'd after the tool execution finishes
# and the loop is closed, causing "no running event loop" errors to be printed to stderr.
_original_unraisablehook = sys.unraisablehook


def _filter_unraisable_errors(unraisable):
    err_str = str(unraisable.exc_value)
    if unraisable.exc_type is RuntimeError and ("async generator ignored GeneratorExit" in err_str or "no running event loop" in err_str or "cancel scope" in err_str):
        return
    _original_unraisablehook(unraisable)


sys.unraisablehook = _filter_unraisable_errors


class StderrFilter:
    """
    Filter stderr to suppress benign async cleanup errors.
    """

    def __init__(self):
        self.original_stderr = sys.stderr
        self.buffer = io.StringIO()

    def __enter__(self):
        sys.stderr = self.buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stderr = self.original_stderr
        # Process captured output
        self.buffer.seek(0)
        for line in self.buffer.readlines():
            if "async generator ignored GeneratorExit" in line:
                continue
            if "no running event loop" in line:
                continue
            if "cancel scope" in line:
                continue
            if "Exception ignored in" in line:
                continue
            if "Traceback (most recent call last)" in line:
                continue
            if "File " in line and "httpcore" in line:
                continue
            if "File " in line and "anyio" in line:
                continue

            # If not filtered, write to original stderr
            self.original_stderr.write(line)


class GenericMCPTool(BaseTool):
    """
    A generic adapter to expose an MCP tool as a CrewAI BaseTool.
    """

    name: str = Field(..., description="Name of the tool")
    description: str = Field(..., description="Description of the tool")
    mcp_url: str = Field(..., description="URL of the MCP server")
    mcp_tool_name: str = Field(..., description="Name of the tool in MCP")
    # args_schema: Optional[Type[BaseModel]] = Field(None, description="Schema for tool arguments")

    def _run(self, **kwargs) -> str:
        """
        Execute the tool synchronously by running the async implementation.
        """
        # Use stderr filter to suppress benign cleanup noise
        with StderrFilter():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return loop.run_until_complete(self._arun(**kwargs))
                return asyncio.run(self._arun(**kwargs))
            except RuntimeError:
                return asyncio.run(self._arun(**kwargs))
            except Exception as e:
                # Better error reporting for ExceptionGroups (common in asyncio/anyio)
                if hasattr(e, "exceptions"):
                    error_msgs = [str(exc) for exc in e.exceptions]  # type: ignore
                    return f"Error executing MCP tool: {'; '.join(error_msgs)}"
                return f"Error executing MCP tool: {e!s}"

    async def _arun(self, **kwargs) -> str:
        """
        Execute the tool asynchronously via MCP protocol.
        """
        # Connect to MCP server via StreamableHTTP (POST + SSE)
        async with streamablehttp_client(self.mcp_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Call the tool
                # MCP expects arguments as a dictionary
                result = await session.call_tool(self.mcp_tool_name, arguments=kwargs)

                # Format result
                output = []
                if result.content:
                    for content in result.content:
                        if content.type == "text":
                            output.append(content.text)
                        # Handle other types if needed (image, etc.)

                return "\n".join(output) if output else "No output returned from MCP tool."
