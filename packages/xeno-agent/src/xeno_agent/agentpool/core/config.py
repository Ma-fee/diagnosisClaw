"""Configuration models for Xeno agent system.

This module defines Pydantic models for the Xeno agent configuration,
reflecting the 4-role collaboration model from RFC 001:
- Q&A Assistant (Gateway/Front Desk)
- Fault Expert (Orchestrator/Diagnostician)
- Equipment Expert (Hybrid Worker+Active)
- Material Assistant (Worker/Researcher)
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import ConfigDict, Field
from schemez import Schema


class RoleType(str, Enum):
    """Xeno agent role types from RFC 001.

    - `qa_assistant`: Gateway/Front Desk role for user intent recognition and simple queries
    - `fault_expert`: Orchestrator/Diagnostician role for fault diagnosis coordination
    - `equipment_expert`: Hybrid role (Worker + Active) for device analysis and guidance
    - `material_assistant`: Worker/Researcher role for document retrieval and summarization
    """

    QA_ASSISTANT = "qa_assistant"
    FAULT_EXPERT = "fault_expert"
    EQUIPMENT_EXPERT = "equipment_expert"
    MATERIAL_ASSISTANT = "material_assistant"


# Type alias for type checking compatibility
RoleTypeLiteral = Literal[
    "qa_assistant",
    "fault_expert",
    "equipment_expert",
    "material_assistant",
]


class XenoRoleConfig(Schema):
    """Configuration for a single Xeno agent role.

    This model defines the configuration for one of the 4 specialized roles
    in the Xeno agent system, following RFC 001 specifications.

    Attributes:
        type: The role type (qa_assistant, fault_expert, equipment_expert, material_assistant)
        name: Human-readable identifier for the role
        description: Optional description of the role's purpose
        system_prompt: System prompt defining the role's behavior
        model: Model identifier string (e.g., "openai:gpt-4o")
        capabilities: Optional list of capabilities the role possesses
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "x-icon": "octicon:robot-16",
            "x-doc-title": "Xeno Role Configuration",
        },
    )

    type: RoleType = Field(
        ...,
        examples=[RoleType.QA_ASSISTANT, RoleType.FAULT_EXPERT, RoleType.EQUIPMENT_EXPERT, RoleType.MATERIAL_ASSISTANT],
        title="Role type",
        description="The type of role this agent plays in Xeno system",
    )
    """Role type from RFC 001's 4-role collaboration model."""

    name: str = Field(
        ...,
        examples=["qa_agent", "fault_agent", "equipment_agent", "material_agent"],
        title="Role name",
        description="Human-readable identifier for this agent role",
    )
    """Unique name for this agent role instance."""

    description: str | None = Field(
        default=None,
        examples=[
            "Q&A Assistant for user query handling",
            "Fault Expert for diagnosis coordination",
            "Equipment Expert for device guidance",
            "Material Assistant for document retrieval",
        ],
        title="Role description",
        description="Optional description of the role's purpose and responsibilities",
    )
    """Human-readable description of what this role does."""

    system_prompt: str = Field(
        ...,
        examples=[
            "You are a helpful Q&A assistant for engineering machinery.",
            "You are a fault diagnosis expert for complex technical issues.",
            "You are an equipment expert for device analysis and user guidance.",
            "You are a material research assistant for technical documentation.",
        ],
        title="System prompt",
        description="System prompt that defines the role's behavior and expertise",
    )
    """System prompt that guides the agent's behavior."""

    model: str = Field(
        ...,
        examples=["openai:gpt-4o", "anthropic:claude-sonnet-4"],
        title="Model",
        description="Model identifier string for the LLM to use",
    )
    """Model identifier (e.g., 'openai:gpt-4o', 'anthropic:claude-sonnet-4')."""

    capabilities: list[str] | None = Field(
        default=None,
        examples=[
            [
                "intent_recognition",
                "simple_query_handling",
                "routing_to_experts",
            ],
            [
                "phenomenon_clarification",
                "hypothesis_generation",
                "diagnostic_planning",
            ],
            [
                "image_analysis",
                "diagram_analysis",
                "step_by_step_guidance",
            ],
            [
                "document_retrieval",
                "case_search",
                "standard_lookup",
            ],
        ],
        title="Capabilities",
        description="Optional list of specific capabilities this role possesses",
    )
    """List of capabilities this role can perform, as defined in RFC 001 capability section."""


class XenoConfig(Schema):
    """Complete configuration for the Xeno agent system.

    This is the root configuration model for Xeno, containing all 4 roles
    as defined in RFC 001. Each role can be configured with its own
    system prompt, model, and capabilities.

    Attributes:
        version: Configuration version string
        roles: Dictionary mapping role identifiers to their configurations
    """

    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "x-icon": "octicon:organization-16",
            "x-doc-title": "Xeno System Configuration",
        },
    )

    version: str = Field(
        default="1.0.0",
        examples=["1.0.0", "1.1.0"],
        title="Configuration version",
        description="Version string for the configuration format",
    )
    """Configuration version for compatibility tracking."""

    roles: dict[str, XenoRoleConfig] = Field(
        ...,
        examples=[
            {
                "qa": {
                    "type": "qa_assistant",
                    "name": "qa_agent",
                    "description": "Q&A Assistant",
                    "system_prompt": "You are a Q&A assistant.",
                    "model": "openai:gpt-4o",
                },
                "fault": {
                    "type": "fault_expert",
                    "name": "fault_agent",
                    "description": "Fault Expert",
                    "system_prompt": "You are a fault expert.",
                    "model": "openai:gpt-4o",
                },
            },
        ],
        title="Roles",
        description="Dictionary mapping role identifiers to their configurations",
    )
    """All Xeno agent roles configured in the system.

    Keys are role identifiers (e.g., "qa", "fault", "equipment", "material")
    and values are XenoRoleConfig instances.

    RFC 001 defines 4 required roles:
    - `qa_assistant`: Gateway/Front Desk
    - `fault_expert`: Orchestrator/Diagnostician
    - `equipment_expert`: Hybrid Worker+Active
    - `material_assistant`: Worker/Researcher
    """

    def get_role(self, role_id: str) -> XenoRoleConfig | None:
        """Get a role configuration by identifier.

        Args:
            role_id: The role identifier to look up

        Returns:
            The XenoRoleConfig for the specified role, or None if not found
        """
        return self.roles.get(role_id)

    def get_roles_by_type(self, role_type: RoleType | RoleTypeLiteral | str) -> list[XenoRoleConfig]:
        """Get all role configurations of a specific type.

        Args:
            role_type: The RoleType to filter by (enum, string literal, or plain string)

        Returns:
            List of XenoRoleConfig instances matching the specified type
        """
        # Convert to string for comparison
        if isinstance(role_type, RoleType):
            role_type_str = role_type.value
        elif isinstance(role_type, str):
            role_type_str = role_type
        else:
            # It's already a RoleTypeLiteral (string literal)
            role_type_str = role_type
        return [role for role in self.roles.values() if str(role.type) == str(role_type_str)]
