"""QuestionForUser tool implementation with XML parsing and MCP Elicit integration."""

from __future__ import annotations

from typing import Any

from agentpool.agents.context import AgentContext
from agentpool.tools.base import ToolResult
from mcp.types import ElicitRequestFormParams, ErrorData
from pydantic_xml import BaseXmlModel, attr, element


class Suggest(BaseXmlModel, tag="suggest"):
    """A suggestion option within a question."""

    type: str = attr(default="choice")
    description: str | None = attr(default=None)
    next_action: str | None = attr(default=None)
    label: str  # Element text


class Question(BaseXmlModel, tag="question"):
    """A single question with its options."""

    header: str = attr()
    type: str = attr(default="enum")
    required: bool = attr(default=True)
    text: str = element(tag="text")
    options: list[Suggest] = element(tag="suggest", default=[])


class Questions(BaseXmlModel, tag="questions"):
    """Wrapper for multiple questions."""

    questions: list[Question] = element(tag="question")


def parse_questionnaire(xml: str) -> list[Question]:
    """Parse XML questionnaire into Question objects.

    Args:
        xml: XML string containing one or more <question> tags.

    Returns:
        List of parsed Question objects.
    """
    wrapped = f"<questions>{xml}</questions>"
    return Questions.from_xml(wrapped).questions


def _build_acp_schema(questions: list[Question]) -> dict[str, Any]:
    """Build ACP JSON schema from questions.

    Maps question types to appropriate JSON schema constructs:
    - enum -> string with oneOf for options
    - multi -> array with enum items
    - input -> string with minLength=1

    Args:
        questions: List of Question objects.

    Returns:
        JSON schema dictionary for ACP form.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    for i, q in enumerate(questions):
        key = f"q{i}"
        if q.required:
            required.append(key)

        if q.type == "enum":
            properties[key] = {
                "type": "string",
                "title": q.header,
                "description": q.text,
                "oneOf": [{"const": o.label, **({"title": o.description} if o.description else {})} for o in q.options],
            }
        elif q.type == "multi":
            # Build options and x-option-descriptions mapping
            option_labels = [o.label for o in q.options]
            descriptions = {o.label: o.description for o in q.options if o.description}
            multi_schema: dict[str, Any] = {
                "type": "array",
                "title": q.header,
                "description": q.text,
                "items": {
                    "type": "string",
                    "enum": option_labels,
                },
                "uniqueItems": True,
            }
            if descriptions:
                multi_schema["items"]["x-option-descriptions"] = descriptions
            properties[key] = multi_schema
        elif q.type == "input":
            properties[key] = {
                "type": "string",
                "title": q.header,
                "description": q.text,
                "minLength": 1,
            }

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def _format_response(questions: list[Question], result: Any) -> ToolResult:
    """Format the elicitation result into a ToolResult.

    Args:
        questions: List of Question objects (for structure reference).
        result: Result from ctx.handle_elicitation (ElicitResult or ErrorData).

    Returns:
        ToolResult with formatted content and metadata.
    """
    if isinstance(result, ErrorData):
        return ToolResult(
            content=f"Error: {result.message}",
            metadata={"answers": []},
        )

    action = result.action
    if action == "accept":
        content = result.content
        # Content is a dict with q0, q1... keys per schema
        answers: list[list[Any]] = []
        content_parts: list[str] = []

        for i, q in enumerate(questions):
            key = f"q{i}"
            value = content.get(key) if isinstance(content, dict) else None

            if q.type == "multi":
                # Multi-select returns list
                answer_list = value if isinstance(value, list) else [value] if value else []
                answers.append(answer_list)
                content_parts.append(f"{q.header}: {', '.join(str(a) for a in answer_list)}")
            else:
                # enum or input returns single value
                answer = str(value) if value else ""
                answers.append([answer])
                content_parts.append(f"{q.header}: {answer}")

        return ToolResult(
            content="\n".join(content_parts),
            metadata={"answers": answers},
        )
    if action == "cancel":
        return ToolResult(
            content="User cancelled the questionnaire",
            metadata={"answers": []},
        )
    if action == "decline":
        return ToolResult(
            content="User declined to complete the questionnaire",
            metadata={"answers": []},
        )
    raise RuntimeError(f"Unknown action: {action}")


async def question_for_user(
    ctx: AgentContext,
    questionnaire: str,
) -> ToolResult:
    """Present a questionnaire to the user and collect responses.

    Parses questions from XML format, presents them as a form via MCP Elicit,
    and returns the user's answers.

    XML Format:
        <question header="..." type="enum|multi|input" required="true">
            <text>Question text</text>
            <suggest type="choice">Option 1</suggest>
            <suggest type="choice">Option 2</suggest>
        </question>

    Args:
        ctx: Agent execution context.
        questionnaire: XML string containing one or more <question> tags.

    Returns:
        ToolResult with formatted answers in metadata["answers"].
    """
    questions = parse_questionnaire(questionnaire)
    schema = _build_acp_schema(questions)
    message = "Please answer the following questions:"
    if questions:
        message = questions[0].header
    params = ElicitRequestFormParams(message=message, requestedSchema=schema)
    result = await ctx.handle_elicitation(params)
    return _format_response(questions, result)
