from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig, MCPServerConfig, ToolConfig


@pytest.mark.asyncio
async def test_agent_creation_with_mcp_servers():
    config_loader = MagicMock()
    config_loader.load_agent_config.return_value = AgentConfig(
        identifier="test-agent",
        role="Tester",
        backstory="Tester",
        when_to_use="Always",
        tools=ToolConfig(
            mcp_servers=[
                "http://localhost:8000/mcp",
                MCPServerConfig(command="python", args=["server.py"], env={"KEY": "VAL"}),
            ],
        ),
    )

    factory = AgentFactory(config_loader, model="test")
    flow_config = FlowConfig(name="Test Flow", description="Test description", entry_agent="test-agent", participants=["test-agent"], global_instructions="Instructions")

    agent = await factory.create("test-agent", flow_config)

    assert len(agent._mcp_servers) == 2
    assert isinstance(agent._mcp_servers[0], MCPServerStreamableHTTP)
    assert agent._mcp_servers[0].url == "http://localhost:8000/mcp"

    assert isinstance(agent._mcp_servers[1], MCPServerStdio)
    assert agent._mcp_servers[1].command == "python"
    assert agent._mcp_servers[1].args == ["server.py"]
    assert agent._mcp_servers[1].env == {"KEY": "VAL"}


@pytest.mark.asyncio
async def test_run_mcp_servers_called():
    config_loader = MagicMock()
    config_loader.load_agent_config.return_value = AgentConfig(
        identifier="test-agent",
        role="Tester",
        backstory="Tester",
        when_to_use="Always",
        tools=ToolConfig(mcp_servers=["http://localhost:8000/mcp"]),
    )

    factory = AgentFactory(config_loader, model="test")
    flow_config = FlowConfig(name="Test Flow", description="Test description", entry_agent="test-agent", participants=["test-agent"], global_instructions="Instructions")

    agent = await factory.create("test-agent", flow_config)

    with patch.object(agent, "run_mcp_servers") as mock_run:
        mock_run.return_value.__aenter__ = AsyncMock()
        mock_run.return_value.__aexit__ = AsyncMock()

        async with agent.run_mcp_servers():
            pass

        mock_run.assert_called_once()
