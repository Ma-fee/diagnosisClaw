"""
Builtin meta-tools for agent simulation flow control.

These tools implement the core simulation flow primitives:
- switch_mode: Change the current agent mode (GOTO)
- new_task: Start a new subtask with a different agent (GOSUB)
- attempt_completion: Mark the current task as complete (RETURN)
- ask_followup_question: Ask the user a question (HITL)
"""

from .diagnostic_tools import (
    CollectMetricsTool,
    DeepInspectTool,
    QueryKnowledgeBaseTool,
    QueryLogsTool,
)
from .meta_tools import (
    AskFollowupTool,
    AttemptCompletionTool,
    NewTaskTool,
    SwitchModeTool,
)

__all__ = [
    "AskFollowupTool",
    "AttemptCompletionTool",
    "CollectMetricsTool",
    "DeepInspectTool",
    "NewTaskTool",
    "QueryKnowledgeBaseTool",
    "QueryLogsTool",
    "SwitchModeTool",
]
