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
    InteractionHandler,
    NewTaskSignal,
    SimulationSignal,
    SimulationState,
    SwitchModeSignal,
    TaskFrame,
    UpdateTodoListSignal,
    XenoSimulationFlow,
    requires_approval,
)
from .llm import create_crewai_llm, get_llm_config, test_connection
from .skills.registry import SkillRegistry, register_builtin_skills

__all__ = [
    "AgentRegistry",
    "AskFollowupSignal",
    "CompletionSignal",
    "InteractionHandler",
    "NewTaskSignal",
    "SimulationSignal",
    "SimulationState",
    "SkillRegistry",
    "SwitchModeSignal",
    "TaskFrame",
    "UpdateTodoListSignal",
    "XenoAgentBuilder",
    "XenoSimulationFlow",
    "create_crewai_llm",
    "get_llm_config",
    "load_agent_from_yaml",
    "register_builtin_skills",
    "requires_approval",
    "test_connection",
]

__version__ = "0.1.0"
