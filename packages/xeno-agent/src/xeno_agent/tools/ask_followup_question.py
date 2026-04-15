"""AskFollowupQuestion tool implementation."""

from __future__ import annotations

import html
import re
from typing import Any, assert_never, cast

from agentpool.agents.context import AgentContext
from agentpool.tools.base import ToolResult
from mcp.types import ElicitRequestFormParams, ErrorData


async def ask_followup_question(
    ctx: AgentContext,
    question: str,
    follow_up: str,
) -> ToolResult:
    """Ask a follow-up question with suggestions.

    Parses suggestions from <suggest> tags and presents them to the user.

    Args:
        ctx: Agent execution context.
        question: The main question to ask the user.
        follow_up: Question text containing <suggest> tags.

    Returns:
        ToolResult with the user's response.
    """
    # Use specified regex for extraction
    raw_suggestions = re.findall(r"<suggest\s*([^>]*)>(.*?)</suggest>", follow_up, re.DOTALL)
    suggestions = cast(list[tuple[str, str]], raw_suggestions)

    choices: list[str] = []
    input_suggestion: str | None = None
    suggestion_map: dict[str, dict[str, str]] = {}

    for attr_str, content_raw in suggestions:
        # Unescape content as requested
        suggestion_content = html.unescape(content_raw).strip()
        # Parse attributes
        raw_attrs = re.findall(r'(\w+)="([^"]*)"', attr_str)
        suggestion_attrs = dict(cast(list[tuple[str, str]], raw_attrs))
        suggestion_map[suggestion_content] = suggestion_attrs

        if suggestion_attrs.get("type") == "input":
            input_suggestion = suggestion_content
        else:
            choices.append(suggestion_content)

    # Map suggestions to a JSON schema enum
    if choices:
        schema: dict[str, Any] = {
            "type": "string",
            "enum": choices,
        }
        # Include type="input" suggestions in the schema
        if input_suggestion and input_suggestion not in choices:
            choices.append(input_suggestion)
            schema["enum"] = choices
    elif input_suggestion:
        # If only input suggestion exists, we can still use it or fallback to plain string
        schema = {"type": "string", "default": input_suggestion}
    else:
        schema = {"type": "string"}

    params = ElicitRequestFormParams(message=question, requestedSchema=schema)
    result = await ctx.handle_elicitation(params)

    if isinstance(result, ErrorData):
        return ToolResult(
            content=f"Error: {result.message}",
            metadata={"answers": []},
        )

    # Now result is ElicitResult
    action = result.action
    match action:
        case "accept":
            content = result.content
            # Content is a dict with "value" key per MCP spec
            if isinstance(content, dict) and "value" in content:
                value = content["value"]
                answer_str = str(value)
            else:
                answer_str = str(content)

            # Return ToolResult with answer wrapped in [[answer]] in metadata
            metadata: dict[str, Any] = {"answers": [[answer_str]]}
            if suggestion_attrs := suggestion_map.get(answer_str):
                metadata["suggestion_attributes"] = suggestion_attrs

            return ToolResult(
                content=answer_str,
                metadata=metadata,
            )
        case "cancel":
            return ToolResult(
                content="User cancelled the request",
                metadata={"answers": []},
            )
        case "decline":
            return ToolResult(
                content="User declined to answer",
                metadata={"answers": []},
            )
        case _ as unreachable:
            assert_never(unreachable)
