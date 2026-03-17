"""Unit tests for the question_for_user tool."""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from agentpool.tasks import RunAbortedError
from mcp.types import ErrorData

from xeno_agent.tools.question_for_user import (
    Question,
    Suggest,
    _build_acp_schema,
    _format_response,
    parse_questionnaire,
    question_for_user,
)

# =============================================================================
# XML Parsing Tests
# =============================================================================


def test_parse_enum_question_with_questions_wrapper():
    """Test parsing enum question with explicit <questions> wrapper."""
    xml = '<questions><question header="Model" type="enum"><text>What is the equipment model?</text><suggest>SY215C</suggest><suggest>SY235C</suggest></question></questions>'
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert result[0].header == "Model"
    assert result[0].type == "enum"
    assert result[0].text == "What is the equipment model?"
    assert len(result[0].options) == 2
    assert result[0].options[0].label == "SY215C"
    assert result[0].options[1].label == "SY235C"


def test_parse_enum_question_backward_compatible():
    """Test parsing bare enum question (backward compatibility - auto-wraps)."""
    xml = '<question header="Model" type="enum"><text>What is the equipment model?</text><suggest>SY215C</suggest><suggest>SY235C</suggest></question>'
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert result[0].header == "Model"
    assert result[0].type == "enum"
    assert result[0].text == "What is the equipment model?"
    assert len(result[0].options) == 2
    assert result[0].options[0].label == "SY215C"
    assert result[0].options[1].label == "SY235C"


def test_parse_multi_question_with_wrapper():
    """Test parsing multi-select with <questions> wrapper."""
    xml = (
        '<questions><question header="Symptoms" type="multi">'
        "<text>Select the observed symptoms</text>"
        "<suggest>Black smoke</suggest><suggest>Low power</suggest>"
        "<suggest>Abnormal noise</suggest></question></questions>"
    )
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert result[0].header == "Symptoms"
    assert result[0].type == "multi"
    assert result[0].text == "Select the observed symptoms"
    assert len(result[0].options) == 3
    assert result[0].options[0].label == "Black smoke"
    assert result[0].options[2].label == "Abnormal noise"


def test_parse_input_question_with_wrapper():
    """Test parsing input type question with <questions> wrapper."""
    xml = '<questions><question header="Notes" type="input"><text>Enter additional notes</text></question></questions>'
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert result[0].header == "Notes"
    assert result[0].type == "input"
    assert result[0].text == "Enter additional notes"
    assert len(result[0].options) == 0


def test_parse_multiple_questions_with_wrapper():
    """Test parsing multiple questions with explicit <questions> wrapper."""
    xml = (
        "<questions>"
        '<question header="First" type="enum"><text>Question 1</text><suggest>Option A</suggest></question>'
        '<question header="Second" type="input"><text>Question 2</text></question>'
        "</questions>"
    )
    result = parse_questionnaire(xml)

    assert len(result) == 2
    assert result[0].header == "First"
    assert result[0].type == "enum"
    assert result[1].header == "Second"
    assert result[1].type == "input"


def test_parse_question_with_suggest_attributes_and_wrapper():
    """Test parsing questions with suggest attributes using <questions> wrapper."""
    xml = (
        '<questions><question header="Test" type="enum"><text>Select option</text>'
        '<suggest type="input" description="Custom option" next_action="next">Custom</suggest>'
        "</question></questions>"
    )
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert len(result[0].options) == 1
    option = result[0].options[0]
    assert option.label == "Custom"
    assert option.type == "input"
    assert option.description == "Custom option"
    assert option.next_action == "next"


def test_parse_question_optional_with_wrapper():
    """Test parsing optional questions with <questions> wrapper."""
    xml = '<questions><question header="Optional" type="input" required="false"><text>Optional question</text></question></questions>'
    result = parse_questionnaire(xml)

    assert len(result) == 1
    assert result[0].header == "Optional"
    assert not result[0].required


# =============================================================================
# Schema Generation Tests
# =============================================================================


def test_build_enum_schema():
    """Test JSON schema generation for enum type question."""
    questions = [
        Question(
            header="Model",
            type="enum",
            text="What model?",
            required=True,
            options=[Suggest(label="SY215C"), Suggest(label="SY235C")],
        ),
    ]
    schema = _build_acp_schema(questions)

    assert schema["type"] == "object"
    assert "properties" in schema
    assert schema["required"] == ["q0"]
    assert "q0" in schema["properties"]
    assert schema["properties"]["q0"]["type"] == "string"
    assert schema["properties"]["q0"]["title"] == "Model"
    assert schema["properties"]["q0"]["description"] == "What model?"
    assert "oneOf" in schema["properties"]["q0"]
    one_of = schema["properties"]["q0"]["oneOf"]
    assert len(one_of) == 2
    # When no description, oneOf only has const (matches implementation)
    assert one_of[0] == {"const": "SY215C"}
    assert one_of[1] == {"const": "SY235C"}


