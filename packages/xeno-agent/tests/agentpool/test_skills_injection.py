"""Tests for skill injection in delegation subagent creation (RFC-0002).

These tests verify that the XenoDelegationProvider correctly handles
the `skills` parameter when creating subagents via the `new_task` tool.

TDD RED Phase: These tests should FAIL until the feature is implemented.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool import Agent, AgentContext
from agentpool.agents.base_agent import BaseAgent
from agentpool.delegation import AgentPool
from agentpool.tools.exceptions import ToolError

from xeno_agent.agentpool.resource_providers.delegation_provider import XenoDelegationProvider


@pytest.fixture
def mock_pool_with_skills() -> AgentPool:
    """Create a mock AgentPool with skills manager."""
    pool = AsyncMock(spec=AgentPool)

    # Create a mock skills manager
    skills_manager = MagicMock()
    pool.skills = skills_manager

    # Create a mock agent in the pool
    mock_agent = MagicMock(spec=BaseAgent)

    # Create an async generator that yields nothing
    async def empty_async_generator():
        yield  # Never actually yields, generator is empty

    # The run_stream method should return an async generator
    mock_agent.run_stream = lambda prompt=None, deps=None: empty_async_generator()

    # Configure pool.nodes to return mock agent
    pool.nodes = {"test_agent": mock_agent}

    return pool


@pytest.fixture
def mock_skill() -> MagicMock:
    """Create a mock skill object."""
    skill = MagicMock()
    skill.name = "git-master"
    skill.description = "Git best practices for operations like commit, rebase, and history"
    skill.skill_path = "/home/user/.claude/skills/git-master/"
    skill.load_instructions.return_value = """# Git Master

When working with Git:
1. Use atomic commits
2. Write descriptive commit messages
3. Rebase before merging"""
    return skill


@pytest.fixture
def mock_skill_python() -> MagicMock:
    """Create another mock skill object for Python."""
    skill = MagicMock()
    skill.name = "python-expert"
    skill.description = "Python best practices and patterns"
    skill.skill_path = "/home/user/.claude/skills/python-expert/"
    skill.load_instructions.return_value = """# Python Expert

