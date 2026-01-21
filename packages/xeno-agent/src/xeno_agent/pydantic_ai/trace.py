import uuid
from dataclasses import dataclass, field


@dataclass
class TraceID:
    trace_id: str
    span_id: str
    parent_id: str | None = None
    path: list[str] = field(default_factory=list)

    @classmethod
    def new(cls) -> "TraceID":
        """Start a new trace."""
        return cls(trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), parent_id=None, path=[])

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
