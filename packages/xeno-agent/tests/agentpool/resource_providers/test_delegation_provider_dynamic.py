"""Tests for XenoDelegationProvider dynamic schema injection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool import Agent, AgentContext
from agentpool.agents.base_agent import BaseAgent
from agentpool.delegation import AgentPool

from xeno_agent.agentpool.resource_providers.delegation_provider import XenoDelegationProvider


@pytest.fixture
def mock_pool_with_agents() -> AgentPool:
    """Create a mock AgentPool with agents."""
    pool = AsyncMock(spec=AgentPool)

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
def mock_pool_with_multiple_agents() -> AgentPool:
    """Create a mock AgentPool with multiple agents."""
    pool = AsyncMock(spec=AgentPool)

    # Create multiple mock agents in the pool
    async def empty_async_generator():
        yield

    agent1 = MagicMock(spec=BaseAgent)
    agent1.run_stream = lambda prompt=None, deps=None: empty_async_generator()

    agent2 = MagicMock(spec=BaseAgent)
    agent2.run_stream = lambda prompt=None, deps=None: empty_async_generator()

    agent3 = MagicMock(spec=BaseAgent)
    agent3.run_stream = lambda prompt=None, deps=None: empty_async_generator()

    # Configure pool.nodes to return multiple mock agents
    pool.nodes = {
        "agent_a": agent1,
        "agent_b": agent2,
        "agent_c": agent3,
    }

    return pool


@pytest.fixture
def valid_new_task_schema_yaml() -> str:
    """Return a valid YAML schema for new_task (matches RFC)."""
    return """
name: new_task
description: Custom description for new_task tool
parameters:
  type: object
  properties:
    mode:
      type: string
      description: The specialized mode for new task. Must be one of available modes.
    message:
      type: string
      description: A clear, concise statement of what task entails.
    expected_output:
      type: string
      description: A precise definition of successful outcome for this sub-task.
  required:
    - mode
    - message
    - expected_output
