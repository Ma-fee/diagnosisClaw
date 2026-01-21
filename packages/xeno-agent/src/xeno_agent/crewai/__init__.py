"""
CrewAI-based implementation of xeno-agent.

This subpackage contains the CrewAI-specific implementation of the xeno-agent framework.
"""

from .agents import (
    AgentRegistry,
    XenoAgentBuilder,
    load_agent_from_yaml,
)
from .core import (
    AskFollowupSignal,
    CompletionSignal,
    NewTaskSignal,
    SimulationSignal,
    SimulationState,
    SwitchModeSignal,
    TaskFrame,
    UpdateTodoListSignal,
    XenoSimulationFlow,
)
from .llm import create_crewai_llm, get_llm_config, test_connection

__all__ = [
    "AgentRegistry",
    "AskFollowupSignal",
    "CompletionSignal",
    "NewTaskSignal",
    "SimulationSignal",
    "SimulationState",
    "SwitchModeSignal",
    "TaskFrame",
    "UpdateTodoListSignal",
    "XenoAgentBuilder",
    "XenoSimulationFlow",
    "create_crewai_llm",
    "get_llm_config",
    "load_agent_from_yaml",
    "test_connection",
]
