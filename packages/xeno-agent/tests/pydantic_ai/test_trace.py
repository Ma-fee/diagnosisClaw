from xeno_agent.pydantic_ai.trace import TraceID


def test_trace_id_generation():
    trace = TraceID.new()
    assert trace.trace_id is not None
    assert trace.span_id is not None
    assert trace.path == []


def test_trace_child_creation():
    parent = TraceID.new()
    child = parent.child("agent_a")

    assert child.trace_id == parent.trace_id
    assert child.parent_id == parent.span_id
    assert child.span_id != parent.span_id
    assert child.path == ["agent_a"]


def test_trace_path_accumulation():
    t1 = TraceID.new()
    t2 = t1.child("agent_a")
    t3 = t2.child("agent_b")

    assert t3.path == ["agent_a", "agent_b"]


def test_trace_cycle_detection():
    t1 = TraceID.new()
    t2 = t1.child("agent_a")
    t3 = t2.child("agent_b")

    # "agent_a" is already in path ["agent_a", "agent_b"]? No, "agent_a" calls "agent_b"
    # Wait, path logic:
    # t1 (root) -> path []
    # t2 (agent_a) -> path ["agent_a"] ? Or path of CALLER?
    # Usually trace context carries "who called me".
    # Let's say path tracks the visited nodes.

    assert t3.has_cycle("agent_a") is True
    assert t3.has_cycle("agent_c") is False
