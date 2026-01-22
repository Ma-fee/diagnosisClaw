import uuid
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class TraceID:
    trace_id: str
    span_id: str
    parent_id: str | None = None
    path: list[str] = field(default_factory=list)

    @classmethod
    def new(cls, root_trace_id: Optional[str] = None) -> "TraceID":
        """Start a new trace (optionally continuing an existing session)."""
        trace_id = root_trace_id if root_trace_id is not None else str(uuid.uuid4())
        return cls(trace_id=trace_id, span_id=str(uuid.uuid4()), parent_id=None, path=[])

    def child(self, current_agent: str) -> "TraceID":
        """Create a child trace for a new span."""
        return TraceID(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_id=self.span_id,
            path=[*self.path, current_agent],
        )

    def has_cycle(self, target_agent: str) -> bool:
        """Check if target_agent is already in the call path."""
        return target_agent in self.path
