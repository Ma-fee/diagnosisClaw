"""
Tests for AgentRegistry and agent loading.
"""

import pytest
from crewai.tools import BaseTool

from xeno_agent.simulation import AgentRegistry, get_agent, register_builtin_skills


class MockTool(BaseTool):
    """Mock tool for testing."""

    name: str = "mock_tool"
    description: str = "A mock tool for testing"

    def _run(self, **kwargs):
        return "mock_result"


def test_agent_registry_register():
    """Test registering an agent."""
    mode_slug = "test_mode"

    def creator(llm=None):
        return {"role": mode_slug}

    AgentRegistry.register(mode_slug, creator)

    assert mode_slug in AgentRegistry._agents


def test_get_agent():
    """Test retrieving an agent from registry."""
    mode_slug = "test_mode"

    def creator(llm=None):
        return {"role": mode_slug}

    AgentRegistry.register(mode_slug, creator)

    agent = get_agent(mode_slug, llm=None)

    assert agent["role"] == mode_slug


def test_get_agent_not_found():
    """Test getting a non-existent agent raises error."""
    with pytest.raises(ValueError) as exc_info:
        get_agent("nonexistent_mode")

    assert "nonexistent_mode" in str(exc_info.value)


def test_register_builtin_skills():
    """Test registering built-in meta tools."""
    from xeno_agent.simulation import SkillRegistry

    # Clear first
    SkillRegistry.clear()

    register_builtin_skills()

    # Check that built-in skills are registered
    skills = SkillRegistry.list_skills()
    assert "switch_mode" in skills
    assert "new_task" in skills
    assert "attempt_completion" in skills
    assert "ask_followup_question" in skills


def test_load_agent_from_yaml(tmp_path):
    """Test loading agent from YAML file."""
    yaml_content = """
role: "Test Agent"
goal: "Test goal"
backstory: "Test backstory"
skills:
  - switch_mode
"""

    agent_file = tmp_path / "test_agent.yaml"
    agent_file.write_text(yaml_content)

    from xeno_agent.simulation import SkillRegistry, load_agent_from_yaml

    SkillRegistry.clear()
    register_builtin_skills()

    # Load the agent
    load_agent_from_yaml(str(agent_file), llm=None)

    # Verify it's registered
    agent = get_agent("test")

    assert agent.role == "Test Agent"


def test_load_multiple_agents_from_directory(tmp_path):
    """Test loading multiple agents from a directory."""
    agent1 = """
role: "Agent 1"
goal: "Goal 1"
backstory: "Backstory 1"
skills:
  - switch_mode
"""

    agent2 = """
role: "Agent 2"
goal: "Goal 2"
backstory: "Backstory 2"
skills:
  - new_task
"""

    (tmp_path / "agent1.yaml").write_text(agent1)
    (tmp_path / "agent2.yaml").write_text(agent2)

    from xeno_agent.simulation import SkillRegistry

    SkillRegistry.clear()
    register_builtin_skills()

    # Load both
    from xeno_agent.simulation import load_agent_from_yaml

    load_agent_from_yaml(str(tmp_path / "agent1.yaml"), llm=None)
    load_agent_from_yaml(str(tmp_path / "agent2.yaml"), llm=None)

    # Verify both are registered
    agent1_obj = get_agent("agent1")
    agent2_obj = get_agent("agent2")

    assert agent1_obj.role == "Agent 1"
    assert agent2_obj.role == "Agent 2"
