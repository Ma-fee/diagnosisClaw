"""
Tests for agentpool integration.
"""

from unittest.mock import AsyncMock, Mock, patch

import agentpool
import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart

from xeno_agent.agentpool.node import (
    MAX_DELEGATION_DEPTH,
    MessageNode,
    XenoAgentNode,
    XenoMessageNode,
)
from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.tool_manager import FlowToolManager


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


# ============================================================================
# Tests for XenoAgentNode
# ============================================================================


@pytest.mark.asyncio
async def test_xeno_agent_node_initialization():
    """Test that XenoAgentNode can be initialized."""
    # Setup
    base_path = "config"
    config_loader = YAMLConfigLoader(base_path=base_path)
    factory = AgentFactory(config_loader=config_loader, model="test-model")

    flow_config = config_loader.load_flow_config("fault_diagnosis")
    tool_manager = FlowToolManager(flow_config.tools)

    # Create XenoAgentNode
    node = XenoAgentNode(
        agent_id="qa_assistant",
        factory=factory,
        flow_config=flow_config,
        tool_manager=tool_manager,
        model="test-model",
    )

    # Verify initialization
    assert node.agent_id == "qa_assistant"
    assert node.factory is factory
    assert node.flow_config is flow_config
    assert node.tool_manager is tool_manager
    assert node.model == "test-model"


@pytest.mark.asyncio
async def test_xeno_agent_node_recursion_limit():
    """Test that XenoAgentNode throws RecursionError when depth exceeds limit."""
    # Setup
    base_path = "config"
    config_loader = YAMLConfigLoader(base_path=base_path)
    factory = AgentFactory(config_loader=config_loader, model="test-model")

    flow_config = config_loader.load_flow_config("fault_diagnosis")
    tool_manager = FlowToolManager(flow_config.tools)

    # Create node
    node = XenoAgentNode(
        agent_id="qa_assistant",
        factory=factory,
        flow_config=flow_config,
        tool_manager=tool_manager,
    )

    # The run() method should detect this depth and raise RecursionError
    # Simulate deep recursion by passing parent_depth
    with pytest.raises(RecursionError) as exc_info:
        # Pass depth that would exceed limit when adding 1 for current agent
        await node.run(
            message="Test message",
            parent_depth=MAX_DELEGATION_DEPTH,  # Already at limit, adding current agent would exceed
        )

    # Verify error message mentions depth limit
    assert f"Max delegation depth ({MAX_DELEGATION_DEPTH}) exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_xeno_agent_node_run_without_api():
    """Test that XenoAgentNode run() method constructs correct RuntimeDeps."""
    from pydantic_ai import Agent

    # Setup
    base_path = "config"
    config_loader = YAMLConfigLoader(base_path=base_path)
    factory = AgentFactory(config_loader=config_loader, model="test-model")

    flow_config = config_loader.load_flow_config("fault_diagnosis")
    tool_manager = FlowToolManager(flow_config.tools)

    node = XenoAgentNode(
        agent_id="qa_assistant",
        factory=factory,
        flow_config=flow_config,
        tool_manager=tool_manager,
    )

    # Create a mock agent
    mock_agent = Mock(spec=Agent)

    # Create a mock result with proper structure
    mock_result = Mock()
    mock_result.all_messages.return_value = [
        ModelResponse(
            parts=[TextPart(content="Mocked response")],
            model_name="test-model",
            timestamp=None,
            usage=Mock(request_tokens=10, response_tokens=20, total_tokens=30),
        ),
    ]
    mock_result.usage.return_value = Mock(request_tokens=10, response_tokens=20, total_tokens=30)
    mock_result.data = "Mocked response"
    mock_agent.run = AsyncMock(return_value=mock_result)

    # Patch factory.create to return our mock agent
    with patch("xeno_agent.pydantic_ai.factory.AgentFactory.create", AsyncMock(return_value=mock_agent)):
        # Run the node
        result_node = await node.run(message="Test message")

        # Verify result node
        assert isinstance(result_node, XenoMessageNode)
        assert result_node.content == "Mocked response"
        assert result_node.metadata["agent_id"] == "qa_assistant"
        assert "trace_id" in result_node.metadata
        assert result_node.metadata["depth"] == 1
        assert "usage" in result_node.metadata
        assert result_node.metadata["usage"]["total_tokens"] == 30


@pytest.mark.asyncio
async def test_xeno_agent_node_create_child():
    """Test that XenoAgentNode can create child nodes for delegation."""
    # Setup
    base_path = "config"
    config_loader = YAMLConfigLoader(base_path=base_path)
    factory = AgentFactory(config_loader=config_loader, model="test-model")

    flow_config = config_loader.load_flow_config("fault_diagnosis")
    tool_manager = FlowToolManager(flow_config.tools)

    # Create parent node
    parent_node = XenoAgentNode(
        agent_id="qa_assistant",
        factory=factory,
        flow_config=flow_config,
        tool_manager=tool_manager,
    )

    # Create child node
    child_node = parent_node.create_child_node("fault_expert")

    # Verify child node
    assert isinstance(child_node, XenoAgentNode)
    assert child_node.agent_id == "fault_expert"
    assert child_node.factory is parent_node.factory
    assert child_node.flow_config is parent_node.flow_config
    assert child_node.tool_manager is parent_node.tool_manager
