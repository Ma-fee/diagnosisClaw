import pytest

from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime, RuntimeDeps
from xeno_agent.pydantic_ai.trace import TraceID


def test_trace_id_new_generates_uuid():
    trace = TraceID.new()
    assert isinstance(trace.trace_id, str)
    assert len(trace.trace_id) == 36


def test_trace_id_continuity():
    root_id = "session-root-123"
    trace1 = TraceID.new()
    trace2 = TraceID.new(root_trace_id=root_id)

    assert trace1.trace_id != root_id
    assert trace2.trace_id == root_id
    assert trace1.span_id != trace2.span_id
    assert trace1.parent_id is None
    assert trace2.parent_id is None
