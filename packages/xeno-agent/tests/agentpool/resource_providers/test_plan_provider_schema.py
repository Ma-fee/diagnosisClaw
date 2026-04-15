"""Tests for XenoPlanProvider schema loading."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from agentpool import Agent, AgentContext
from agentpool.delegation import AgentPool
from agentpool.utils.streams import TodoTracker

from xeno_agent.agentpool.resource_providers.plan_provider import XenoPlanProvider


@pytest.fixture
def mock_pool_with_todos() -> AgentPool:
    """Create a mock AgentPool with TodoTracker."""
    pool = AsyncMock(spec=AgentPool)
    pool.todos = TodoTracker()
    return pool


@pytest.fixture
def valid_schema_yaml() -> str:
    """Return a valid YAML schema for update_todo_list."""
    return """
name: update_todo_list
description: Custom description for update_todo_list tool
parameters:
  type: object
  properties:
    todos:
      type: string
      description: XML string with todo tags
    message:
      type: string
      description: Optional message
"""


@pytest.fixture
def valid_schema_json() -> str:
    """Return a valid JSON schema for update_todo_list."""
    return """{
  "name": "update_todo_list",
  "description": "Custom JSON description for update_todo_list tool",
  "parameters": {
    "type": "object",
    "properties": {
      "todos": {
        "type": "string",
        "description": "XML string with todo tags"
      },
      "message": {
        "type": "string",
        "description": "Optional message"
      }
    }
  }
}"""


@pytest.mark.unit
async def test_provider_without_schema_path(mock_pool_with_todos: AgentPool):
    """Test provider initialization without schema path (None)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    provider = XenoPlanProvider(schemas=None)

    # Verify provider created successfully
    assert provider is not None
    assert provider._update_todo_list_schema_override is None

    # Verify tools can be retrieved
    tools = await provider.get_tools()
    assert len(tools) == 1
    assert tools[0].name == "update_todo_list"


