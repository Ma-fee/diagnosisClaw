"""
Tests for SkillRegistry.
"""

import pytest
from crewai.tools import BaseTool

from xeno_agent.simulation import SkillRegistry


class MockTool(BaseTool):
    """Mock tool for testing."""

    name: str = "mock_tool"
    description: str = "A mock tool for testing"

    def _run(self, **kwargs):
        return "mock_result"


def test_skill_registry_register():
    """Test registering a skill."""
    tool = MockTool()
    instruction = "Use this tool to do X"

    SkillRegistry.register("mock_skill", tool, instruction)

    retrieved_tool, retrieved_instruction = SkillRegistry.get("mock_skill")

    assert retrieved_tool is tool
    assert retrieved_instruction == instruction


def test_skill_registry_get_nonexistent():
    """Test getting a non-existent skill raises error."""
    with pytest.raises(ValueError) as exc_info:
        SkillRegistry.get("nonexistent")

    assert "nonexistent" in str(exc_info.value)


def test_skill_registry_list_skills():
    """Test listing all registered skills."""
    tool1 = MockTool()
    tool2 = MockTool()
    tool1.name = "tool1"
    tool1.description = "Description 1"
    tool2.name = "tool2"
    tool2.description = "Description 2"

    SkillRegistry.register("skill1", tool1, "Instruction 1")
    SkillRegistry.register("skill2", tool2, "Instruction 2")

    skills = SkillRegistry.list_skills()

    assert "skill1" in skills
    assert "skill2" in skills
    assert skills["skill1"] == "Description 1"


def test_skill_registry_clear():
    """Test clearing the registry."""
    tool = MockTool()
    SkillRegistry.register("temp_skill", tool, "Instruction")

    # Verify it's registered
    assert "temp_skill" in SkillRegistry._skills

    # Clear
    SkillRegistry.clear()

    # Verify it's gone
    assert len(SkillRegistry._skills) == 0


def test_skill_registry_isolation():
    """Test that registry is a class-level singleton."""
    tool = MockTool()

    # Register via class
    SkillRegistry.register("test", tool, "instruction")

    # Access via class
    tool_from_registry, _ = SkillRegistry.get("test")

    assert tool_from_registry is tool
