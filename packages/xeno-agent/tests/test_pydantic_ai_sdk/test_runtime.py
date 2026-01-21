from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from xeno_agent.pydantic_ai.interfaces import AgentResult
from xeno_agent.pydantic_ai.runtime import delegate_task
from xeno_agent.pydantic_ai.trace import TraceID


# Mock Deps Structure
class MockConfig:
    def __init__(self, allow_delegation_to=None):
        self.allow_delegation_to = allow_delegation_to or []


class MockDeps:
    def __init__(self, config=None, trace=None, factory=None):
        self.config = config or MockConfig()
        self.trace = trace or TraceID.new()
        self.factory = factory

    def child(self, target):
        return MockDeps(config=self.config, trace=self.trace.child(target), factory=self.factory)


@pytest.mark.asyncio
async def test_delegate_task_permission_denied():
    # Setup
    deps = MockDeps(config=MockConfig(allow_delegation_to=["agent_b"]))
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    # Act & Assert
    with pytest.raises(PermissionError, match="Delegation to agent_c not allowed"):
        await delegate_task(ctx, "agent_c", "task")


@pytest.mark.asyncio
async def test_delegate_task_cycle_detection():
    # Setup: Trace path is already ["agent_a", "agent_b"]
    trace = TraceID.new().child("agent_a").child("agent_b")
    deps = MockDeps(config=MockConfig(allow_delegation_to=["agent_a"]), trace=trace)
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

    deps = MockDeps(config=MockConfig(allow_delegation_to=["next_agent"]), trace=trace)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    # Act & Assert
    with pytest.raises(RecursionError, match="Max delegation depth exceeded"):
        await delegate_task(ctx, "next_agent", "task")


@pytest.mark.asyncio
async def test_delegate_task_success():
    # Setup
    mock_agent = AsyncMock()
    mock_agent.run.return_value = AgentResult(data="Success", metadata={})

    mock_factory = MagicMock()
    mock_factory.load.return_value = mock_agent

    deps = MockDeps(config=MockConfig(allow_delegation_to=["agent_b"]), factory=mock_factory)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    ctx.usage = MagicMock()

    # Act
    result = await delegate_task(ctx, "agent_b", "do something")

    # Assert
    assert result == "Success"
    mock_factory.load.assert_called_with("agent_b")
    mock_agent.run.assert_called_once()
    # Check that child deps were passed
    call_kwargs = mock_agent.run.call_args.kwargs
    assert "deps" in call_kwargs
    assert call_kwargs["deps"].trace.path == ["agent_b"]  # Assuming root was empty
