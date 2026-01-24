"""
Tests for agentpool integration.
"""

import agentpool
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart

from xeno_agent.pydantic_ai.pool import MessageNode, XenoMessageNode


def test_agentpool_import():
    """Test that agentpool can be imported."""
    assert agentpool is not None


def test_message_node_base():
    """Test that MessageNode base class exists and works."""
    node = MessageNode(
        id="test-id",
        parent_id=None,
        content="Test content",
        role="user",
    )
    assert node.id == "test-id"
    assert node.content == "Test content"
    assert node.role == "user"
    assert node.parent_id is None
    assert node.tool_calls == []
    assert node.tool_returns == []


def test_node_creation():
    """Test that a MessageNode can be created."""
    # Create a simple text message node
    node = XenoMessageNode.from_text("Hello, world!", parent_id=None, role="user")

    assert node.id is not None
    assert node.content == "Hello, world!"
    assert node.role == "user"
    assert node.parent_id is None
    assert len(node.tool_calls) == 0
    assert len(node.tool_returns) == 0


def test_xeno_message_node_from_model_response():
    """Test creating XenoMessageNode from pydantic_ai ModelResponse."""
    # Create a ModelResponse with text content
    message = ModelResponse(
        parts=[TextPart(content="This is a test response")],
        model_name="gpt-4",
        timestamp=None,
        usage=None,
    )

    node = XenoMessageNode.from_message(message, parent_id="parent-id", role="assistant")

    assert node.id is not None
    assert node.content == "This is a test response"
    assert node.role == "assistant"
    assert node.parent_id == "parent-id"
    assert node.message == message
    assert len(node.tool_calls) == 0
    assert len(node.tool_returns) == 0


def test_xeno_message_node_with_tool_calls():
    """Test XenoMessageNode with tool calls."""
    message = ModelResponse(
        parts=[
            TextPart(content="Let me help you with that."),
            ToolCallPart(
                tool_call_id="call_123",
                tool_name="search",
                args={"query": "test"},
            ),
        ],
        model_name="gpt-4",
        timestamp=None,
        usage=None,
    )

    node = XenoMessageNode.from_message(message)

    assert len(node.tool_calls) == 1
    assert node.tool_calls[0]["tool_call_id"] == "call_123"
    assert node.tool_calls[0]["tool_name"] == "search"
    assert node.tool_calls[0]["args"] == {"query": "test"}
    assert node.has_tool_calls() is True
    assert node.get_tool_call_count() == 1


def test_xeno_message_node_with_tool_returns():
    """Test XenoMessageNode with tool returns."""
    message = ModelResponse(
        parts=[
            ToolReturnPart(
                tool_call_id="call_123",
                tool_name="search",
                content="Search result: found 10 items",
            ),
        ],
        model_name="gpt-4",
        timestamp=None,
        usage=None,
    )

    node = XenoMessageNode.from_message(message)

    assert len(node.tool_returns) == 1
    assert node.tool_returns[0]["tool_call_id"] == "call_123"
    assert node.tool_returns[0]["content"] == "Search result: found 10 items"


def test_xeno_message_node_to_dict():
    """Test converting XenoMessageNode to dictionary."""
    node = XenoMessageNode.from_text("Test message", role="user")

    result = node.to_dict()

    assert result["id"] == node.id
    assert result["content"] == "Test message"
    assert result["role"] == "user"
    assert result["parent_id"] is None
    assert "tool_calls" in result
    assert "tool_returns" in result
    assert "metadata" in result


def test_xeno_message_node_inheritance():
    """Test that XenoMessageNode inherits from MessageNode."""
    node = XenoMessageNode.from_text("Test")

    assert isinstance(node, MessageNode)
    assert isinstance(node, XenoMessageNode)