@pytest.mark.unit
async def test_provider_with_valid_yaml_schema(valid_schema_yaml: str, mock_pool_with_todos: AgentPool):
    """Test provider initialization with valid YAML schema file."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with schema path
        provider = XenoPlanProvider(schemas={"update_todo_list": schema_path})

        # Verify schema was loaded
        assert provider._update_todo_list_schema_override is not None
        assert provider._update_todo_list_schema_override["name"] == "update_todo_list"
        assert provider._update_todo_list_schema_override["description"] == "Custom description for update_todo_list tool"

        # Verify tool uses schema override
        tools = await provider.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "update_todo_list"

        # Verify the provider still works functionally
        agent = Agent(name="test_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool_with_todos)

        todos_input = """<todo pos="1" status="inProgress">Test task</todo>"""
        result = await provider.update_todo_list(agent_ctx, todos_input)

        assert result.metadata is not None
        assert len(result.metadata["todos"]) == 1
        assert result.metadata["todos"][0]["content"] == "Test task"

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_provider_with_valid_json_schema(valid_schema_json: str, mock_pool_with_todos: AgentPool):
    """Test provider initialization with valid JSON schema file."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_json)
        schema_path = f.name

    try:
        # Create provider with schema path
        provider = XenoPlanProvider(schemas={"update_todo_list": schema_path})

        # Verify schema was loaded
        assert provider._update_todo_list_schema_override is not None
        assert provider._update_todo_list_schema_override["name"] == "update_todo_list"
        assert provider._update_todo_list_schema_override["description"] == "Custom JSON description for update_todo_list tool"

        # Verify tool uses schema override
        tools = await provider.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "update_todo_list"

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
def test_provider_with_nonexistent_schema_path():
    """Test provider initialization fails with nonexistent schema path (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    nonexistent_path = "/path/that/does/not/exist/schema.yaml"

    with pytest.raises(FileNotFoundError, match="Tool schema file not found"):
        XenoPlanProvider(schemas={"update_todo_list": nonexistent_path})


@pytest.mark.unit
def test_provider_with_invalid_yaml_schema():
    """Test provider initialization fails with invalid YAML schema (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    invalid_yaml = """
name: update_todo_list
description: Invalid YAML
  bad_indent: true
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(invalid_yaml)
        schema_path = f.name

    try:
        with pytest.raises(ValueError, match="Failed to parse tool schema file"):
            XenoPlanProvider(schemas={"update_todo_list": schema_path})
    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
def test_provider_with_invalid_json_schema():
    """Test provider initialization fails with invalid JSON schema (Fail Fast)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    invalid_json = """
{
  "name": "update_todo_list",
  "description": "Invalid JSON"
  "missing_comma": true
}
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(invalid_json)
        schema_path = f.name

    try:
        with pytest.raises(ValueError, match="Failed to parse tool schema file"):
            XenoPlanProvider(schemas={"update_todo_list": schema_path})
    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_schema_override_changes_tool_properties(valid_schema_yaml: str):
    """Test that schema override actually changes tool properties."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with custom schema
        provider = XenoPlanProvider(schemas={"update_todo_list": schema_path})

        # Get tools
        tools = await provider.get_tools()
        assert len(tools) == 1

        tool = tools[0]

        # Verify tool has custom name from schema
        assert tool.name == "update_todo_list"

        # Verify tool has custom description from schema
        assert tool.description == "Custom description for update_todo_list tool"

        # Verify schema_override (full schema) is stored in tool
        assert tool.schema_override is not None

        # Verify full schema structure with nested parameters
        assert "name" in tool.schema_override
        assert "description" in tool.schema_override
        assert "parameters" in tool.schema_override
        assert tool.schema_override["parameters"]["type"] == "object"
        assert "properties" in tool.schema_override["parameters"]
        assert "todos" in tool.schema_override["parameters"]["properties"]
        assert "message" in tool.schema_override["parameters"]["properties"]

        # Verify tool.parameters correctly reflects the schema
        params = {p.name: p for p in tool.parameters}
        assert len(params) == 2
        assert "todos" in params
        assert params["todos"].type_info == "string"
        assert params["todos"].description == "XML string with todo tags"
        assert "message" in params
        assert params["message"].type_info == "string"
        assert params["message"].description == "Optional message"

        # Verify final OpenAI schema function block equals full schema_override
        # When schema_override has "name" key (full function), it replaces entire function block
        assert tool.schema["function"] == tool.schema_override

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_default_tool_properties_without_override(mock_pool_with_todos: AgentPool):
    """Test that tools work correctly with default name/description when no override is provided."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    # Create provider without schema path
    provider = XenoPlanProvider(schemas=None)

    # Get tools
    tools = await provider.get_tools()
    assert len(tools) == 1

    tool = tools[0]

    # Verify tool has default name (from function name)
    assert tool.name == "update_todo_list"

    # Verify tool has default description (from function docstring)
    assert "todo" in tool.description.lower()

    # Verify no schema override is set
    assert tool.schema_override is None


@pytest.mark.unit
async def test_multiple_providers_with_different_schemas(valid_schema_yaml: str, valid_schema_json: str):
    """Test creating multiple providers with different schema paths."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_yaml)
        yaml_path = f.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_json)
        json_path = f.name

    try:
        # Create provider with YAML schema
        provider_yaml = XenoPlanProvider(schemas={"update_todo_list": yaml_path})

        # Create provider with JSON schema
        provider_json = XenoPlanProvider(schemas={"update_todo_list": json_path})

        # Verify both have different schemas
        assert provider_yaml._update_todo_list_schema_override is not None
        assert provider_json._update_todo_list_schema_override is not None

        yaml_desc = provider_yaml._update_todo_list_schema_override["description"]
        json_desc = provider_json._update_todo_list_schema_override["description"]

        assert yaml_desc != json_desc
        assert "YAML" not in yaml_desc
        assert "JSON" in json_desc

        # Verify both work independently
        tools_yaml = await provider_yaml.get_tools()
        tools_json = await provider_json.get_tools()

        assert len(tools_yaml) == 1
        assert len(tools_json) == 1

    finally:
        # Clean up
        Path(yaml_path).unlink(missing_ok=True)
        Path(json_path).unlink(missing_ok=True)


@pytest.mark.unit
async def test_tool_execution_with_rfc_parameters(
    valid_schema_yaml: str,
    mock_pool_with_todos: AgentPool,
):
    """Test that update_todo_list tool executes successfully with RFC parameters (todos and optional message)."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(valid_schema_yaml)
        schema_path = f.name

    try:
        # Create provider with RFC schema
        provider = XenoPlanProvider(schemas={"update_todo_list": schema_path})

        # Get agent context

        agent = Agent(name="test_agent", model="test")
        agent_ctx = AgentContext(node=agent, pool=mock_pool_with_todos)

        # Verify tool execution with RFC parameters (todos, message) doesn't raise TypeError
        todos_input = """<todo pos="1" status="inProgress">Test task 1</todo>
<todo pos="2">Test task 2</todo>"""
        result = await provider.update_todo_list(agent_ctx, todos_input, message="Updated todos")

        # Verify result
        assert result.metadata is not None
        assert len(result.metadata["todos"]) == 2
        assert result.metadata["todos"][0]["content"] == "Test task 1"
        assert result.metadata["todos"][1]["content"] == "Test task 2"
        assert "1" in result.content
        assert "Test task 1" in result.content

        # Verify tool execution without optional message parameter
        todos_input_2 = """<todo pos="1" status="completed">Test task 1</todo>"""
        result_2 = await provider.update_todo_list(agent_ctx, todos_input_2)

        assert result_2.metadata is not None
        assert len(result_2.metadata["todos"]) == 2
        assert result_2.metadata["todos"][0]["status"] == "completed"

    finally:
        # Clean up
        Path(schema_path).unlink(missing_ok=True)
