from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from ..utils.logging import get_logger

from ..core.signals import AskFollowupSignal, CompletionSignal, NewTaskSignal, SwitchModeSignal

logger = get_logger(__name__)


class SwitchModeTool(BaseTool):
    name: str = "switch_mode"
    description: str = """
    【切换角色/模式】
    使用场景：
    1. QA Assistant → Fault Expert: 检测到复杂故障诊断场景
    2. Fault Expert → Equipment Expert: 需要物理操作/现场指导
    3. Equipment Expert → Fault Expert: Active 模式下返回编排

    说明：完全切换到新角色，原角色不再执行
    """

    class Input(BaseModel):
        target: str = Field(..., description="The target agent mode/role (e.g. 'FaultExpert').")
        reason: str = Field(default="Switching context", description="The reason for switching.")

    args_schema: type[BaseModel] = Input

    def _run(self, target: str, reason: str = "Switching context") -> None:
        """
        Execute tool - raises signal to be caught by Flow.

        Args:
            target: The target agent mode/role
            reason: The reason for switching
        """
        raise SwitchModeSignal(target_mode=target, reason=reason)


class NewTaskTool(BaseTool):
    name: str = "new_task"
    description: str = """
    【委派子任务】
    使用场景：
    1. QA Assistant → Material Assistant: 简单信息查询
    2. Fault Expert → Material Assistant: 查找资料/规格/图纸
    3. Fault Expert → Equipment Expert (Worker): 分析图纸/诊断

    动作：临时切换角色执行任务，返回后继续原流程
    说明：子任务完成后自动返回当前角色，可使用子任务结果继续工作
    """

    class Input(BaseModel):
        target: str = Field(..., description="The target agent mode/role.")
        message: str = Field(default="", description="The task description.")
        expected_output: str = Field(default="", description="The expected output criteria.")

    args_schema: type[BaseModel] = Input

    def _run(self, target: str, message: str = "", expected_output: str = "") -> None:
        """
        Execute tool - raises signal for new task delegation.

        Args:
            target: The target agent mode/role
            message: The task description
            expected_output: The expected output criteria
        """
        if not message:
            message = f"Delegate task to {target}"
        if not expected_output:
            expected_output = "Task result"
        raise NewTaskSignal(target_mode=target, message=message, expected_output=expected_output)


class AttemptCompletionTool(BaseTool):
    name: str = "attempt_completion"
    description: str = "Complete the current task."

    class Input(BaseModel):
        result: str = Field(..., description="The final result.")

    args_schema: type[BaseModel] = Input

    def _run(self, result: str) -> None:
        """
        Execute tool - raises signal for task completion.

        Args:
            result: The final result of the task
        """
        raise CompletionSignal(result=result)


class AskFollowupTool(BaseTool):
    name: str = "ask_followup_question"
    description: str = "【询问用户】⚠️ 已弃用，请使用 Flow 级 HITL"

    class Input(BaseModel):
        question: str = Field(..., description="The question to ask.")
        options: list[str] | None = Field(default=None, description="Optional list of valid answers.")

    args_schema: type[BaseModel] = Input

    # NO @requires_approval because this tool IS the interaction
    def _run(self, question: str, options: list[str] | None = None) -> None:
        """
        Execute tool - raises signal for follow-up question.

        Note: Deprecated. Please use Flow's @human_feedback decorator.

        Args:
            question: The question to ask the user
            options: Optional list of valid answers
        """
        logger.warning("ask_followup_question 已弃用。请使用 Flow 的 @human_feedback 装饰器。")
        # We still raise a signal because the answer comes from the Flow loop (potentially)
        # OR we could just block here.
        # Given the Flow design, raising a signal allows the Flow to manage the state/history cleanly.
        raise AskFollowupSignal(question=question, options=options)
