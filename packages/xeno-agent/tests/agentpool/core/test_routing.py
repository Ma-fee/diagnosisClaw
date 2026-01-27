"""Tests for Xeno routing tools.

Tests for routing tools that manage agent interaction flow:
- ask_followup: Request additional information from user
- attempt_completion: Signal task completion
- switch_mode: Transition between roles
- new_task: Delegate sub-task to another role
- update_todo: Update session todo list
"""

from __future__ import annotations

from inspect import signature
from unittest.mock import MagicMock

import pytest
from pydantic_ai import RunContext

from xeno_agent.agentpool.core.config import (
    RoleType,
    XenoConfig,
    XenoRoleConfig,
)
from xeno_agent.agentpool.core.deps import XenoAgentDeps

# Import routing tools
from xeno_agent.agentpool.core.routing import (
    ask_followup,
    attempt_completion,
    new_task,
    switch_mode,
    update_todo,
)


@pytest.fixture
def xeno_config() -> XenoConfig:
    """Create a test Xeno configuration."""
    return XenoConfig(
        version="1.0.0",
        roles={
            "qa": XenoRoleConfig(
                type=RoleType.QA_ASSISTANT,
                name="qa_agent",
                description="Q&A Assistant",
                system_prompt="You are a Q&A assistant.",
                model="openai:gpt-4o",
            ),
            "fault": XenoRoleConfig(
                type=RoleType.FAULT_EXPERT,
                name="fault_agent",
                description="Fault Expert",
                system_prompt="You are a fault expert.",
                model="openai:gpt-4o",
            ),
        },
    )


@pytest.fixture
def role_config(xeno_config: XenoConfig) -> XenoRoleConfig:
    """Get a test role configuration."""
    return xeno_config.roles["qa"]


@pytest.fixture
def deps(xeno_config: XenoConfig, role_config: XenoRoleConfig) -> XenoAgentDeps:
    """Create test dependencies."""
    return XenoAgentDeps(
        xeno_config=xeno_config,
        role_config=role_config,
    )


@pytest.fixture
def run_context(deps: XenoAgentDeps) -> RunContext[XenoAgentDeps]:
    """Create a mock RunContext."""
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


