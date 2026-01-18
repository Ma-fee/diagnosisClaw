"""
Tests for meta tools (switch_mode, new_task, etc.).
"""

import pytest

from xeno_agent.simulation import (
    AskFollowupSignal,
    AskFollowupTool,
    AttemptCompletionTool,
    CompletionSignal,
    InteractionHandler,
    NewTaskSignal,
    NewTaskTool,
    SwitchModeSignal,
    SwitchModeTool,
)


def test_switch_mode_tool_tool_name():
    """Test SwitchModeTool has correct name."""
    tool = SwitchModeTool()
    assert tool.name == "switch_mode"


def test_switch_mode_tool_raises_signal():
    """Test SwitchModeTool raises SwitchModeSignal."""
    tool = SwitchModeTool()
    InteractionHandler.set_auto_approve(True)

    with pytest.raises(SwitchModeSignal) as exc_info:
        tool._run(target_mode="developer", reason="Need code")

    assert exc_info.value.target_mode == "developer"
    assert exc_info.value.reason == "Need code"


def test_new_task_tool_tool_name():
    """Test NewTaskTool has correct name."""
    tool = NewTaskTool()
    assert tool.name == "new_task"


def test_new_task_tool_raises_signal():
    """Test NewTaskTool raises NewTaskSignal."""
    tool = NewTaskTool()
    InteractionHandler.set_auto_approve(True)

    with pytest.raises(NewTaskSignal) as exc_info:
        tool._run(target_mode="qa", message="Test this", expected_output="results")

    assert exc_info.value.target_mode == "qa"
    assert exc_info.value.message == "Test this"


def test_attempt_completion_tool_tool_name():
    """Test AttemptCompletionTool has correct name."""
    tool = AttemptCompletionTool()
    assert tool.name == "attempt_completion"


def test_attempt_completion_tool_raises_signal():
    """Test AttemptCompletionTool raises CompletionSignal."""
    tool = AttemptCompletionTool()
    InteractionHandler.set_auto_approve(True)

    with pytest.raises(CompletionSignal) as exc_info:
        tool._run(result="Done!")

    assert exc_info.value.result == "Done!"


def test_ask_followup_tool_tool_name():
    """Test AskFollowupTool has correct name."""
    tool = AskFollowupTool()
    assert tool.name == "ask_followup_question"


def test_ask_followup_tool_raises_signal():
    """Test AskFollowupTool raises AskFollowupSignal."""
    tool = AskFollowupTool()

    with pytest.raises(AskFollowupSignal) as exc_info:
        tool._run(question="Continue?", options=["yes", "no"])

    assert exc_info.value.question == "Continue?"
    assert exc_info.value.options == ["yes", "no"]


def test_ask_followup_tool_no_approval():
    """Test that AskFollowupTool doesn't require approval."""
    tool = AskFollowupTool()

    # AskFollowupTool should not have @requires_approval
    # So it should work without setting auto_approve
    with pytest.raises(AskFollowupSignal):
        tool._run(question="Test?", options=["a", "b"])
