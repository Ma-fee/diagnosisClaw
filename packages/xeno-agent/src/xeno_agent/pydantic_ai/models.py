from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MCPServerConfig(BaseModel):
    """Configuration for an MCP (Model Context Protocol) server.

    Represents either a remote MCP server (URL-based) or a local MCP server
    (command-based), but never both simultaneously.
    """

    url: str | None = Field(default=None, description="URL of the remote MCP server (e.g., 'http://localhost:8000/sse'). Mutually exclusive with 'command'.")

    command: str | None = Field(
        default=None,
        description="Command to spawn a local MCP server process (e.g., 'npx @modelcontextprotocol/server-filesystem'). Mutually exclusive with 'url'.",
    )

    args: list[str] = Field(
        default_factory=list,
        description="Additional command-line arguments to pass to the server process. Only used when 'command' is provided. Example: ['/path/to/root', '--verbose'].",
    )

    env: dict[str, str] | None = Field(default=None, description="Environment variables for the server process. Only used when 'command' is provided. Example: {'DEBUG': 'true'}.")
    timeout: float = Field(default=5.0, description="Connection timeout in seconds.")
    read_timeout: float = Field(default=300.0, description="Read timeout in seconds.")
    max_retries: int = Field(default=1, description="Maximum number of retries for tool calls.")
    allow_sampling: bool = Field(default=True, description="Whether to allow the server to request sampling (LLM completions).")
    cache_tools: bool = Field(default=True, description="Whether to cache tools discovered from the server.")
    cache_resources: bool = Field(default=True, description="Whether to cache resources discovered from the server.")
    tool_prefix: str | None = Field(default=None, description="Prefix to add to all tools from this server to avoid name collisions.")
    headers: dict[str, str] | None = Field(default=None, description="Custom HTTP headers to send with requests (for URL-based servers).")
    cwd: str | None = Field(default=None, description="The working directory to use when spawning the process. Only used when 'command' is provided.")
    id: str | None = Field(default=None, description="Unique ID for MCP server (used by tool_prefix if not set).")
    log_level: Literal["debug", "info", "warn", "error"] | None = Field(default=None, description="Log level to set when connecting to server.")
    client_info: dict[str, str] | None = Field(
        default=None,
        description="Client identification information (e.g., {'name': 'my-client', 'version': '1.0.0'}) sent to server during initialization.",
    )

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> "MCPServerConfig":
        """Ensure that exactly one of 'url' or 'command' is provided.

        Returns:
            self if validation passes

        Raises:
            ValueError: If both 'url' and 'command' are provided, or if neither is provided
        """
        has_url = self.url is not None
        has_command = self.command is not None

        if has_url and has_command:
            raise ValueError("Invalid MCPServerConfig: cannot specify both 'url' and 'command'. Provide either a remote server URL or a local server command, not both.")

        if not has_url and not has_command:
            raise ValueError(
                "Invalid MCPServerConfig: must specify either 'url' or 'command'. "
                "Provide a remote server URL for HTTP/SSE connections, or a local server command for subprocess-based servers.",
            )

        return self


class ToolConfig(BaseModel):
    mode: Literal["allowlist", "blocklist"] = "allowlist"
    builtins: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)
    mcp_servers: list[str | MCPServerConfig] = Field(default_factory=list)


class AgentConfig(BaseModel):
    identifier: str
    type: Literal["main", "sub"] = "sub"
    role: str
    backstory: str
    when_to_use: str
    allow_delegation_to: list[str] = Field(default_factory=list)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    skills: list[str] = Field(default_factory=list)


class FlowConfig(BaseModel):
    name: str
    description: str
    entry_agent: str
    participants: list[str]
    global_instructions: str
    delegation_rules: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
