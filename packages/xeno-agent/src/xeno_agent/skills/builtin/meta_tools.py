from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ...core.hitl import requires_approval
from ...core.signals import AskFollowupSignal, CompletionSignal, NewTaskSignal, SwitchModeSignal


class SwitchModeTool(BaseTool):
    name: str = "switch_mode"
    description: str = "Switch to a different agent role."

    class Input(BaseModel):
        mode_slug: str = Field(..., description="The slug of the mode to switch to.")
        reason: str = Field(..., description="The reason for switching.")

    args_schema: type[BaseModel] = Input

    @requires_approval
    def _run(self, mode_slug: str, reason: str):
        # Raise signal to be caught by Flow
        raise SwitchModeSignal(target_mode=mode_slug, reason=reason)


class NewTaskTool(BaseTool):
    name: str = "new_task"
    description: str = "Delegate a sub-task to another agent."

    class Input(BaseModel):
        mode: str = Field(..., description="The target agent mode.")
        message: str = Field(..., description="The task description.")
        expected_output: str = Field(..., description="The expected output criteria.")

    args_schema: type[BaseModel] = Input

    @requires_approval
    def _run(self, mode: str, message: str, expected_output: str):
        raise NewTaskSignal(target_mode=mode, message=message, expected_output=expected_output)


class AttemptCompletionTool(BaseTool):
    name: str = "attempt_completion"
    description: str = "Complete the current task."

    class Input(BaseModel):
        result: str = Field(..., description="The final result.")

    args_schema: type[BaseModel] = Input

    @requires_approval
    def _run(self, result: str):
        raise CompletionSignal(result=result)


class AskFollowupTool(BaseTool):
    name: str = "ask_followup_question"
    description: str = "Ask the user a follow-up question."

    class Input(BaseModel):
        question: str = Field(..., description="The question to ask.")
        options: list[str] = Field(default=None, description="Optional list of valid answers.")

    args_schema: type[BaseModel] = Input

    # NO @requires_approval because this tool IS the interaction
    def _run(self, question: str, options: list[str] | None = None):
        # We still raise a signal because the answer comes from the Flow loop (potentially)
        # OR we could just block here.
        # Given the Flow design, raising a signal allows the Flow to manage the state/history cleanly.
        raise AskFollowupSignal(question=question, options=options)
