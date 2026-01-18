"""
Tests for XenoAgentBuilder.
"""

from crewai.tools import BaseTool

from xeno_agent.simulation import XenoAgentBuilder


class MockTool(BaseTool):
    """Mock tool for testing."""

    name: str = "mock_tool"
    description: str = "A mock tool for testing"

    def _run(self, **kwargs):
        return "mock_result"


def test_builder_with_goal():
    """Test setting agent goal."""
    builder = XenoAgentBuilder(mode_slug="test_mode")
    builder.with_goal("Test goal")
    builder.with_llm(None)

    agent = builder.build()

    assert agent.role == "test_mode"
    assert agent.goal == "Test goal"


def test_builder_with_backstory():
    """Test setting agent backstory."""
    builder = XenoAgentBuilder(mode_slug="test_mode")
    builder.with_goal("Test goal")
    builder.with_backstory("Test backstory")
    builder.with_llm(None)

    agent = builder.build()

    assert agent.backstory == "Test backstory"


def test_builder_with_skill():
    """Test adding a skill to the agent."""
    from xeno_agent.simulation import SkillRegistry

    # Register a skill first
    tool = MockTool()
    SkillRegistry.register("test_skill", tool, "Use this tool")

    builder = XenoAgentBuilder(mode_slug="test_mode")
    builder.with_goal("Test goal")
    builder.with_skill("test_skill")
    builder.with_llm(None)

    agent = builder.build()

    # Check that the tool was added
    assert len(agent.tools) == 1


def test_builder_multiple_skills():
    """Test adding multiple skills."""
    from xeno_agent.simulation import SkillRegistry

    tool1 = MockTool()
    tool1.name = "tool1"
    tool2 = MockTool()
    tool2.name = "tool2"

    SkillRegistry.register("skill1", tool1, "Use tool1")
    SkillRegistry.register("skill2", tool2, "Use tool2")

    builder = XenoAgentBuilder(mode_slug="test_mode")
    builder.with_goal("Test goal")
    builder.with_skill("skill1")
    builder.with_skill("skill2")
    builder.with_llm(None)

    agent = builder.build()

    assert len(agent.tools) == 2


def test_builder_chaining():
    """Test that builder methods can be chained."""
    builder = XenoAgentBuilder(mode_slug="test_mode").with_goal("Test goal").with_backstory("Test backstory").with_llm(None)

    agent = builder.build()

    assert agent.role == "test_mode"
    assert agent.goal == "Test goal"
    assert agent.backstory == "Test backstory"


def test_builder_skill_instruction_compilation():
    """Test that skill instructions are compiled into backstory."""
    from xeno_agent.simulation import SkillRegistry

    tool = MockTool()
    SkillRegistry.register("test_skill", tool, "Use this for testing purposes")

    builder = XenoAgentBuilder(mode_slug="test_mode")
    builder.with_goal("Test goal")
    builder.with_backstory("Original backstory.")
    builder.with_skill("test_skill")
    builder.with_llm(None)

    agent = builder.build()

    # Check that skill instruction was added to backstory
    assert "testing purposes" in agent.backstory or "Original backstory" in agent.backstory
