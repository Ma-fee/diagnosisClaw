"""
Tests for HITL (Human-in-the-Loop) components.
"""

from xeno_agent.simulation import InteractionHandler, requires_approval


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
    assert handler._input_provider is custom_input


def test_ask_approval_with_auto_approve():
    """Test approval with auto-approve enabled."""
    handler = InteractionHandler()
    handler.set_auto_approve(True)

    approved = handler.ask_approval("Execute tool?", ["tool", "arg1"])

    assert approved is True


def test_ask_approval_with_custom_provider():
    """Test approval with custom input provider."""
    handler = InteractionHandler()
    handler.set_input_provider(lambda prompt: "y")

    approved = handler.ask_approval("Execute tool?", ["tool", "arg1"])

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
