import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", v):
            raise ValueError("Name must start with a letter and contain only alphanumeric characters or underscores")
        return v

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> "MCPServerConfig":
        if self.url and (self.command or self.args or self.env):
            raise ValueError("Cannot specify both 'url' and 'command/args/env'")
        if not self.url and not self.command:
            raise ValueError("Must specify either 'url' or 'command'")
        return self


class FlowToolsConfig(BaseModel):
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    system_prompt: str | None = None
    tools: list[str] = Field(default_factory=list)


class FlowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    tools: FlowToolsConfig = Field(default_factory=FlowToolsConfig)
