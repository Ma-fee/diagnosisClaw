"""Integration tests for skills delegation functionality."""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool import Agent, AgentContext, ChatMessage
from agentpool.agents.base_agent import BaseAgent
from agentpool.agents.events import StreamCompleteEvent
from agentpool.delegation import AgentPool
from agentpool.skills import SkillsManager
from agentpool.tools.exceptions import ToolError

from xeno_agent.agentpool.resource_providers.delegation_provider import XenoDelegationProvider


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create a temporary skills directory with test skills."""
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)

    # Create test-git skill
    test_git_dir = skills_dir / "test-git"
    test_git_dir.mkdir()
    (test_git_dir / "SKILL.md").write_text("""---
name: test-git
description: Test Git best practices skill
---

# Test Git Skill

This is a test skill for git operations.

## Guidelines
- Always use atomic commits
- Write meaningful commit messages
""")

    # Create test-python skill
    test_python_dir = skills_dir / "test-python"
    test_python_dir.mkdir()
    (test_python_dir / "SKILL.md").write_text("""---
name: test-python
description: Test Python coding skill
---

# Test Python Skill

This is a test skill for Python development.

## Guidelines
- Follow PEP 8
- Use type hints where appropriate
""")

    return skills_dir


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_skill_injection(temp_skills_dir, tmp_path):
    """Test that real skills are properly injected into subagent prompts."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create SkillsManager with temp directory
    skills_manager = SkillsManager(skills_dirs=[temp_skills_dir])
    await skills_manager.__aenter__()

    try:
        # Create mock pool with real skills manager
        mock_pool = AsyncMock(spec=AgentPool)
        mock_pool.skills = skills_manager

        # Create a mock agent in the pool
        mock_agent = MagicMock(spec=BaseAgent)

        # Capture the prompt passed to run_stream
        captured_prompt = None

        async def capture_stream(prompt=None, deps=None):
            nonlocal captured_prompt
            captured_prompt = prompt
            yield StreamCompleteEvent(message=ChatMessage(content="Done", role="assistant"))

        mock_agent.run_stream = capture_stream
        mock_pool.nodes = {"test_agent": mock_agent}

        # Create provider and context
        provider = XenoDelegationProvider(schemas=None)
        agent = Agent(name="parent_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool)

        # Call new_task with skills (result not needed for this test)
        _ = await provider.new_task(
            agent_ctx,
            mode="test_agent",
            message="Test the skills injection",
            expected_output="Confirmation that skills were injected",
            skills=["test-git", "test-python"],
        )

        # Verify the prompt contains skills XML
        assert captured_prompt is not None
        assert "<available-skills>" in captured_prompt
        assert '<skill name="test-git"' in captured_prompt
        assert '<skill name="test-python"' in captured_prompt
        assert "<description>Test Git best practices skill</description>" in captured_prompt
        assert "<description>Test Python coding skill</description>" in captured_prompt
        assert "<instructions>" in captured_prompt
        assert "<task>" in captured_prompt
        assert "<expected_output>" in captured_prompt

        # Verify skills come before task
        skills_pos = captured_prompt.find("<available-skills>")
        task_pos = captured_prompt.find("<task>")
        assert skills_pos < task_pos, "Skills should come before task in prompt"

    finally:
        await skills_manager.__aexit__(None, None, None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_skill_missing_strict_mode(temp_skills_dir):
    """Test that missing skills raise ToolError in strict mode."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create SkillsManager with temp directory
    skills_manager = SkillsManager(skills_dirs=[temp_skills_dir])
    await skills_manager.__aenter__()

    try:
        # Create mock pool with real skills manager
        mock_pool = AsyncMock(spec=AgentPool)
        mock_pool.skills = skills_manager
        mock_pool.nodes = {"test_agent": MagicMock(spec=BaseAgent)}

        # Create provider and context
        provider = XenoDelegationProvider(schemas=None)
        agent = Agent(name="parent_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool)

        # Attempt to use non-existent skill
        with pytest.raises(ToolError, match="Item not found: nonexistent-skill"):
            await provider.new_task(
                agent_ctx,
                mode="test_agent",
                message="Test with missing skill",
                expected_output="Should fail",
                skills=["nonexistent-skill"],
            )

    finally:
        await skills_manager.__aexit__(None, None, None)
