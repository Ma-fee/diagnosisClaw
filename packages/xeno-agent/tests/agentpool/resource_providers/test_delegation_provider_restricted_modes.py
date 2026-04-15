"""Tests for restricted delegation and worker session isolation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool import Agent, AgentContext, ChatMessage
from agentpool.agents.base_agent import BaseAgent
from agentpool.agents.events import StreamCompleteEvent
from agentpool.delegation import AgentPool
from agentpool.tools.exceptions import ToolError
from pydantic_ai.tools import ToolDefinition

from xeno_agent.agentpool.resource_providers.delegation_provider import XenoDelegationProvider


@pytest.fixture
def mock_pool_with_multiple_agents() -> AgentPool:
    """Create a mock pool with parent and two worker agents."""
    pool = AsyncMock(spec=AgentPool)

    def build_agent(name: str) -> MagicMock:
        agent = MagicMock(spec=BaseAgent)
        agent.name = name
        agent.description = f"{name} description"
        return agent

    material_agent = build_agent("material_assistant")
    equipment_agent = build_agent("equipment_expert")

    async def complete_stream(*_args, **_kwargs):
        yield StreamCompleteEvent(message=ChatMessage(content="done", role="assistant"))

    material_agent.run_stream = complete_stream
    equipment_agent.run_stream = complete_stream

    pool.nodes = {
        "fault_expert": build_agent("fault_expert"),
        "material_assistant": material_agent,
        "equipment_expert": equipment_agent,
    }
    return pool


@pytest.mark.unit
@pytest.mark.asyncio
async def test_prepare_new_task_lists_only_allowed_modes(mock_pool_with_multiple_agents: AgentPool):
    """The tool description should expose only allowed target modes."""
    provider = XenoDelegationProvider(
        schemas=None,
        allowed_modes=["material_assistant"],
    )
    parent = Agent(name="fault_expert", model="test")
    ctx = AgentContext(node=parent, pool=mock_pool_with_multiple_agents)
    run_ctx = SimpleNamespace(deps=ctx)
    tool_def = ToolDefinition(
        name="new_task",
        description="delegate",
        parameters_json_schema={"type": "object"},
    )

    prepared = await provider.prepare_new_task(run_ctx, tool_def)

    assert "material_assistant" in prepared.description
    assert "equipment_expert" not in prepared.description
    assert "fault_expert" not in prepared.description


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_task_rejects_disallowed_mode(mock_pool_with_multiple_agents: AgentPool):
    """Delegation should fail fast when target mode is outside the whitelist."""
    provider = XenoDelegationProvider(
        schemas=None,
        allowed_modes=["material_assistant"],
    )
    parent = Agent(name="fault_expert", model="test")
    ctx = AgentContext(node=parent, pool=mock_pool_with_multiple_agents)

    with pytest.raises(ToolError, match="Allowed modes: material_assistant"):
        await provider.new_task(
            ctx,
            mode="equipment_expert",
            message="Need field operation guidance",
            expected_output="Guidance",
            load_skills=[],
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_task_uses_fresh_session_when_enabled(mock_pool_with_multiple_agents: AgentPool):
    """Worker delegation can force a fresh child session instead of reusing worker history."""
    captured_session_id: str | None = None
    captured_input_provider = None

    async def capture_stream(prompt=None, deps=None, session_id=None, input_provider=None):
        nonlocal captured_session_id
        nonlocal captured_input_provider
        captured_session_id = session_id
        captured_input_provider = input_provider
        yield StreamCompleteEvent(message=ChatMessage(content="done", role="assistant"))

    mock_pool_with_multiple_agents.nodes["material_assistant"].run_stream = capture_stream

    provider = XenoDelegationProvider(
        schemas=None,
        allowed_modes=["material_assistant"],
        fresh_session=True,
    )
    parent = Agent(name="fault_expert", model="test")
    parent.session_id = "parent-session"
    input_provider = object()
    ctx = AgentContext(
        node=parent,
        pool=mock_pool_with_multiple_agents,
        input_provider=input_provider,
    )

    await provider.new_task(
        ctx,
        mode="material_assistant",
        message="Retrieve hydraulic specs",
        expected_output="Structured retrieval notes",
        load_skills=[],
    )

    assert captured_session_id is not None
    assert captured_session_id != parent.session_id
    assert captured_input_provider is input_provider


@pytest.mark.unit
@pytest.mark.asyncio
async def test_new_task_returns_failure_result_when_worker_raises(
    mock_pool_with_multiple_agents: AgentPool,
):
    """Worker exceptions should be downgraded into delegation results for parent fallback."""

    async def failing_stream(*_args, **_kwargs):
        raise RuntimeError("search backend unavailable")
        yield  # pragma: no cover

    mock_pool_with_multiple_agents.nodes["material_assistant"].run_stream = failing_stream

    provider = XenoDelegationProvider(
        schemas=None,
        allowed_modes=["material_assistant"],
        fresh_session=True,
    )
    parent = Agent(name="fault_expert", model="test")
    ctx = AgentContext(
        node=parent,
        pool=mock_pool_with_multiple_agents,
        input_provider=object(),
    )

    result = await provider.new_task(
        ctx,
        mode="material_assistant",
        message="Retrieve pump pressure specifications",
        expected_output="Structured retrieval notes",
        load_skills=[],
    )

    assert "DELEGATION_STATUS: FAILED" in result
    assert "AGENT: material_assistant" in result
    assert "search backend unavailable" in result
    assert "Continue with your own domain knowledge" in result
