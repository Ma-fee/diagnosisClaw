from unittest.mock import AsyncMock, MagicMock

import pytest

from xeno_agent.agentpool.core.config import RoleType, XenoConfig, XenoRoleConfig
from xeno_agent.agentpool.core.deps import XenoAgentDeps


@pytest.fixture
def mock_config():
    return XenoConfig(
        roles={
            "qa": XenoRoleConfig(
                type=RoleType.QA_ASSISTANT,
                name="qa_agent",
                system_prompt="QA Prompt",
                model="test:model",
            ),
            "fault": XenoRoleConfig(
                type=RoleType.FAULT_EXPERT,
                name="fault_agent",
                system_prompt="Fault Prompt",
                model="test:model",
            ),
        },
    )


@pytest.fixture
def mock_role_config(mock_config):
    return mock_config.roles["qa"]


@pytest.fixture
def deps(mock_config, mock_role_config):
    return XenoAgentDeps(xeno_config=mock_config, role_config=mock_role_config, agent_pool=MagicMock(), storage_manager=AsyncMock(), tool_manager=MagicMock())


def test_properties(deps, mock_config, mock_role_config):
    assert deps.xeno_config == mock_config
    assert deps.role_config == mock_role_config
    assert deps.agent_pool is not None
    assert deps.storage_manager is not None
    assert deps.tool_manager is not None


@pytest.mark.asyncio
async def test_context_manager(deps):
    async with deps as d:
        assert d == deps

    # storage_manager.__aexit__ should be called
    deps.storage_manager.__aexit__.assert_called_once()


def test_get_other_role(deps):
    role = deps.get_other_role("fault")
    assert role is not None
    assert role.name == "fault_agent"

    role = deps.get_other_role("nonexistent")
    assert role is None


def test_get_roles_by_type(deps):
    roles = deps.get_roles_by_type(RoleType.FAULT_EXPERT)
    assert len(roles) == 1
    assert roles[0].name == "fault_agent"


def test_get_agent_context(deps):
    # Currently returns None
    assert deps.get_agent_context() is None

    # Test without pool
    deps._agent_pool = None
    assert deps.get_agent_context() is None