When writing Python code:
1. Follow PEP 8
2. Use type hints
3. Write docstrings"""
    return skill


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_task_accepts_skills_parameter(mock_pool_with_skills: AgentPool):
    """Test that new_task accepts the skills parameter without raising TypeError.

        This verifies the basic signature change for RFC-0002, ensuring that
    the skills parameter is accepted even if not yet implemented.
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Test that skills parameter is accepted (should not raise TypeError)
    # If the parameter is not implemented, this will fail with TypeError
    result = await provider.new_task(
        agent_ctx,
        mode="test_agent",
        message="Test task with skills",
        expected_output="Test output",
        load_skills=["git-master"],  # NEW parameter per RFC-0002
    )

    # Verify the call completed without TypeError
    assert result is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skill_resolved_from_manager(
    mock_pool_with_skills: AgentPool,
    mock_skill: MagicMock,
):
    """Test that skills are resolved from the pool's SkillsManager.

    Verifies that the skills parameter triggers a lookup in the pool's
    SkillsManager using get_skill() for each skill name.
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Configure mock to return the skill
    mock_pool_with_skills.skills.get_skill.return_value = mock_skill

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Call new_task with skills
    await provider.new_task(
        agent_ctx,
        mode="test_agent",
        message="Test task with skills",
        expected_output="Test output",
        load_skills=["git-master"],
    )

    # Verify SkillsManager.get_skill was called for the skill
    mock_pool_with_skills.skills.get_skill.assert_called_once_with("git-master")

    # Verify skill.load_instructions was called to get the content
    mock_skill.load_instructions.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_missing_skill_raises_error_strict_mode(mock_pool_with_skills: AgentPool):
    """Test that missing skills raise ToolError in STRICT mode.

        When a skill is specified but not found in the registry, and strict mode
        is enabled (default for RFC-0002), a ToolError should be raised with
    clear messaging about the missing skill and available skills.
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Configure mock to return None (skill not found)
    mock_pool_with_skills.skills.get_skill.return_value = None
    mock_pool_with_skills.skills.list_skills.return_value = ["git-master", "python-expert"]

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Test that missing skill raises ToolError in strict mode
    with pytest.raises(ToolError, match=r"Skill.*not found"):
        await provider.new_task(
            agent_ctx,
            mode="test_agent",
            message="Test task with missing skill",
            expected_output="Test output",
            load_skills=["nonexistent-skill"],
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skills_formatted_as_xml(
    mock_pool_with_skills: AgentPool,
    mock_skill: MagicMock,
):
    """Test that skills are formatted as XML with correct structure.

    Verifies the skill-instruction format per RFC-0002:
    <skill-instruction name="git-master" base=".claude/skills/git-master/">
      # Git Master
      ...
    </skill-instructions>
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Configure mock to return the skill
    mock_pool_with_skills.skills.get_skill.return_value = mock_skill

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Capture the prompt passed to run_stream
    captured_prompt = None

    async def capture_stream(prompt=None, deps=None):
        nonlocal captured_prompt
        captured_prompt = prompt
        return
        yield  # Make it an async generator

    # Replace the agent's run_stream with capture
    mock_pool_with_skills.nodes["test_agent"].run_stream = capture_stream

    # Call new_task with skills
    await provider.new_task(
        agent_ctx,
        mode="test_agent",
        message="Test task",
        expected_output="Test output",
        load_skills=["git-master"],
    )

    # Verify the captured prompt contains XML-formatted skills
    assert captured_prompt is not None
    assert '<skill-instruction name="git-master"' in captured_prompt
    assert f'base="{mock_skill.skill_path}"' in captured_prompt
    assert "</skill-instructions>" in captured_prompt
    assert "# Git Master" in captured_prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_skills_prepended_to_prompt(
    mock_pool_with_skills: AgentPool,
    mock_skill: MagicMock,
):
    """Test that skills XML is prepended before the task in the formatted prompt.

    The expected order is:
    1. <skill-instruction>...</skill-instructions>
    2. <task>...</task>
    3. <expected_output>...</expected_output>
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Configure mock to return the skill
    mock_pool_with_skills.skills.get_skill.return_value = mock_skill

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Capture the prompt passed to run_stream
    captured_prompt = None

    async def capture_stream(prompt=None, deps=None):
        nonlocal captured_prompt
        captured_prompt = prompt
        return
        yield  # Make it an async generator

    # Replace the agent's run_stream with capture
    mock_pool_with_skills.nodes["test_agent"].run_stream = capture_stream

    test_message = "Review this code for git best practices"
    test_expected = "Code review with git suggestions"

    # Call new_task with skills
    await provider.new_task(
        agent_ctx,
        mode="test_agent",
        message=test_message,
        expected_output=test_expected,
        load_skills=["git-master"],
    )

    # Verify the order: skills before task before expected_output
    assert captured_prompt is not None

    skills_pos = captured_prompt.find('<skill-instruction name="git-master"')
    task_pos = captured_prompt.find(f"<task>\n{test_message}")
    expected_pos = captured_prompt.find(f"<expected_output>\n{test_expected}")

    assert skills_pos != -1, "Skills section not found"
    assert task_pos != -1, "Task section not found"
    assert expected_pos != -1, "Expected output section not found"

    # Verify order: skills < task < expected_output
    assert skills_pos < task_pos, "Skills should come before task"
    assert task_pos < expected_pos, "Task should come before expected_output"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_backward_compatibility_no_skills(mock_pool_with_skills: AgentPool):
    """Test that calls without skills parameter still work (backward compatibility).

    Per RFC-0002, the skills parameter is optional. Existing code that
    does not pass skills should continue to work without changes.
    """
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    provider = XenoDelegationProvider(schemas=None)

    # Get agent context
    agent = Agent(name="parent_agent", model="test")
    agent_ctx = AgentContext(node=agent, pool=mock_pool_with_skills)

    # Capture the prompt passed to run_stream
    captured_prompt = None

    async def capture_stream(prompt=None, deps=None):
        nonlocal captured_prompt
        captured_prompt = prompt
        return
        yield  # Make it an async generator

    # Replace the agent's run_stream with capture
    mock_pool_with_skills.nodes["test_agent"].run_stream = capture_stream

    test_message = "Test task without skills"
    test_expected = "Expected output"

    # Call new_task WITHOUT skills parameter (old way)
    result = await provider.new_task(
        agent_ctx,
        mode="test_agent",
        message=test_message,
        expected_output=test_expected,
    )

    # Verify the call completed successfully
    assert result is not None

    # Verify the prompt does NOT contain skills section
    assert captured_prompt is not None
    assert "<skill-instruction" not in captured_prompt

    # Verify the prompt contains task and expected_output in correct format
    assert f"<task>\n{test_message}\n</task>" in captured_prompt
    assert f"<expected_output>\n{test_expected}\n</expected_output>" in captured_prompt
