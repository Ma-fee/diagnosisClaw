"""Tests for Xeno configuration models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from xeno_agent.agentpool.core.config import (
    RoleType,
    XenoConfig,
    XenoRoleConfig,
)


def test_qa_assistant_role_config():
    """Test Q&A Assistant role configuration model."""
    config = XenoRoleConfig(
        type=RoleType.QA_ASSISTANT,
        name="qa_agent",
        description="Q&A Assistant for user query handling",
        system_prompt="You are a helpful Q&A assistant.",
        model="openai:gpt-4o",
    )

    assert config.type == RoleType.QA_ASSISTANT
    assert config.name == "qa_agent"
    assert config.system_prompt == "You are a helpful Q&A assistant."
    assert config.model == "openai:gpt-4o"


def test_fault_expert_role_config():
    """Test Fault Expert role configuration model."""
    config = XenoRoleConfig(
        type=RoleType.FAULT_EXPERT,
        name="fault_agent",
        description="Fault Expert for diagnosis",
        system_prompt="You are a fault diagnosis expert.",
        model="openai:gpt-4o",
    )

    assert config.type == RoleType.FAULT_EXPERT
    assert config.name == "fault_agent"


def test_equipment_expert_role_config():
    """Test Equipment Expert role configuration model."""
    config = XenoRoleConfig(
        type=RoleType.EQUIPMENT_EXPERT,
        name="equipment_agent",
        description="Equipment Expert for device guidance",
        system_prompt="You are an equipment expert.",
        model="openai:gpt-4o",
    )

    assert config.type == RoleType.EQUIPMENT_EXPERT
    assert config.name == "equipment_agent"


def test_material_assistant_role_config():
    """Test Material Assistant role configuration model."""
    config = XenoRoleConfig(
        type=RoleType.MATERIAL_ASSISTANT,
        name="material_agent",
        description="Material Assistant for document retrieval",
        system_prompt="You are a material research assistant.",
        model="openai:gpt-4o",
    )

    assert config.type == RoleType.MATERIAL_ASSISTANT
    assert config.name == "material_agent"


def test_xeno_config_full():
    """Test complete Xeno configuration with all 4 roles."""
    config = XenoConfig(
        version="1.0.0",
        roles={
            "qa": XenoRoleConfig(
                type=RoleType.QA_ASSISTANT,
                name="qa_agent",
                description="Q&A Assistant",
                system_prompt="You are a Q&A assistant.",
                model="openai:gpt-4o",
            ),
            "fault": XenoRoleConfig(
                type=RoleType.FAULT_EXPERT,
                name="fault_agent",
                description="Fault Expert",
                system_prompt="You are a fault expert.",
                model="openai:gpt-4o",
            ),
            "equipment": XenoRoleConfig(
                type=RoleType.EQUIPMENT_EXPERT,
                name="equipment_agent",
                description="Equipment Expert",
                system_prompt="You are an equipment expert.",
                model="openai:gpt-4o",
            ),
            "material": XenoRoleConfig(
                type=RoleType.MATERIAL_ASSISTANT,
                name="material_agent",
                description="Material Assistant",
                system_prompt="You are a material assistant.",
                model="openai:gpt-4o",
            ),
        },
    )

    assert config.version == "1.0.0"
    assert len(config.roles) == 4
    assert "qa" in config.roles
    assert "fault" in config.roles
    assert "equipment" in config.roles
    assert "material" in config.roles


def test_role_config_with_optional_fields():
    """Test role config with optional fields."""
    config = XenoRoleConfig(
        type=RoleType.QA_ASSISTANT,
        name="qa_agent",
        system_prompt="You are a Q&A assistant.",
        model="openai:gpt-4o",
    )

    # Optional fields should default to None
    assert config.description is None
    assert config.capabilities is None


def test_role_config_with_capabilities():
    """Test role config with capabilities list."""
    config = XenoRoleConfig(
        type=RoleType.QA_ASSISTANT,
        name="qa_agent",
        system_prompt="You are a Q&A assistant.",
        model="openai:gpt-4o",
        capabilities=[
            "intent_recognition",
            "simple_query_handling",
            "routing_to_experts",
        ],
    )

    assert config.capabilities == [
        "intent_recognition",
        "simple_query_handling",
        "routing_to_experts",
    ]


def test_xeno_config_from_dict():
    """Test creating Xeno config from dictionary."""
    config_dict = {
        "version": "1.0.0",
        "roles": {
            "qa": {
                "type": "qa_assistant",
                "name": "qa_agent",
                "description": "Q&A Assistant",
                "system_prompt": "You are a Q&A assistant.",
                "model": "openai:gpt-4o",
            },
        },
    }

    config = XenoConfig(**config_dict)

    assert config.version == "1.0.0"
    assert "qa" in config.roles
    assert config.roles["qa"].type == "qa_assistant"


def test_invalid_role_type():
    """Test that invalid role type raises ValidationError."""
    with pytest.raises(ValidationError):
        XenoRoleConfig(
            type="invalid_role",  # type: ignore[arg-type]
            name="agent",
            system_prompt="You are an assistant.",
            model="openai:gpt-4o",
        )


def test_required_fields_validation():
    """Test that required fields are validated."""
    # Missing required 'name' field
    with pytest.raises(ValidationError):
        XenoRoleConfig(
            type=RoleType.QA_ASSISTANT,
            system_prompt="You are an assistant.",
            model="openai:gpt-4o",
        )


def test_role_type_enum():
    """Test RoleType enum values."""
    assert RoleType.QA_ASSISTANT == "qa_assistant"
    assert RoleType.FAULT_EXPERT == "fault_expert"
    assert RoleType.EQUIPMENT_EXPERT == "equipment_expert"
    assert RoleType.MATERIAL_ASSISTANT == "material_assistant"


def test_config_immutability():
    """Test that config is frozen (immutable)."""
    config = XenoRoleConfig(
        type=RoleType.QA_ASSISTANT,
        name="qa_agent",
        system_prompt="You are a Q&A assistant.",
        model="openai:gpt-4o",
    )

    with pytest.raises(ValidationError):
        config.name = "new_name"  # type: ignore
