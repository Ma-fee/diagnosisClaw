"""Tests for XenoDelegationProvider schema loading."""

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


@pytest.fixture
def valid_attempt_completion_schema_yaml() -> str:
    """Return a valid YAML schema for attempt_completion."""
    return """
name: attempt_completion
description: Custom description for attempt_completion tool
parameters:
  type: object
  properties:
    result:
      type: string
      description: The result of the task
"""


@pytest.fixture
def valid_new_task_schema_json() -> str:
    """Return a valid JSON schema for new_task (matches RFC)."""
    return """{
  "name": "new_task",
  "description": "Custom JSON description for new_task tool",
  "parameters": {
    "type": "object",
    "properties": {
      "mode": {
        "type": "string",
        "description": "The specialized mode for new task. Must be one of available modes."
      },
      "message": {
        "type": "string",
        "description": "A clear, concise statement of what task entails."
      },
      "expected_output": {
        "type": "string",
        "description": "A precise definition of successful outcome for this sub-task."
      }
    },
    "required": ["mode", "message", "expected_output"]
  }
}"""


@pytest.mark.unit
async def test_provider_without_schema_paths():
    """Test provider initialization without schema paths (None)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    provider = XenoDelegationProvider(
        schemas=None,
    )

    # Verify provider created successfully
    assert provider is not None
    assert provider._new_task_schema_override is None
    assert provider._attempt_completion_schema_override is None

    # Verify tools can be retrieved
    tools = await provider.get_tools()
    assert len(tools) == 2
    assert tools[0].name == "new_task"
    assert tools[1].name == "attempt_completion"


@pytest.mark.unit
async def test_provider_with_valid_new_task_yaml_schema(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test provider initialization with valid YAML schema for new_task."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema path for new_task only
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
        )

        # Verify new_task schema was loaded
        assert provider._new_task_schema_override is not None
        assert provider._new_task_schema_override["name"] == "new_task"
        assert provider._new_task_schema_override["description"] == "Custom description for new_task tool"

        # Verify attempt_completion schema is None
        assert provider._attempt_completion_schema_override is None

        # Verify tools can be retrieved
        tools = await provider.get_tools()
        assert len(tools) == 2

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_provider_with_valid_attempt_completion_yaml_schema(
    valid_attempt_completion_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test provider initialization with valid YAML schema for attempt_completion."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_attempt_completion_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema path for attempt_completion only
        provider = XenoDelegationProvider(
            schemas={"attempt_completion": schema_path},
        )

        # Verify attempt_completion schema was loaded
        assert provider._attempt_completion_schema_override is not None
        assert provider._attempt_completion_schema_override["name"] == "attempt_completion"
        assert provider._attempt_completion_schema_override["description"] == "Custom description for attempt_completion tool"

        # Verify new_task schema is None
        assert provider._new_task_schema_override is None

        # Verify tools can be retrieved
        tools = await provider.get_tools()
        assert len(tools) == 2

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_provider_with_both_valid_yaml_schemas(
    valid_new_task_schema_yaml: str,
    valid_attempt_completion_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test provider initialization with valid YAML schemas for both tools."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        new_task_schema_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_attempt_completion_schema_yaml)
        attempt_completion_schema_path = f.name

    try:
        # Create provider with both schema paths
        provider = XenoDelegationProvider(
            schemas={
                "new_task": new_task_schema_path,
                "attempt_completion": attempt_completion_schema_path,
            },
        )

        # Verify both schemas were loaded
        assert provider._new_task_schema_override is not None
        assert provider._attempt_completion_schema_override is not None

        # Verify new_task schema content
        assert provider._new_task_schema_override["name"] == "new_task"
        assert provider._new_task_schema_override["description"] == "Custom description for new_task tool"

        # Verify attempt_completion schema content
        assert provider._attempt_completion_schema_override["name"] == "attempt_completion"
        assert provider._attempt_completion_schema_override["description"] == "Custom description for attempt_completion tool"

        # Verify tools can be retrieved
        tools = await provider.get_tools()
        assert len(tools) == 2

    finally:
        # Clean up
        Path(new_task_schema_path).unlink(missing_ok=True)
        Path(attempt_completion_schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_provider_with_valid_json_schema(
    valid_new_task_schema_json: str,
    mock_pool_with_agents: AgentPool,
):
    """Test provider initialization with valid JSON schema file."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_json)
        schema_path = f.name

    try:
        # Create provider with JSON schema path
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
        )

        # Verify schema was loaded
        assert provider._new_task_schema_override is not None
        assert provider._new_task_schema_override["name"] == "new_task"
        assert provider._new_task_schema_override["description"] == "Custom JSON description for new_task tool"

        # Verify tools can be retrieved
        tools = await provider.get_tools()
        assert len(tools) == 2

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
def test_provider_with_nonexistent_new_task_schema_path():
    """Test provider initialization fails with nonexistent schema path for new_task (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    nonexistent_path = "/path/that/does/not/exist/schema.yaml"

    with pytest.raises(FileNotFoundError, match="Tool schema file not found"):
        XenoDelegationProvider(
            schemas={"new_task": nonexistent_path},
        )


@pytest.mark.unit
def test_provider_with_nonexistent_attempt_completion_schema_path():
    """Test provider initialization fails with nonexistent schema path for attempt_completion (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    nonexistent_path = "/path/that/does/not/exist/schema.yaml"

    with pytest.raises(FileNotFoundError, match="Tool schema file not found"):
        XenoDelegationProvider(
            schemas={"attempt_completion": nonexistent_path},
        )


@pytest.mark.unit
def test_provider_with_invalid_yaml_schema():
    """Test provider initialization fails with invalid YAML schema (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    invalid_yaml = """
name: new_task
description: Invalid YAML
  bad_indent: true
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(invalid_yaml)
        schema_path = f.name

    try:
        with pytest.raises(ValueError, match="Failed to parse tool schema file"):
            XenoDelegationProvider(
                schemas={"new_task": schema_path},
            )
    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
def test_provider_with_invalid_json_schema():
    """Test provider initialization fails with invalid JSON schema (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    invalid_json = """
{
  "name": "new_task",
  "description": "Invalid JSON"
  "missing_comma": true
}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(invalid_json)
        schema_path = f.name

    try:
        with pytest.raises(ValueError, match="Failed to parse tool schema file"):
            XenoDelegationProvider(
                schemas={"new_task": schema_path},
            )
    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_schema_override_changes_tool_properties(
    valid_new_task_schema_yaml: str,
    valid_attempt_completion_schema_yaml: str,
):
    """Test that schema override actually changes tool properties."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        new_task_schema_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_attempt_completion_schema_yaml)
        attempt_completion_schema_path = f.name

    try:
        # Create provider with custom schemas
        provider = XenoDelegationProvider(
            schemas={
                "new_task": new_task_schema_path,
                "attempt_completion": attempt_completion_schema_path,
            },
        )

        # Get tools
        tools = await provider.get_tools()
        assert len(tools) == 2

        new_task_tool = tools[0]
        attempt_completion_tool = tools[1]

        # Verify tools have custom names from schemas
        assert new_task_tool.name == "new_task"
        assert attempt_completion_tool.name == "attempt_completion"

        # Verify tools have custom descriptions from schemas
        assert new_task_tool.description == "Custom description for new_task tool"
        assert attempt_completion_tool.description == "Custom description for attempt_completion tool"

        # Verify schema_override (full schema) is stored in tools
        assert new_task_tool.schema_override is not None
        assert attempt_completion_tool.schema_override is not None

        # Verify full schema structure with nested parameters
        assert "name" in new_task_tool.schema_override
        assert "description" in new_task_tool.schema_override
        assert "parameters" in new_task_tool.schema_override
        assert new_task_tool.schema_override["parameters"]["type"] == "object"
        assert "properties" in new_task_tool.schema_override["parameters"]
        assert "mode" in new_task_tool.schema_override["parameters"]["properties"]
        assert "message" in new_task_tool.schema_override["parameters"]["properties"]
        assert "expected_output" in new_task_tool.schema_override["parameters"]["properties"]

        assert "name" in attempt_completion_tool.schema_override
        assert "description" in attempt_completion_tool.schema_override
        assert "parameters" in attempt_completion_tool.schema_override
        assert attempt_completion_tool.schema_override["parameters"]["type"] == "object"
        assert "properties" in attempt_completion_tool.schema_override["parameters"]
        assert "result" in attempt_completion_tool.schema_override["parameters"]["properties"]

        # Verify tool.parameters correctly reflects that schema
        new_task_params = {p.name: p for p in new_task_tool.parameters}
        assert len(new_task_params) == 3
        assert "mode" in new_task_params
        assert new_task_params["mode"].type_info == "string"
        assert new_task_params["mode"].description == "The specialized mode for new task. Must be one of available modes."
        assert "message" in new_task_params
        assert new_task_params["message"].type_info == "string"
        assert new_task_params["message"].description == "A clear, concise statement of what task entails."
        assert "expected_output" in new_task_params
        assert new_task_params["expected_output"].type_info == "string"
        assert new_task_params["expected_output"].description == "A precise definition of successful outcome for this sub-task."

        attempt_completion_params = {p.name: p for p in attempt_completion_tool.parameters}
        assert len(attempt_completion_params) == 1
        assert "result" in attempt_completion_params
        assert attempt_completion_params["result"].type_info == "string"
        assert attempt_completion_params["result"].description == "The result of the task"

        # Verify final OpenAI schema function block equals full schema_override
        # When schema_override has "name" key (full function), it replaces entire function block
        assert new_task_tool.schema["function"] == new_task_tool.schema_override
        assert attempt_completion_tool.schema["function"] == attempt_completion_tool.schema_override

    finally:
        # Clean up
        Path(new_task_schema_path).unlink(missing_ok=True)
        Path(attempt_completion_schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_default_tool_properties_without_override(mock_pool_with_agents: AgentPool):
    """Test that tools work correctly with default name/description when no override is provided."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create provider without schema paths
    provider = XenoDelegationProvider(schemas=None)

    # Get tools
    tools = await provider.get_tools()
    assert len(tools) == 2

    new_task_tool = tools[0]
    attempt_completion_tool = tools[1]

    # Verify tools have default names (from function names)
    assert new_task_tool.name == "new_task"
    assert attempt_completion_tool.name == "attempt_completion"

    # Verify tools have default descriptions (from function docstrings)
    assert "delegate" in new_task_tool.description.lower()
    assert "complete" in attempt_completion_tool.description.lower()

    # Verify no schema override is set
    assert new_task_tool.schema_override is None
    assert attempt_completion_tool.schema_override is None


@pytest.mark.unit
async def test_multiple_providers_with_different_schemas(
    valid_new_task_schema_yaml: str,
    valid_new_task_schema_json: str,
):
    """Test creating multiple providers with different schema paths."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        yaml_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_json)
        json_path = f.name

    try:
        # Create provider with YAML schema
        provider_yaml = XenoDelegationProvider(
            schemas={"new_task": yaml_path},
        )

        # Create provider with JSON schema
        provider_json = XenoDelegationProvider(
            schemas={"new_task": json_path},
        )

        # Verify both have different schemas
        assert provider_yaml._new_task_schema_override is not None
        assert provider_json._new_task_schema_override is not None

        yaml_desc = provider_yaml._new_task_schema_override["description"]
        json_desc = provider_json._new_task_schema_override["description"]

        assert yaml_desc != json_desc
        assert "YAML" not in yaml_desc
        assert "JSON" in json_desc

        # Verify both work independently
        tools_yaml = await provider_yaml.get_tools()
        tools_json = await provider_json.get_tools()

        assert len(tools_yaml) == 2
        assert len(tools_json) == 2

    finally:
        # Clean up
        Path(yaml_path).unlink(missing_ok=True)
        Path(json_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_tool_execution_with_rfc_parameters(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that new_task tool executes successfully with RFC parameters (mode and message)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with RFC schema
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
        )

        # Get agent context

        agent = Agent(name="test_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool_with_agents)

        # Verify tool execution with RFC parameters (mode, message) doesn't raise TypeError
        result = await provider.new_task(
            agent_ctx,
            mode="test_agent",
            message="Test task description",
            expected_output="Expected output",
        )

        # Verify result contains expected output format
        assert result is not None

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_tool_execution_with_legacy_parameters(
    valid_new_task_schema_yaml: str,
    mock_pool_with_agents: AgentPool,
):
    """Test that new_task tool still works with legacy parameters (agent_name and task)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_new_task_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with RFC schema
        provider = XenoDelegationProvider(
            schemas={"new_task": schema_path},
        )

        # Get agent context

        agent = Agent(name="test_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool_with_agents)

        # Verify tool execution with legacy parameters (agent_name, task) still works
        result = await provider.new_task(
            agent_ctx,
            agent_name="test_agent",
            task="Test task description",
            expected_output="Expected output",
        )

        # Verify result contains expected output format
        assert result is not None

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)
