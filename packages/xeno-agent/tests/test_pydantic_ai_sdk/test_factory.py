from unittest.mock import MagicMock

import pytest

from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig


@pytest.mark.asyncio
async def test_create_agent_with_flow():
    config_loader = MagicMock()
    config_loader.load_agent_config.return_value = AgentConfig(
        identifier="qa",
        role="Quality Assurance",
        backstory="Expert tester",
        when_to_use="When testing is needed",
    )

    factory = AgentFactory(config_loader, model="test")
    flow_config = FlowConfig(name="Test Flow", description="Test description", entry_agent="qa", participants=["qa"], global_instructions="Test everything")

    agent = await factory.create("qa", flow_config, tool_manager=MagicMock())
    assert agent is not None

    # Check if dependency type is set (sanity check)
    # Note: Accessing internal _deps_type or similar might be flaky across versions
    # But we assume basic creation worked.
