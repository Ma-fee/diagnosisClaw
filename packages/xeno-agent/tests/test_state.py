"""
Tests for state models.
"""

from xeno_agent.simulation import SimulationState, TaskFrame


def test_task_frame_creation():
    """Test creating a TaskFrame with all required fields."""
    frame = TaskFrame(
        mode_slug="pm",
        task_id="task_1",
        trigger_message="Hello world",
        caller_mode=None,
        is_isolated=False,
    )

    assert frame.mode_slug == "pm"
    assert frame.task_id == "task_1"
    assert frame.trigger_message == "Hello world"
    assert frame.caller_mode is None
    assert frame.is_isolated is False


def test_task_frame_defaults():
    """Test TaskFrame with optional fields omitted."""
    frame = TaskFrame(mode_slug="pm", task_id="task_1", trigger_message="Hello world")

    assert frame.caller_mode is None
    assert frame.is_isolated is False


def test_simulation_state_creation():
    """Test creating an empty SimulationState."""
    state = SimulationState()

    assert len(state.stack) == 0
    assert len(state.conversation_history) == 0
    assert state.final_output is None
    assert state.is_terminated is False


def test_simulation_state_with_stack():
    """Test SimulationState with a stack of frames."""
    frame = TaskFrame(mode_slug="pm", task_id="task_1", trigger_message="Hello")

    state = SimulationState(stack=[frame])

    assert len(state.stack) == 1
    assert state.stack[0].mode_slug == "pm"


def test_simulation_state_conversation_history():
    """Test adding conversation history."""
    state = SimulationState()

    state.conversation_history.append({"role": "user", "content": "Hello"})
    state.conversation_history.append({"role": "assistant", "content": "Hi there!"})

    assert len(state.conversation_history) == 2
    assert state.conversation_history[0]["role"] == "user"
