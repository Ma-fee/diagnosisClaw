"""
Core simulation components for xeno-agent.

This module contains the fundamental building blocks of the simulation system:
- state.py: SimulationState and TaskFrame models
- flow.py: Flow kernel for managing simulation lifecycle
- signals.py: Signal system for agent communication and flow control
- hitl.py: Human-in-the-loop interaction handling
"""

from .flow import XenoSimulationFlow
from .hitl import InteractionHandler, requires_approval
from .signals import (
    AskFollowupSignal,
    CompletionSignal,
    NewTaskSignal,
    SimulationSignal,
    SwitchModeSignal,
    UpdateTodoListSignal,
)
from .state import SimulationState, TaskFrame

__all__ = [
    "AskFollowupSignal",
    "CompletionSignal",
    "InteractionHandler",
    "NewTaskSignal",
    "SimulationSignal",
    "SimulationState",
    "SwitchModeSignal",
    "TaskFrame",
    "UpdateTodoListSignal",
    "XenoSimulationFlow",
    "requires_approval",
]
