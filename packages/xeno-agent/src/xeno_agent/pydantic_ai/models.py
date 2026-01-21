from typing import Literal

from pydantic import BaseModel, Field


class ToolConfig(BaseModel):
    mode: Literal["allowlist", "blocklist"] = "allowlist"
    builtins: list[str] = Field(default_factory=list)
    external: list[str] = Field(default_factory=list)


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