def test_build_multi_schema():
    """Test JSON schema generation for multi-select type question."""
    questions = [
        Question(
            header="Symptoms",
            type="multi",
            text="Select symptoms",
            required=True,
            options=[Suggest(label="A"), Suggest(label="B"), Suggest(label="C")],
        ),
    ]
    schema = _build_acp_schema(questions)

    assert schema["properties"]["q0"]["type"] == "array"
    assert schema["properties"]["q0"]["title"] == "Symptoms"
    assert schema["properties"]["q0"]["description"] == "Select symptoms"
    assert "items" in schema["properties"]["q0"]
    assert schema["properties"]["q0"]["items"]["type"] == "string"
    assert schema["properties"]["q0"]["items"]["enum"] == ["A", "B", "C"]
    assert schema["properties"]["q0"]["uniqueItems"]


def test_build_input_schema():
    """Test JSON schema generation for input type question."""
    questions = [
        Question(
            header="Notes",
            type="input",
            text="Enter notes",
            required=True,
            options=[],
        ),
    ]
    schema = _build_acp_schema(questions)

    assert schema["properties"]["q0"]["type"] == "string"
    assert schema["properties"]["q0"]["title"] == "Notes"
    assert schema["properties"]["q0"]["description"] == "Enter notes"
    assert schema["properties"]["q0"]["minLength"] == 1


def test_build_acp_schema_multiple_questions():
    """Test JSON schema generation with multiple questions of different types."""
    questions = [
        Question(
            header="Enum Q",
            type="enum",
            text="Enum question",
            required=True,
            options=[Suggest(label="Option1")],
        ),
        Question(
            header="Multi Q",
            type="multi",
            text="Multi question",
            required=True,
            options=[Suggest(label="Opt1"), Suggest(label="Opt2")],
        ),
        Question(
            header="Input Q",
            type="input",
            text="Input question",
            required=False,
            options=[],
        ),
    ]
    schema = _build_acp_schema(questions)

    assert "q0" in schema["properties"]
    assert "q1" in schema["properties"]
    assert "q2" in schema["properties"]
    # Only q0 and q1 should be required
    assert "required" in schema
    assert sorted(schema["required"]) == ["q0", "q1"]


def test_build_acp_schema_not_required():
    """Test schema without required fields."""
    questions = [
        Question(
            header="Optional",
            type="input",
            text="Optional question",
            required=False,
            options=[],
        ),
    ]
    schema = _build_acp_schema(questions)

    # No required key if all questions are optional
    assert "required" not in schema or len(schema.get("required", [])) == 0


# =============================================================================
# Response Formatting Tests
# =============================================================================


