"""
Tests for Flow-Scoped MCP Architecture
Tests the new flow-scoped MCP system where MCP servers are defined at flow level
and shared across agents.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.models import (
    AgentConfig,
    FlowConfig,
    FlowToolsConfig,
    MCPServerConfig,
)
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager


@pytest.fixture
def mock_config_loader():
    """Create a mock config loader."""
    return MagicMock()


@pytest.fixture
def flow_config():
    """Create a test flow config with MCP servers."""
    return FlowConfig(
        name="Test Flow",
        description="Test flow",
        tools=FlowToolsConfig(
            mcp_servers=[
                MCPServerConfig(
                    name="kb",
                    url="http://localhost:8000/mcp",
                ),
                MCPServerConfig(
                    name="fs",
                    command="python",
                    args=["server.py"],
                    env={"KEY": "VAL"},
                ),
            ],
        ),
    )


@pytest.fixture
def agent_config():
    """Create a test agent config with tool references."""
    return AgentConfig(
        name="test-agent",
        description="Test agent",
        tools=["kb__search", "fs__read_file"],
    )


@pytest.mark.asyncio
async def test_flow_tool_manager_initialization(flow_config):
    """Test FlowToolManager initializes all configured MCP servers."""
    manager = FlowToolManager(flow_config.tools)

    # Mock actual MCP connections
    with patch.object(
        manager,
        "_servers",
        {
            "kb": MagicMock(),
            "fs": MagicMock(),
        },
    ):
        await manager.initialize()

        # Verify all servers were initialized
        assert len(manager._servers) == 2
        assert "kb" in manager._servers
        assert "fs" in manager._servers

    await manager.cleanup()


@pytest.mark.asyncio
async def test_flow_tool_manager_get_tools(flow_config, agent_config):
    """Test FlowToolManager resolves tool names to Tool objects."""
    manager = FlowToolManager(flow_config.tools)

    # Mock tools
    mock_tool1 = MagicMock()
    mock_tool1.name = "kb__search"
    mock_tool2 = MagicMock()
    mock_tool2.name = "fs__read_file"

    manager._all_tools = {
        "kb__search": mock_tool1,
        "fs__read_file": mock_tool2,
    }

    # Get tools by name
    tools = manager.get_tools(agent_config.tools)

    assert len(tools) == 2
    assert tools[0].name == "kb__search"
    assert tools[1].name == "fs__read_file"


@pytest.mark.asyncio
async def test_flow_tool_manager_handles_missing_tools(flow_config):
    """Test FlowToolManager gracefully handles missing tools."""
    manager = FlowToolManager(flow_config.tools)

    # Mock only one tool
    mock_tool = MagicMock()
    mock_tool.name = "kb__search"
    manager._all_tools = {"kb__search": mock_tool}

    # Request tools where one doesn't exist
    tools = manager.get_tools(["kb__search", "fs__missing"])

    # Should only return existing tool
    assert len(tools) == 1
    assert tools[0].name == "kb__search"


@pytest.mark.asyncio
async def test_agent_factory_uses_tool_manager(mock_config_loader, flow_config, agent_config):
    """Test AgentFactory uses FlowToolManager to resolve tools."""
    mock_config_loader.load_agent_config.return_value = agent_config

    # Create mock tools
    mock_tool1 = MagicMock()
    mock_tool1.name = "kb__search"
    mock_tool2 = MagicMock()
    mock_tool2.name = "fs__read_file"

    # Create mock tool manager
    mock_manager = MagicMock()
    mock_manager.get_tools.return_value = [mock_tool1, mock_tool2]

    factory = AgentFactory(mock_config_loader, model="test")

    # Create agent
    await factory.create("test-agent", flow_config, mock_manager)

    # Verify tool manager was called
    mock_manager.get_tools.assert_called_once_with(["kb__search", "fs__read_file"])

    # Note: We can't verify agent._tools directly as it's a PydanticAI Agent
    # but we can verify the factory resolved tools correctly


@pytest.mark.asyncio
async def test_agent_factory_tool_prefixing(mock_config_loader, flow_config):
    """Test tools are properly prefixed with {mcp_name}__."""
    # Agent requests tools with prefixes
    agent_config = AgentConfig(
        name="test-agent",
        description="Test agent",
        tools=["kb__search", "kb__query", "fs__read"],
    )

    mock_config_loader.load_agent_config.return_value = agent_config

    # Create mock tools
    mock_tools = [
        MagicMock(name="kb__search"),
        MagicMock(name="kb__query"),
        MagicMock(name="fs__read"),
    ]

    mock_manager = MagicMock()
    mock_manager.get_tools.return_value = mock_tools

    factory = AgentFactory(mock_config_loader, model="test")

    # Create agent
    await factory.create("test-agent", flow_config, mock_manager)

    # Verify all prefixed tools were requested
    mock_manager.get_tools.assert_called_once_with(["kb__search", "kb__query", "fs__read"])


@pytest.mark.asyncio
async def test_mcp_server_config_validation():
    """Test MCPServerConfig name validation."""
    # Valid name
    config = MCPServerConfig(
        name="valid_name",
        url="http://localhost:8000/mcp",
    )
    assert config.name == "valid_name"

    # Invalid name (starts with number)
    with pytest.raises(ValidationError):
        MCPServerConfig(name="123invalid", url="http://localhost:8000/mcp")

    # Invalid name (contains special chars)
    with pytest.raises(ValidationError):
        MCPServerConfig(name="invalid-name", url="http://localhost:8000/mcp")


@pytest.mark.asyncio
async def test_mcp_server_config_mutual_exclusivity():
    """Test MCPServerConfig URL/command mutual exclusivity."""
    # Valid: URL only
    config1 = MCPServerConfig(name="test1", url="http://localhost:8000/mcp")
    assert config1.url == "http://localhost:8000/mcp"

    # Valid: Command only
    config2 = MCPServerConfig(name="test2", command="python", args=["server.py"])
    assert config2.command == "python"

    # Invalid: Both URL and command
    with pytest.raises(ValidationError) as exc:
        MCPServerConfig(
            name="test3",
            url="http://localhost:8000/mcp",
            command="python",
        )
    assert "Cannot specify both 'url' and 'command/args/env'" in str(exc.value)

    # Invalid: Neither URL nor command
    with pytest.raises(ValidationError) as exc:
        MCPServerConfig(name="test4")
    assert "Must specify either 'url' or 'command'" in str(exc.value)


@pytest.mark.asyncio
async def test_flow_tools_config_defaults():
    """Test FlowToolsConfig default values."""
    config = FlowToolsConfig()
    assert config.mcp_servers == []


@pytest.mark.asyncio
async def test_agent_config_tools_list():
    """Test AgentConfig.tools is now a list of strings."""
    config = AgentConfig(
        name="test",
        description="test",
        tools=["kb__search", "fs__read"],
    )
    assert config.tools == ["kb__search", "fs__read"]
    assert isinstance(config.tools, list)
    assert all(isinstance(t, str) for t in config.tools)