"""


@pytest.mark.unit
async def test_get_tools_injects_agent_names_into_new_task_schema(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that get_tools() injects agent names into new_task schema when pool is present."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema and pool
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=mock_pool_with_agents,
        )

        # Get tools
        tools = await provider.get_tools()
        assert len(tools) == 2

        # Find new_task tool
        new_task_tool = tools[0]
        assert new_task_tool.name == "new_task"

        # Verify schema_override has been updated with agent names
        schema_override = new_task_tool.schema_override
        assert schema_override is not None

        # Check that mode parameter has enum with agent names
        parameters = schema_override.get("parameters", {})
        properties = parameters.get("properties", {})
        mode_prop = properties.get("mode")

        assert mode_prop is not None
        assert "enum" in mode_prop
        assert mode_prop["enum"] == ["test_agent"]

        # Verify description mentions available agents
        assert "test_agent" in mode_prop["description"]
        assert "Available agents:" in mode_prop["description"]

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_get_tools_injects_multiple_agent_names(
    valid_new_task_schema_yaml: str,
    mock_pool_with_multiple_agents: AgentPool,
):
    """Test that get_tools() injects all agent names from pool into new_task schema."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema and pool with multiple agents
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=mock_pool_with_multiple_agents,
        )

        # Get tools
        tools = await provider.get_tools()
        assert len(tools) == 2

        # Find new_task tool
        new_task_tool = tools[0]
        assert new_task_tool.name == "new_task"

        # Verify all agent names are in the enum
        schema_override = new_task_tool.schema_override
        assert schema_override is not None

        parameters = schema_override.get("parameters", {})
        properties = parameters.get("properties", {})
        mode_prop = properties.get("mode")

        assert mode_prop is not None
        assert mode_prop["enum"] == ["agent_a", "agent_b", "agent_c"]

        # Verify all agents mentioned in description
        description = mode_prop["description"]
        assert "agent_a" in description
        assert "agent_b" in description
        assert "agent_c" in description

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_set_pool_updates_schema_dynamically(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that set_pool() updates schema dynamically on subsequent get_tools() calls."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema but no pool initially
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=None,
        )

        # Get tools without pool - should not have agent names in enum
        tools_without_pool = await provider.get_tools()
        new_task_without_pool = tools_without_pool[0]
        assert new_task_without_pool.name == "new_task"

        # Without pool, mode parameter should not have enum (or have original value)
        schema_without_pool = new_task_without_pool.schema_override
        assert schema_without_pool is not None

        parameters = schema_without_pool.get("parameters", {})
        properties = parameters.get("properties", {})
        mode_prop = properties.get("mode")

        # Without pool, mode shouldn't have enum
        assert mode_prop is not None
        assert "enum" not in mode_prop or mode_prop.get("enum") is None

        # Now set the pool
        provider.set_pool(mock_pool_with_agents)

        # Get tools again with pool - should have agent names
        tools_with_pool = await provider.get_tools()
        new_task_with_pool = tools_with_pool[0]
        assert new_task_with_pool.name == "new_task"

        schema_with_pool = new_task_with_pool.schema_override
        assert schema_with_pool is not None

        parameters = schema_with_pool.get("parameters", {})
        properties = parameters.get("properties", {})
        mode_prop = properties.get("mode")

        # With pool, mode should have enum with agent names
        assert mode_prop is not None
        assert "enum" in mode_prop
        assert mode_prop["enum"] == ["test_agent"]

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_copy_on_read_prevents_original_schema_mutation(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that Copy-on-Read pattern prevents mutation of original tool schema."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema and pool
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=mock_pool_with_agents,
        )

        # Get tools multiple times
        tools_1 = await provider.get_tools()
        tools_2 = await provider.get_tools()

        # Both should have the same agent names in enum
        new_task_1 = tools_1[0]
        new_task_2 = tools_2[0]

        # Both should have schema_override (we provided one)
        assert new_task_1.schema_override is not None
        assert new_task_2.schema_override is not None

        enum_1 = new_task_1.schema_override["parameters"]["properties"]["mode"]["enum"]
        enum_2 = new_task_2.schema_override["parameters"]["properties"]["mode"]["enum"]

        assert enum_1 == enum_2 == ["test_agent"]

        # Modify the first tool's schema_override
        new_task_1.schema_override["parameters"]["properties"]["mode"]["enum"] = ["modified_agent"]

        # The second tool should not be affected
        assert new_task_2.schema_override["parameters"]["properties"]["mode"]["enum"] == ["test_agent"]

        # Get tools again
        tools_3 = await provider.get_tools()
        new_task_3 = tools_3[0]

        # The new tool should have schema_override
        assert new_task_3.schema_override is not None
        assert new_task_3.schema_override["parameters"]["properties"]["mode"]["enum"] == ["test_agent"]

        # Original provider's _new_task_schema_override should not be mutated
        original_schema = provider._new_task_schema_override
        assert original_schema is not None

        mode_prop = original_schema.get("parameters", {}).get("properties", {}).get("mode")
        assert "enum" not in mode_prop or mode_prop.get("enum") is None

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_get_tools_without_pool_fallback(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that new_task fallback to provider pool when context pool is None."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with pool
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=mock_pool_with_agents,
        )

        # Create agent context without pool
        agent = Agent(name="test_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=None)

        # Execute new_task - should use provider's pool
        result = await provider.new_task(
            agent_ctx,
            mode="test_agent",
            task="Test task description",
            expected_output="Expected output",
        )

        # Verify execution succeeded (didn't raise ToolError about missing pool)
        assert result is not None

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_get_tools_without_schema_override(
    mock_pool_with_agents: AgentPool,
):
    """Test that get_tools() works correctly when no schema override is provided."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create provider without schema override
    provider = XenoDelegationProvider(
        schemas=None,
        pool=mock_pool_with_agents,
    )

    # Get tools should still work
    tools = await provider.get_tools()
    assert len(tools) == 2

    # new_task tool should exist
    new_task_tool = tools[0]
    assert new_task_tool.name == "new_task"

    # Without schema_override, tool should be returned as-is
    assert new_task_tool.schema_override is None

    # Verify tool is still functional despite no schema override
    assert new_task_tool.description is not None


@pytest.mark.unit
async def test_get_tools_with_pool_but_no_schema_override(
    mock_pool_with_agents: AgentPool,
):
    """Test that get_tools() handles case where pool exists but no schema override."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create provider without schema override but with pool
    provider = XenoDelegationProvider(
        schemas=None,
        pool=mock_pool_with_agents,
    )

    # Get tools should work
    tools = await provider.get_tools()
    assert len(tools) == 2

    # new_task tool should exist
    new_task_tool = tools[0]
    assert new_task_tool.name == "new_task"

    # Without schema_override, no injection happens
    assert new_task_tool.schema_override is None


@pytest.mark.unit
async def test_pool_replacement_updates_schema(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
    mock_pool_with_multiple_agents: AgentPool,
):
    """Test that replacing the pool updates schema with new agent names."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with single-agent pool
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
            pool=mock_pool_with_agents,
        )

        # Get tools - should have single agent
        tools_1 = await provider.get_tools()
        new_task_1 = tools_1[0]
        assert new_task_1.schema_override is not None
        enum_1 = new_task_1.schema_override["parameters"]["properties"]["mode"]["enum"]
        assert enum_1 == ["test_agent"]

        # Replace pool with multi-agent pool
        provider.set_pool(mock_pool_with_multiple_agents)

        # Get tools - should have multiple agents
        tools_2 = await provider.get_tools()
        new_task_2 = tools_2[0]
        assert new_task_2.schema_override is not None
        enum_2 = new_task_2.schema_override["parameters"]["properties"]["mode"]["enum"]
        assert enum_2 == ["agent_a", "agent_b", "agent_c"]

        # Verify description updated with new agents
        assert new_task_2.schema_override is not None
        description = new_task_2.schema_override["parameters"]["properties"]["mode"]["description"]
        assert "agent_a" in description
        assert "agent_b" in description
        assert "agent_c" in description

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)
