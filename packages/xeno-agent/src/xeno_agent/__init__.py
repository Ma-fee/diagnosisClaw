"""
Xeno-agent package.

A multi-agent simulation system built on CrewAI for offline task execution.
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

# Removed: from .skills.registry import SkillRegistry, register_builtin_skills

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

__version__ = "0.1.0"