def test_format_response_accept_enum():
    """Test formatting accept response for enum question."""
    questions = [
        Question(
            header="Model",
            type="enum",
            text="What model?",
            required=True,
            options=[Suggest(label="SY215C")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "SY215C"}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert content == "Model: SY215C"
    assert metadata["answers"] == [["SY215C"]]


def test_format_response_accept_multi():
    """Test formatting accept response for multi-select question."""
    questions = [
        Question(
            header="Symptoms",
            type="multi",
            text="Select symptoms",
            required=True,
            options=[Suggest(label="A"), Suggest(label="B")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": ["A", "B"]}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert content == "Symptoms: A, B"
    assert metadata["answers"] == [["A", "B"]]


def test_format_response_accept_input():
    """Test formatting accept response for input question."""
    questions = [
        Question(
            header="Notes",
            type="input",
            text="Enter notes",
            required=True,
            options=[],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "My notes"}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert content == "Notes: My notes"
    assert metadata["answers"] == [["My notes"]]


def test_format_response_accept_multiple_questions():
    """Test formatting accept response for multiple questions."""
    questions = [
        Question(
            header="Q1",
            type="enum",
            text="Question 1",
            required=True,
            options=[Suggest(label="A")],
        ),
        Question(
            header="Q2",
            type="input",
            text="Question 2",
            required=True,
            options=[],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "A", "q1": "Response"}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert content == "Q1: A\nQ2: Response"
    assert metadata["answers"] == [["A"], ["Response"]]


def test_format_response_cancel():
    """Test formatting cancel action response raises RunAbortedError."""
    questions = [
        Question(
            header="Test",
            type="enum",
            text="Test question",
            required=True,
            options=[Suggest(label="A")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "cancel"

    with pytest.raises(RunAbortedError, match="cancelled"):
        _format_response(questions, mock_result)


def test_format_response_decline():
    """Test formatting decline action response raises RunAbortedError."""
    questions = [
        Question(
            header="Test",
            type="enum",
            text="Test question",
            required=True,
            options=[Suggest(label="A")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "decline"

    with pytest.raises(RunAbortedError, match="declined"):
        _format_response(questions, mock_result)


def test_format_response_error_data():
    """Test formatting ErrorData response."""
    questions = [
        Question(
            header="Test",
            type="enum",
            text="Test question",
            required=True,
            options=[Suggest(label="A")],
        ),
    ]
    error_result = ErrorData(code=500, message="Server error occurred")

    result = _format_response(questions, error_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert "Error" in content
    assert "Server error occurred" in content
    assert metadata["answers"] == []


def test_format_response_unknown_action_raises():
    """Test that unknown action raises RuntimeError."""
    questions = [
        Question(
            header="Test",
            type="enum",
            text="Test question",
            required=True,
            options=[Suggest(label="A")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "unknown_action"

    with pytest.raises(RuntimeError) as exc_info:
        _format_response(questions, mock_result)

    assert "Unknown action: unknown_action" in str(exc_info.value)


def test_format_response_multi_empty():
    """Test formatting empty multi-select response."""
    questions = [
        Question(
            header="Symptoms",
            type="multi",
            text="Select symptoms",
            required=True,
            options=[Suggest(label="A")],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": []}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    # Empty multi-select returns empty list (not list with empty string)
    assert content == "Symptoms: "
    assert metadata["answers"] == [[]]


def test_format_response_input_empty():
    """Test formatting empty input response."""
    questions = [
        Question(
            header="Notes",
            type="input",
            text="Enter notes",
            required=True,
            options=[],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": ""}

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert content == "Notes: "
    assert metadata["answers"] == [[""]]


def test_format_response_non_dict_content():
    """Test handling non-dict content."""
    questions = [
        Question(
            header="Notes",
            type="input",
            text="Enter notes",
            required=True,
            options=[],
        ),
    ]
    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = "Direct string content"

    result = _format_response(questions, mock_result)
    content = cast(str, result.content)

    assert content == "Notes: "


# =============================================================================
# Integration Tests (question_for_user with mocked handle_elicitation)
# =============================================================================


@pytest.mark.asyncio
async def test_accept_response_single():
    """Test question_for_user with single enum accept response."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "SY215C"}
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Model" type="enum"><text>What model?</text><suggest>SY215C</suggest><suggest>SY235C</suggest></question>'
    result = await question_for_user(mock_ctx, xml)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert metadata["answers"] == [["SY215C"]]
    content = cast(str, result.content)
    assert "Model: SY215C" in content


@pytest.mark.asyncio
async def test_accept_response_multi():
    """Test question_for_user with multi-select accept response."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": ["A", "B", "C"]}
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Symptoms" type="multi"><text>Select symptoms</text><suggest>A</suggest><suggest>B</suggest><suggest>C</suggest></question>'
    result = await question_for_user(mock_ctx, xml)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert metadata["answers"] == [["A", "B", "C"]]
    content = cast(str, result.content)
    assert "Symptoms: A, B, C" in content


@pytest.mark.asyncio
async def test_cancel_response():
    """Test question_for_user with cancel action raises RunAbortedError."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "cancel"
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Test"><text>Q</text><suggest>A</suggest></question>'
    with pytest.raises(RunAbortedError, match="cancelled"):
        await question_for_user(mock_ctx, xml)


@pytest.mark.asyncio
async def test_decline_response():
    """Test question_for_user with decline action raises RunAbortedError."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "decline"
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Test"><text>Q</text><suggest>A</suggest></question>'
    with pytest.raises(RunAbortedError, match="declined"):
        await question_for_user(mock_ctx, xml)


@pytest.mark.asyncio
async def test_error_data_response():
    """Test question_for_user with ErrorData response."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    error_data = ErrorData(code=500, message="Server error")
    mock_ctx.handle_elicitation.return_value = error_data

    xml = '<question header="Test"><text>Q</text><suggest>A</suggest></question>'
    result = await question_for_user(mock_ctx, xml)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)
    content = cast(str, result.content)

    assert "Error" in content
    assert "Server error" in content
    assert metadata["answers"] == []


@pytest.mark.asyncio
async def test_question_for_user_multiple():
    """Test question_for_user with multiple questions."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "SY215C", "q1": "Notes here"}
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Model" type="enum"><text>Model?</text><suggest>SY215C</suggest></question><question header="Notes" type="input"><text>Notes?</text></question>'
    result = await question_for_user(mock_ctx, xml)
    metadata: dict[str, list[list[str]]] = cast(dict[str, Any], result.metadata)

    assert metadata["answers"] == [["SY215C"], ["Notes here"]]


@pytest.mark.asyncio
async def test_question_for_user_params_check():
    """Verify question_for_user calls handle_elicitation with correct params."""
    mock_ctx = MagicMock()
    mock_ctx.handle_elicitation = AsyncMock()

    mock_result = MagicMock()
    mock_result.action = "accept"
    mock_result.content = {"q0": "A"}
    mock_ctx.handle_elicitation.return_value = mock_result

    xml = '<question header="Test Question" type="enum"><text>Select option</text><suggest>A</suggest><suggest>B</suggest></question>'
    await question_for_user(mock_ctx, xml)

    mock_ctx.handle_elicitation.assert_called_once()
    params = mock_ctx.handle_elicitation.call_args[0][0]
    assert params.message == "Test Question"  # Uses first question header as message
    assert "requestedSchema" in vars(params) or hasattr(params, "requestedSchema")