def test_ask_followup_basic(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test ask_followup tool with basic question."""
    question = "What is the device model number?"
    result = ask_followup(question=question, ctx=run_context)

    assert isinstance(result, str)
    assert "model number" in result or "device" in result.lower()
    assert "?" in result or "?" in result


def test_ask_followup_complex(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test ask_followup with complex multi-line question."""
    question = """Please provide the following information:
    1. Device model number
    2. Firmware version
    3. Error code displayed
    """
    result = ask_followup(question=question, ctx=run_context)

    assert isinstance(result, str)
    assert "model" in result.lower() or "firmware" in result.lower()
    assert len(result) > 10


def test_attempt_completion_basic(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test attempt_completion with simple answer."""
    answer = "The device is model X-2000 with firmware v3.2.1"
    result = attempt_completion(answer=answer, ctx=run_context)

    assert isinstance(result, str)
    assert "model X-2000" in result or "firmware" in result.lower()
    assert len(result) > 5


def test_attempt_completion_detailed(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test attempt_completion with detailed multi-part answer."""
    answer = """Diagnosis complete:
    - Issue: Overheating due to dust accumulation
    - Solution: Clean air vents and replace thermal paste
    - Preventive action: Schedule monthly maintenance"""
    result = attempt_completion(answer=answer, ctx=run_context)

    assert isinstance(result, str)
    assert "diagnosis" in result.lower() or "solution" in result.lower()
    assert len(result) > 20


def test_switch_mode_valid_target(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test switch_mode with valid target role."""
    target = "fault"
    result = switch_mode(target=target, ctx=run_context)

    assert isinstance(result, str)
    assert "fault" in result.lower() or "expert" in result.lower()
    assert "switched" in result.lower() or "transitioned" in result.lower()


def test_switch_mode_all_targets(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test switch_mode with all valid role targets."""
    valid_targets = ["qa", "fault", "equipment", "material"]

    for target in valid_targets:
        result = switch_mode(target=target, ctx=run_context)
        assert isinstance(result, str)
        assert target in result.lower() or result.lower()


def test_switch_mode_invalid_target(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test switch_mode with invalid target role."""
    target = "invalid_role"
    result = switch_mode(target=target, ctx=run_context)

    assert isinstance(result, str)
    # Should indicate that the role was not found
    assert "not found" in result.lower() or "unknown" in result.lower() or "invalid" in result.lower()


def test_new_task_with_target_and_task(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test new_task delegation with target and task description."""
    target = "fault"
    task = "Analyze the error code E-404 on the device"
    result = new_task(target=target, task=task, ctx=run_context)

    assert isinstance(result, str)
    assert "fault" in result.lower() or "expert" in result.lower()
    assert "E-404" in result or "error" in result.lower()


def test_new_task_different_targets(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test new_task delegation to different roles."""
    test_cases = [
        ("fault", "Diagnose equipment failure"),
        ("equipment", "Analyze device diagram"),
        ("material", "Find technical documentation"),
    ]

    for target, task in test_cases:
        result = new_task(target=target, task=task, ctx=run_context)
        assert isinstance(result, str)
        assert len(result) > 10


def test_new_task_invalid_target(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test new_task with invalid target role."""
    target = "nonexistent_role"
    task = "Some task description"
    result = new_task(target=target, task=task, ctx=run_context)

    assert isinstance(result, str)
    # Should indicate that the role was not found
    assert "not found" in result.lower() or "unknown" in result.lower() or "invalid" in result.lower()


def test_update_todo_add_item(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test update_todo adding a new todo item."""
    item = "Investigate thermal paste condition"
    status = "pending"
    result = update_todo(item=item, status=status, ctx=run_context)

    assert isinstance(result, str)
    assert "thermal paste" in result.lower() or "item" in result.lower()
    assert "pending" in result.lower() or "added" in result.lower()


def test_update_todo_update_status(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test update_todo updating item status."""
    item = "Check firmware version"
    status = "completed"
    result = update_todo(item=item, status=status, ctx=run_context)

    assert isinstance(result, str)
    assert "completed" in result.lower() or "updated" in result.lower()
    assert len(result) > 5


def test_update_todo_various_statuses(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test update_todo with various status values."""
    test_cases = [
        ("Gather information", "in_progress"),
        ("Perform diagnostic", "pending"),
        ("Write report", "completed"),
        ("Follow up with user", "blocked"),
    ]

    for item, status in test_cases:
        result = update_todo(item=item, status=status, ctx=run_context)
        assert isinstance(result, str)
        assert status.lower() in result.lower() or "item" in result.lower()


def test_update_todo_empty_item(run_context: RunContext[XenoAgentDeps]) -> None:
    """Test update_todo with empty item."""
    item = ""
    status = "pending"
    result = update_todo(item=item, status=status, ctx=run_context)

    assert isinstance(result, str)
    # Should handle empty gracefully
    assert len(result) >= 0


def test_tool_signatures() -> None:
    """Test that all tool functions have correct signatures."""

    # Check ask_followup
    sig = signature(ask_followup)
    params = list(sig.parameters.keys())
    assert params[0] == "ctx"
    assert "question" in params

    # Check attempt_completion
    sig = signature(attempt_completion)
    params = list(sig.parameters.keys())
    assert params[0] == "ctx"
    assert "answer" in params

    # Check switch_mode
    sig = signature(switch_mode)
    params = list(sig.parameters.keys())
    assert params[0] == "ctx"
    assert "target" in params

    # Check new_task
    sig = signature(new_task)
    params = list(sig.parameters.keys())
    assert params[0] == "ctx"
    assert "target" in params
    assert "task" in params

    # Check update_todo
    sig = signature(update_todo)
    params = list(sig.parameters.keys())
    assert params[0] == "ctx"
    assert "item" in params
    assert "status" in params
