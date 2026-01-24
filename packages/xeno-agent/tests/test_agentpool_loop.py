"""
Tests for InteractionManager (AgentPoolLoop)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ThinkingPart

from xeno_agent.agentpool.loop import InteractionManager
from xeno_agent.agentpool.node import XenoMessageNode
from xeno_agent.pydantic_ai.events import (
    AgentSwitchEvent,
    ContentEvent,
    ThoughtEvent,
    ToolResultEvent,
    ToolStartEvent,
)


@pytest.fixture
def mock_factory():
    """Create a mock AgentFactory."""
    return MagicMock()


@pytest.fixture
def mock_flow_config():
    """Create a mock FlowConfig."""
    config = MagicMock()
    config.agents = {
        "test_agent": {"name": "Test Agent"},
        "expert_agent": {"name": "Expert Agent"},
    }
    return config


@pytest.fixture
def mock_tool_manager():
    """Create a mock FlowToolManager."""
    return MagicMock()


@pytest.fixture
def interaction_manager(mock_factory, mock_flow_config, mock_tool_manager):
    """Create an InteractionManager instance for testing."""
    return InteractionManager(
        factory=mock_factory,
        flow_config=mock_flow_config,
        tool_manager=mock_tool_manager,
        model="test-model",
    )


class TestInteractionManagerInit:
    """Tests for InteractionManager initialization."""

    def test_init(self, interaction_manager, mock_factory, mock_flow_config, mock_tool_manager):
        """Test InteractionManager initialization."""
        assert interaction_manager.factory == mock_factory
        assert interaction_manager.flow_config == mock_flow_config
        assert interaction_manager.tool_manager == mock_tool_manager
        assert interaction_manager.model == "test-model"


class TestCreateNode:
    """Tests for _create_node method."""

    def test_create_node(self, interaction_manager):
        """Test creating a XenoAgentNode."""
        node = interaction_manager._create_node("test_agent")

        assert node.agent_id == "test_agent"
        assert node.factory == interaction_manager.factory
        assert node.flow_config == interaction_manager.flow_config
        assert node.tool_manager == interaction_manager.tool_manager
        assert node.model == "test-model"


class TestStream:
    """Tests for stream method."""

    @pytest.mark.asyncio
    async def test_stream_basic(self, interaction_manager):
        """Test basic streaming of events."""
        # Create a mock XenoMessageNode with text content
        mock_message = ModelResponse(
            parts=[TextPart(content="Hello, world!")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        # Mock the node.run method to return our mock node
        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=MagicMock(run=AsyncMock(return_value=mock_node)),
        ):
            # Collect events
            events = []
            async for event in interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
            ):
                events.append(event)  # noqa: PERF401

            # Verify we got exactly one ContentEvent
            assert len(events) == 1
            assert isinstance(events[0], ContentEvent)
            assert events[0].delta == "Hello, world!"

    @pytest.mark.asyncio
    async def test_stream_with_thought(self, interaction_manager):
        """Test streaming events with thought content."""
        mock_message = ModelResponse(
            parts=[
                ThinkingPart(content="Let me think about this..."),
                TextPart(content="The answer is 42."),
            ],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=MagicMock(run=AsyncMock(return_value=mock_node)),
        ):
            events = []
            async for event in interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
            ):
                events.append(event)  # noqa: PERF401

            # Verify we got ThoughtEvent and ContentEvent
            assert len(events) == 2
            assert isinstance(events[0], ThoughtEvent)
            assert events[0].delta == "Let me think about this..."
            assert isinstance(events[1], ContentEvent)
            assert events[1].delta == "The answer is 42."

    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(self, interaction_manager):
        """Test streaming events with tool calls."""
        mock_message = ModelResponse(
            parts=[TextPart(content="Done with tool")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        # Add tool calls and returns
        mock_node.tool_calls = [
            {
                "tool_call_id": "call_123",
                "tool_name": "search",
                "args": {"query": "test"},
            },
        ]
        mock_node.tool_returns = [
            {
                "tool_call_id": "call_123",
                "content": "Search result: ...",
            },
        ]

        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=MagicMock(run=AsyncMock(return_value=mock_node)),
        ):
            events = []
            async for event in interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
            ):
                events.append(event)  # noqa: PERF401

            # Verify we got ToolStartEvent, ToolResultEvent, and ContentEvent
            assert len(events) == 3
            assert isinstance(events[0], ToolStartEvent)
            assert events[0].call_id == "call_123"
            assert events[0].name == "search"
            assert events[0].args == {"query": "test"}

            assert isinstance(events[1], ToolResultEvent)
            assert events[1].call_id == "call_123"
            assert events[1].result == "Search result: ..."

            assert isinstance(events[2], ContentEvent)
            assert events[2].delta == "Done with tool"

    @pytest.mark.asyncio
    async def test_stream_with_agent_switch(self, interaction_manager):
        """Test streaming events with agent delegation."""
        mock_message = ModelResponse(
            parts=[TextPart(content="Expert's response")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        # Simulate agent switch by setting different agent_id in metadata
        mock_node.metadata["agent_id"] = "expert_agent"

        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=MagicMock(run=AsyncMock(return_value=mock_node)),
        ):
            events = []
            async for event in interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
            ):
                events.append(event)  # noqa: PERF401

            # Verify we got AgentSwitchEvent and ContentEvent
            assert len(events) == 2
            assert isinstance(events[0], AgentSwitchEvent)
            assert events[0].agent_id == "expert_agent"
            assert events[0].name == "Expert Agent"

            assert isinstance(events[1], ContentEvent)
            assert events[1].delta == "Expert's response"

    @pytest.mark.asyncio
    async def test_stream_with_history_and_session(self, interaction_manager):
        """Test streaming with history and session_id."""
        mock_message = ModelResponse(
            parts=[TextPart(content="Response")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        mock_node_run = AsyncMock(return_value=mock_node)
        mock_node_instance = MagicMock(run=mock_node_run)

        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=mock_node_instance,
        ):
            await interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
                history=["previous message"],
                session_id="session-123",
            ).__anext__()

            # Verify node.run was called with correct arguments
            mock_node_run.assert_called_once()
            call_kwargs = mock_node_run.call_args[1]
            assert call_kwargs["message"] == "Test message"
            assert call_kwargs["history"] == ["previous message"]
            assert call_kwargs["session_id"] == "session-123"

    @pytest.mark.asyncio
    async def test_stream_empty_response(self, interaction_manager):
        """Test streaming with empty response."""
        # Empty message (no parts)
        mock_message = ModelResponse(
            parts=[],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        mock_node = XenoMessageNode.from_message(mock_message)

        with patch.object(
            interaction_manager,
            "_create_node",
            return_value=MagicMock(run=AsyncMock(return_value=mock_node)),
        ):
            events = []
            async for event in interaction_manager.stream(
                agent_id="test_agent",
                message="Test message",
            ):
                events.append(event)  # noqa: PERF401

            # Should have no events
            assert len(events) == 0


class TestEmitEventsFromNode:
    """Tests for _emit_events_from_node method."""

    @pytest.mark.asyncio
    async def test_emit_content_event(self, interaction_manager):
        """Test emitting content events."""
        mock_message = ModelResponse(
            parts=[TextPart(content="Test content")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        node = XenoMessageNode.from_message(mock_message)

        events = []
        async for event in interaction_manager._emit_events_from_node(node, "test_agent"):
            events.append(event)  # noqa: PERF401

        assert len(events) == 1
        assert isinstance(events[0], ContentEvent)
        assert events[0].delta == "Test content"

    @pytest.mark.asyncio
    async def test_emit_thought_event(self, interaction_manager):
        """Test emitting thought events."""
        mock_message = ModelResponse(
            parts=[ThinkingPart(content="Thinking...")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        node = XenoMessageNode.from_message(mock_message)

        events = []
        async for event in interaction_manager._emit_events_from_node(node, "test_agent"):
            events.append(event)  # noqa: PERF401

        assert len(events) == 1
        assert isinstance(events[0], ThoughtEvent)
        assert events[0].delta == "Thinking..."

    @pytest.mark.asyncio
    async def test_emit_multiple_parts(self, interaction_manager):
        """Test emitting events from multiple parts."""
        mock_message = ModelResponse(
            parts=[
                ThinkingPart(content="First thought"),
                TextPart(content="First text"),
                ThinkingPart(content="Second thought"),
                TextPart(content="Second text"),
            ],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        node = XenoMessageNode.from_message(mock_message)

        events = []
        async for event in interaction_manager._emit_events_from_node(node, "test_agent"):
            events.append(event)  # noqa: PERF401

        assert len(events) == 4
        assert isinstance(events[0], ThoughtEvent)
        assert events[0].delta == "First thought"
        assert isinstance(events[1], ContentEvent)
        assert events[1].delta == "First text"
        assert isinstance(events[2], ThoughtEvent)
        assert events[2].delta == "Second thought"
        assert isinstance(events[3], ContentEvent)
        assert events[3].delta == "Second text"

    @pytest.mark.asyncio
    async def test_emit_agent_switch_event(self, interaction_manager):
        """Test emitting agent switch events."""
        mock_message = ModelResponse(
            parts=[TextPart(content="Response")],
            model_name="test-model",
            timestamp=None,
            usage=None,
        )
        node = XenoMessageNode.from_message(mock_message)
        node.metadata["agent_id"] = "expert_agent"

        events = []
        async for event in interaction_manager._emit_events_from_node(node, "test_agent"):
            events.append(event)  # noqa: PERF401

        assert len(events) == 2
        assert isinstance(events[0], AgentSwitchEvent)
        assert events[0].agent_id == "expert_agent"
        assert events[0].name == "Expert Agent"
        assert isinstance(events[1], ContentEvent)
