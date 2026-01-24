"""
XenoMessageNode wrapper for agentpool integration.

This module defines the XenoMessageNode class that wraps pydantic_ai.messages
into the agentpool MessageNode format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic_ai.messages import (
    ModelResponse,
    ModelResponsePart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
)

if TYPE_CHECKING:
    pass


@dataclass
class MessageNode:
    """Base class for message nodes in agentpool.

    This is a local definition since agentpool v0.0.1 is currently an empty stub.
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
