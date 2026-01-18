"""
Tests for signal system.
"""

from xeno_agent.simulation import (
    AskFollowupSignal,
    CompletionSignal,
    NewTaskSignal,
    SimulationSignal,
    SwitchModeSignal,
    UpdateTodoListSignal,
)


def test_switch_mode_signal():
    """Test creating and raising SwitchModeSignal."""
    signal = SwitchModeSignal(target_mode="developer", reason="Need to write code")

    assert isinstance(signal, SimulationSignal)
    assert signal.target_mode == "developer"
    assert signal.reason == "Need to write code"


def test_new_task_signal():
    """Test creating NewTaskSignal."""
    signal = NewTaskSignal(target_mode="qa", message="Test the code", expected_output="test_results")

    assert signal.target_mode == "qa"
    assert signal.message == "Test the code"
    assert signal.expected_output == "test_results"


def test_new_task_signal_defaults():
    """Test NewTaskSignal with optional fields omitted."""
    signal = NewTaskSignal(target_mode="qa", message="Test the code")

    assert signal.expected_output == ""


def test_completion_signal():
    """Test CompletionSignal."""
    signal = CompletionSignal(result="Task completed successfully!")

    assert signal.result == "Task completed successfully!"


def test_ask_followup_signal():
    """Test AskFollowupSignal."""
    signal = AskFollowupSignal(question="Should I proceed?", options=["yes", "no"])

    assert signal.question == "Should I proceed?"
    assert signal.options == ["yes", "no"]


def test_update_todo_list_signal():
    """Test UpdateTodoListSignal."""
    todos = [
        {"id": "1", "task": "Write code", "status": "completed"},
        {"id": "2", "task": "Write tests", "status": "pending"},
    ]

    signal = UpdateTodoListSignal(todos=todos)

    assert signal.todos == todos
    assert len(signal.todos) == 2
