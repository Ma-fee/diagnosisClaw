import re
from typing import Any

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
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    description: str = ""
    identifier: str | None = None
    role: str | None = None
    backstory: str | None = None
    system_prompt: str | None = None
    allow_delegation_to: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ParticipantConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    role: str = ""


class DelegationRuleConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    from_agent: str
    to_agent: str
    condition: str = ""


class FlowConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    description: str | None = None
    entry_agent: str | None = None
    global_instructions: str | None = None
    tools: FlowToolsConfig = Field(default_factory=FlowToolsConfig)
    participants: list[ParticipantConfig] = Field(default_factory=list)
    delegation_rules: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def handle_legacy_formats(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Handle delegation_rules list-to-dict
        if "delegation_rules" in data:
            rules = data["delegation_rules"]
            if isinstance(rules, list):
                new_rules = {}
                for rule in rules:
                    if isinstance(rule, dict):
                        from_agent = rule.get("from_agent")
                        to_agent = rule.get("to_agent")
                        if from_agent and to_agent:
                            if from_agent not in new_rules:
                                new_rules[from_agent] = {"allow_delegation_to": []}
                            if to_agent not in new_rules[from_agent]["allow_delegation_to"]:
                                new_rules[from_agent]["allow_delegation_to"].append(to_agent)
                data["delegation_rules"] = new_rules

        # Handle participants string-to-object
        if "participants" in data:
            participants = data["participants"]
            if isinstance(participants, list):
                new_participants = []
                for p in participants:
                    if isinstance(p, str):
                        new_participants.append({"id": p, "role": p})
                    else:
                        new_participants.append(p)
                data["participants"] = new_participants

        return data
