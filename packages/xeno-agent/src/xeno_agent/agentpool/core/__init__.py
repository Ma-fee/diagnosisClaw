"""Core configuration and dependencies for xeno-agent."""

from __future__ import annotations

from xeno_agent.agentpool.core.config import (
    RoleType,
    XenoConfig,
    XenoRoleConfig,
)
from xeno_agent.agentpool.core.deps import XenoAgentDeps
from xeno_agent.agentpool.core.routing import (
    ask_followup,
    attempt_completion,
    new_task,
    switch_mode,
    update_todo,
)

__all__ = [
    "RoleType",
    "XenoAgentDeps",
    "XenoConfig",
    "XenoRoleConfig",
    "ask_followup",
    "attempt_completion",
    "new_task",
    "switch_mode",
    "update_todo",
]
