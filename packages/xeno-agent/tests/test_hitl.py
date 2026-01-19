"""
Tests for HITL (Human-in-the-Loop) components.
"""

import pytest

from xeno_agent.core.hitl import (
    AutoApproveProvider,
    ConsoleFeedbackProvider,
    InteractionHandler,
    human_feedback,
    requires_approval,
)


@pytest.fixture(autouse=True)
def reset_interaction_handler():
    """Reset InteractionHandler state before each test."""
    InteractionHandler.set_auto_approve(False)
    InteractionHandler.set_input_provider(None)
    yield
    InteractionHandler.set_auto_approve(False)
    InteractionHandler.set_input_provider(None)


def test_interaction_handler_singleton():
    """Test that InteractionHandler is a singleton."""
    handler1 = InteractionHandler()
    handler2 = InteractionHandler()

    assert handler1 is handler2


def test_set_auto_approve():
    """Test setting auto-approve mode."""
    handler = InteractionHandler()

    handler.set_auto_approve(True)
    assert handler._auto_approve is True

    handler.set_auto_approve(False)
    assert handler._auto_approve is False


def test_set_input_provider():
    """Test setting custom input provider."""
    handler = InteractionHandler()

    def custom_input(prompt):
        return "test_input"

    handler.set_input_provider(custom_input)
    assert InteractionHandler._input_provider is custom_input


def test_ask_approval_with_auto_approve():
    """Test approval with auto-approve enabled."""
    handler = InteractionHandler()
    handler.set_auto_approve(True)

    approved = handler.ask_approval("Execute tool?")

    assert approved is True


def test_ask_approval_with_custom_provider():
    """Test approval with custom input provider."""
    handler = InteractionHandler()
    handler.set_input_provider(lambda prompt: "y")

    approved = handler.ask_approval("Execute tool?")

    assert approved is True


def test_get_input_with_auto_approve():
    """Test getting input with auto-approve (should return empty string)."""
    handler = InteractionHandler()
    handler.set_auto_approve(True)

    result = handler.get_input("Enter your input:")

    assert result == ""


def test_requires_approval_decorator():
    """Test @requires_approval decorator creates a wrapper."""

    @requires_approval
    def mock_tool(arg1, arg2):
        return f"executed with {arg1}, {arg2}"

    # The function should still be callable
    assert callable(mock_tool)


def test_decorator_preserves_function_doc():
    """Test that decorator preserves docstrings."""

    @requires_approval
    def my_tool():
        """This is my tool."""
        return "result"

    assert my_tool.__doc__ == "This is my tool."


def test_console_feedback_provider():
    """Test ConsoleFeedbackProvider uses InteractionHandler."""
    provider = ConsoleFeedbackProvider()
    InteractionHandler.set_input_provider(lambda x: "console_input")

    # Test with string context
    assert provider.request_feedback("Test Message", None) == "console_input"

    # Test with object context
    class Context:
        message = "Msg"
        method_output = "Output"

    assert provider.request_feedback(Context, None) == "console_input"


def test_auto_approve_provider():
    """Test AutoApproveProvider returns 'approved'."""
    provider = AutoApproveProvider()
    assert provider.request_feedback("Any", None) == "approved"


def test_human_feedback_decorator_flow():
    """Test human_feedback decorator works with Flow provider."""

    class MockFlow:
        hitl_provider = AutoApproveProvider()

    flow = MockFlow()

    @human_feedback(message="Test", emit=["approved", "rejected"])
    def method(self):
        return "original_result"

    # Manually bind
    bound = method.__get__(flow, MockFlow)

    # AutoApproveProvider returns "approved", which is in emit list
    assert bound() == "approved"


def test_human_feedback_decorator_default_provider():
    """Test human_feedback decorator falls back to Console/InteractionHandler."""

    class MockFlow:
        # No hitl_provider
        pass

    flow = MockFlow()

    InteractionHandler.set_input_provider(lambda x: "manual_input")

    @human_feedback(message="Test")
    def method(self):
        return "original"

    bound = method.__get__(flow, MockFlow)

    assert bound() == "manual_input"
