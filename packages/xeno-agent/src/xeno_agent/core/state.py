from typing import Any

from pydantic import BaseModel, Field


class TaskFrame(BaseModel):
    """Represents a stack frame for a task execution context."""

    mode_slug: str = Field(..., description="The agent role/mode for this frame")
    task_id: str = Field(..., description="Unique identifier for this task")
    trigger_message: str = Field(..., description="The prompt/instruction for this specific frame")
    caller_mode: str | None = Field(None, description="The mode that called this task (for RETURN)")
    is_isolated: bool = Field(False, description="Whether this task has isolated context (no conversation history)")
    result: str | None = Field(None, description="The result of this task execution")


class SimulationState(BaseModel):
    """
    The complete state of the simulation managed by the Flow.
    Implements a call-stack like structure for task delegation and mode switching.
    """

    id: str = Field(default="xeno_simulation_state", description="State identifier for CrewAI Flow persistence")
    stack: list[TaskFrame] = Field(default_factory=list, description="The call stack of active tasks")
    conversation_history: list[dict[str, str]] = Field(default_factory=list, description="Full conversation history (for non-isolated frames)")
    final_output: str | None = Field(None, description="Final result when simulation completes")
    is_terminated: bool = Field(False, description="Whether the simulation has terminated")
    last_signal: Any = Field(None, description="The last signal raised by an agent tool")
