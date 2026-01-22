from unittest.mock import AsyncMock, MagicMock
from contextlib import asynccontextmanager

import pytest
from pydantic_ai import RunContext

from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.runtime import delegate_task
from xeno_agent.pydantic_ai.trace import TraceID


@asynccontextmanager
async def null_mcp_servers(*args, **kwargs):
    yield


# Mock Deps Structure
class MockDeps:
    def __init__(self, flow=None, trace=None, factory=None, message_history=None, session_id=None):
        self.flow = flow or FlowConfig(
            name="Test",
            description="Test",
            entry_agent="a",
            participants=["a"],
            global_instructions="",
            delegation_rules={},
        )
        self.trace = trace or TraceID.new()
        self.factory = factory
        self.message_history = message_history or []
        self.session_id = session_id

    def child(self, target):
        return MockDeps(flow=self.flow, trace=self.trace.child(target), factory=self.factory, message_history=self.message_history, session_id=self.session_id)


@pytest.mark.asyncio
async def test_delegate_task_permission_denied():
    # Setup
    flow = FlowConfig(
        name="Test",
        description="Test",
        entry_agent="agent_a",
        participants=["agent_a", "agent_b", "agent_c"],
        global_instructions="",
        delegation_rules={"agent_a": {"allow_delegation_to": ["agent_b"]}},
    )
    # Current agent is agent_a
    trace = TraceID.new().child("agent_a")
    deps = MockDeps(flow=flow, trace=trace)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    # Act & Assert
    with pytest.raises(PermissionError, match="Delegation from agent_a to agent_c not allowed"):
        await delegate_task(ctx, "agent_c", "task")


@pytest.mark.asyncio
async def test_delegate_task_cycle_detection():
    # Setup: Trace path is already ["agent_a", "agent_b"]
    trace = TraceID.new().child("agent_a").child("agent_b")
    flow = FlowConfig(
        name="Test",
        description="Test",
        entry_agent="agent_a",
        participants=["agent_a", "agent_b"],
        global_instructions="",
        delegation_rules={"agent_b": {"allow_delegation_to": ["agent_a"]}},
    )
    deps = MockDeps(flow=flow, trace=trace)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    # Act & Assert: Agent B tries to call Agent A
    with pytest.raises(RecursionError, match="Cycle detected"):
        await delegate_task(ctx, "agent_a", "task")


@pytest.mark.asyncio
async def test_delegate_task_max_depth_exceeded():
    # Setup: Create a deep trace
    trace = TraceID.new()
    for i in range(6):  # Depth 6 > Default 5
        trace = trace.child(f"agent_{i}")

    deps = MockDeps(trace=trace)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    # Act & Assert
    with pytest.raises(RecursionError, match="Max delegation depth exceeded"):
        await delegate_task(ctx, "next_agent", "task")


@pytest.mark.asyncio
async def test_delegate_task_success():
    # Setup
    mock_agent = AsyncMock()
    # PydanticAI Agent.run returns a result object with .data
    result_mock = MagicMock()
    result_mock.data = "Success"
    mock_agent.run.return_value = result_mock
    mock_agent.run_mcp_servers = null_mcp_servers  # Mock async context manager

    mock_factory = MagicMock()
    mock_factory.create = AsyncMock(return_value=mock_agent)  # Must be AsyncMock for await

    flow = FlowConfig(
        name="Test",
        description="Test",
        entry_agent="agent_a",
        participants=["agent_a", "agent_b"],
        global_instructions="",
        delegation_rules={"agent_a": {"allow_delegation_to": ["agent_b"]}},
    )
    trace = TraceID.new().child("agent_a")
    deps = MockDeps(flow=flow, trace=trace, factory=mock_factory)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    ctx.usage = MagicMock()

    # Act
    result = await delegate_task(ctx, "agent_b", "do something")

    # Assert
    assert result == "Success"
    mock_factory.create.assert_called_with("agent_b", flow)
    mock_agent.run.assert_called_once()
    # Check that child deps were passed
    call_kwargs = mock_agent.run.call_args.kwargs
    assert "deps" in call_kwargs
    assert call_kwargs["deps"].trace.path == ["agent_a", "agent_b"]
