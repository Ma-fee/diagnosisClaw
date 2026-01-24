"""
AgentPool Node Implementation

This module defines the MessageNode base class and XenoAgentNode wrapper
that bridges pydantic_ai agents to the agentpool architecture.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.runtime import RuntimeDeps
from xeno_agent.pydantic_ai.trace import TraceID

logger = logging.getLogger(__name__)

MAX_DELEGATION_DEPTH = 5


@dataclass
class MessageNode:
    """Base class for message nodes in agentpool.

    This is the base interface for all message nodes in the agentpool architecture.
    It represents a single message in the conversation graph.
    """

    id: str
    """Unique identifier for this message node."""

    parent_id: str | None
    """ID of the parent message node."""

    content: str
    """Text content of the message."""

    role: str
    """Role of the message (e.g., 'user', 'assistant', 'system')."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata associated with the message."""

    parts: list[ModelResponsePart] = field(default_factory=list)
    """Raw pydantic_ai message parts."""

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    """Tool calls made in this message."""

    tool_returns: list[dict[str, Any]] = field(default_factory=list)
    """Tool returns received in this message."""

    def to_dict(self) -> dict[str, Any]:
        """Convert message node to dictionary representation."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "content": self.content,
            "role": self.role,
            "metadata": self.metadata,
            "tool_calls": self.tool_calls,
            "tool_returns": self.tool_returns,
        }


@dataclass
class XenoMessageNode(MessageNode):
    """Xeno-specific wrapper for pydantic_ai messages.

    This class wraps pydantic_ai.message types (ModelResponse, etc.) into
    the MessageNode format, providing compatibility with the agentpool architecture.
    """

    message: ModelResponse | None = None
    """Original pydantic_ai ModelResponse message."""

    @classmethod
    def from_message(
        cls,
        message: ModelResponse,
        parent_id: str | None = None,
        role: str = "assistant",
    ) -> XenoMessageNode:
        """Create XenoMessageNode from pydantic_ai ModelResponse.

        Args:
            message: The pydantic_ai ModelResponse to wrap.
            parent_id: ID of the parent message node.
            role: Role of the message (default: 'assistant').

        Returns:
            A new XenoMessageNode instance.
        """
        # Extract text content from parts
        content_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        tool_returns: list[dict[str, Any]] = []

        for part in message.parts:
            if isinstance(part, TextPart):
                content_parts.append(part.content)
            elif isinstance(part, ThinkingPart) and hasattr(part, "content"):
                content_parts.append(f"<thinking>{part.content}</thinking>")
            elif isinstance(part, ToolCallPart):
                tool_calls.append(
                    {
                        "tool_call_id": part.tool_call_id,
                        "tool_name": part.tool_name,
                        "args": part.args if hasattr(part, "args") else {},
                    },
                )
            elif isinstance(part, ToolReturnPart):
                tool_returns.append(
                    {
                        "tool_call_id": part.tool_call_id,
                        "content": str(part.content) if hasattr(part, "content") else "",
                    },
                )

        content = "\n".join(content_parts) if content_parts else ""

        # Build metadata
        metadata: dict[str, Any] = {"model_name": message.model_name}

        if message.timestamp is not None:
            metadata["timestamp"] = message.timestamp.isoformat()

        if message.usage is not None:
            metadata["usage"] = {
                "request_tokens": getattr(message.usage, "request_tokens", 0),
                "response_tokens": getattr(message.usage, "response_tokens", 0),
                "total_tokens": getattr(message.usage, "total_tokens", 0),
            }

        return cls(
            id=message.vendor_id or str(uuid4()),
            parent_id=parent_id,
            content=content,
            role=role,
            parts=message.parts,
            tool_calls=tool_calls,
            tool_returns=tool_returns,
            message=message,
            metadata=metadata,
        )

    @classmethod
    def from_text(
        cls,
        text: str,
        parent_id: str | None = None,
        role: str = "user",
    ) -> XenoMessageNode:
        """Create XenoMessageNode from plain text.

        Args:
            text: The text content.
            parent_id: ID of the parent message node.
            role: Role of the message (default: 'user').

        Returns:
            A new XenoMessageNode instance.
        """
        return cls(
            id=str(uuid4()),
            parent_id=parent_id,
            content=text,
            role=role,
            parts=[],
        )

    def get_text_content(self) -> str:
        """Get the text content of the message.

        Returns:
            The text content string.
        """
        return self.content

    def has_tool_calls(self) -> bool:
        """Check if this message contains any tool calls.

        Returns:
            True if tool_calls is non-empty.
        """
        return len(self.tool_calls) > 0

    def get_tool_call_count(self) -> int:
        """Get the number of tool calls in this message.

        Returns:
            Number of tool calls.
        """
        return len(self.tool_calls)


if TYPE_CHECKING:
    from xeno_agent.pydantic_ai.factory import AgentFactory
    from xeno_agent.pydantic_ai.tool_manager import FlowToolManager


class XenoAgentNode:
    """Bridge wrapper that executes pydantic_ai agents via agentpool interface.

    This class acts as a MessageNode that wraps a pydantic_ai agent execution.
    It handles:
    - Agent creation via AgentFactory
    - TraceID injection into RuntimeDeps
    - Recursion depth checking (max depth = 5)
    - Delegation execution through pydantic_ai's run() method

    Attributes:
        agent_id: The ID of the agent this node represents.
        factory: The AgentFactory used to create agent instances.
        flow_config: The flow configuration for the agent.
        tool_manager: The tool manager for the agent.
        model: The model to use (default from factory).
    """

    def __init__(
        self,
        agent_id: str,
        factory: AgentFactory,
        flow_config: FlowConfig,
        tool_manager: FlowToolManager,
        model: str | None = None,
    ):
        """Initialize XenoAgentNode.

        Args:
            agent_id: The ID of the agent this node represents.
            factory: The AgentFactory used to create agent instances.
            flow_config: The flow configuration for the agent.
            tool_manager: The tool manager for the agent.
            model: Optional model override (uses factory default if None).
        """
        self.agent_id = agent_id
        self.factory = factory
        self.flow_config = flow_config
        self.tool_manager = tool_manager
        self.model = model

    async def run(
        self,
        message: str,
        history: list[ModelMessage] | None = None,
        session_id: str | None = None,
        parent_trace_id: str | None = None,
        parent_depth: int = 0,
    ) -> XenoMessageNode:
        """Execute the agent and return a message node.

        This method:
        1. Creates or reuses a TraceID context
        2. Checks recursion depth (max 5)
        3. Creates the agent via factory.create()
        4. Executes the agent with the given message
        5. Wraps the result in a XenoMessageNode

        Args:
            message: The user message to process.
            history: Optional message history for context.
            session_id: Optional session ID for tracking.
            parent_trace_id: Optional parent TraceID for child context.
            parent_depth: Depth of parent agent (for recursion checking).

        Returns:
            A XenoMessageNode containing the agent's response.

        Raises:
            RecursionError: If recursion depth exceeds MAX_DELEGATION_DEPTH.
        """
        # Create or get trace context
        if parent_trace_id:
            # Child agent - create child trace
            trace = TraceID.new(root_trace_id=parent_trace_id).child(self.agent_id)
        else:
            # Entry agent - create new trace
            trace = TraceID.new().child(self.agent_id)

        # Check recursion depth (include parent depth if provided)
        current_depth = len(trace.path) + parent_depth
        if current_depth > MAX_DELEGATION_DEPTH:
            raise RecursionError(f"Max delegation depth ({MAX_DELEGATION_DEPTH}) exceeded. Current depth: {current_depth}, Path: {trace.path}")

        # Create agent via factory (do this AFTER recursion check!)
        model = self.model or self.factory.model
        agent = await self.factory.create(
            self.agent_id,
            self.flow_config,
            tool_manager=self.tool_manager,
            use_cache=True,
        )

        # Build RuntimeDeps with trace injection
        deps = RuntimeDeps(
            flow=self.flow_config,
            trace=trace,
            factory=self.factory,
            tool_manager=self.tool_manager,
            message_history=history or [],
            session_id=session_id or str(uuid4()),
        )

        # Execute agent
        start_time = time.perf_counter()
        result = await agent.run(
            message,
            deps=deps,
            message_history=deps.message_history,
        )
        duration = time.perf_counter() - start_time

        logger.info(f"XenoAgentNode.run(): Agent {self.agent_id} completed in {duration:.3f}s (Tokens: {result.usage().total_tokens})")

        # Update message history
        all_messages = result.all_messages()
        if len(all_messages) > len(deps.message_history):
            new_messages = all_messages[len(deps.message_history) :]
            deps.message_history.extend(new_messages)

        # Get the last ModelResponse for wrapping
        # agent.run() returns a result, we need to get the final response
        model_response = None
        for msg in reversed(all_messages):
            if isinstance(msg, ModelResponse):
                model_response = msg
                break

        if model_response is None:
            # Fallback: create a text response from result.data
            from pydantic_ai.messages import TextPart as TPart

            model_response = ModelResponse(
                parts=[TPart(content=str(result.data))],
                model_name=model,
                timestamp=None,
                usage=result.usage(),
            )

        # Wrap in XenoMessageNode
        # Use parent trace_id for child relationships
        parent_node_id = parent_trace_id if parent_trace_id else None

        response_node = XenoMessageNode.from_message(
            model_response,
            parent_id=parent_node_id,
            role="assistant",
        )

        # Add execution metadata
        response_node.metadata.update(
            {
                "agent_id": self.agent_id,
                "trace_id": trace.trace_id,
                "session_id": deps.session_id,
                "depth": current_depth,
                "duration_seconds": duration,
                "usage": {
                    "request_tokens": result.usage().request_tokens,
                    "response_tokens": result.usage().response_tokens,
                    "total_tokens": result.usage().total_tokens,
                },
            },
        )

        return response_node

    def create_child_node(self, target_agent_id: str) -> XenoAgentNode:
        """Create a child node for delegation.

        Args:
            target_agent_id: The ID of the child agent.

        Returns:
            A new XenoAgentNode instance for the child agent.
        """
        return XenoAgentNode(
            agent_id=target_agent_id,
            factory=self.factory,
            flow_config=self.flow_config,
            tool_manager=self.tool_manager,
            model=self.model,
        )
