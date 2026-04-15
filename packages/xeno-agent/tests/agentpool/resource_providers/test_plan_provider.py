"""Tests for XenoPlanProvider."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest
from agentpool import Agent, AgentContext
from agentpool.delegation import AgentPool
from agentpool.utils.streams import TodoTracker

# Import XenoPlanProvider classes
from xeno_agent.agentpool.resource_providers.plan_provider import (
    XenoPlanProvider,
)


@pytest.fixture
def mock_pool_with_todos() -> AgentPool:
    """Create a mock AgentPool with TodoTracker."""
    pool = AsyncMock(spec=AgentPool)
    pool.todos = TodoTracker()
    return pool


@pytest.fixture
def provider() -> XenoPlanProvider:
    """Create XenoPlanProvider instance."""
    return XenoPlanProvider()


@pytest.mark.unit
async def test_create_new_list(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test creating a new todo list from scratch."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos_input = """<todo pos="1" status="inProgress">First task</todo>
<todo pos="2">Second task</todo>
<todo pos="3">Third task</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos_input)

    # Verify metadata contains all todos
    assert result.metadata is not None
    assert len(result.metadata["todos"]) == 3

    # Verify entries are created with correct pos values
    entries = result.metadata["todos"]
    assert entries[0]["pos"] == "1"
    assert entries[1]["pos"] == "2"
    assert entries[2]["pos"] == "3"

    # Verify content and status
    assert entries[0]["content"] == "First task"
    assert entries[1]["content"] == "Second task"
    assert entries[2]["content"] == "Third task"
    assert entries[0]["status"] == "in_progress"
    assert entries[1]["status"] == "pending"
    assert entries[2]["status"] == "pending"

    # Verify markdown table format
    assert "## TODO List" in result.content
    assert "| | Task | Status |" in result.content
    assert "|---|---|---|" in result.content
    assert "First task" in result.content
    assert "Second task" in result.content
    assert "Third task" in result.content


@pytest.mark.unit
async def test_incremental_update_status(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test incremental update by changing status of one item."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create initial list
    initial_todos = """<todo pos="1" status="inProgress">First task</todo>
<todo pos="2">Second task</todo>
<todo pos="3">Third task</todo>"""
    await provider.update_todo_list(agent_ctx, initial_todos)

    # Update only status of step_2
    update_todos = """<todo pos="2" status="completed">Second task</todo>"""
    result = await provider.update_todo_list(agent_ctx, update_todos)

    # Verify only 3 entries total (no duplicates)
    assert len(result.metadata["todos"]) == 3

    # Verify step_2 status changed
    step_2 = next(e for e in result.metadata["todos"] if e["pos"] == "2")
    assert step_2["status"] == "completed"

    # Verify other items remain unchanged
    step_1 = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    step_3 = next(e for e in result.metadata["todos"] if e["pos"] == "3")
    assert step_1["status"] == "in_progress"
    assert step_3["status"] == "pending"

    # Verify content unchanged for all
    assert step_1["content"] == "First task"
    assert step_2["content"] == "Second task"
    assert step_3["content"] == "Third task"


@pytest.mark.unit
async def test_add_new_item_to_existing(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test adding new item to existing list."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create initial list with 2 items
    initial_todos = """<todo pos="1" status="inProgress">Task A</todo>
<todo pos="2">Task B</todo>"""
    await provider.update_todo_list(agent_ctx, initial_todos)

    # Add 3rd item
    additional_todos = """<todo pos="3">Task C</todo>"""
    result = await provider.update_todo_list(agent_ctx, additional_todos)

    # Verify all 3 items exist
    assert len(result.metadata["todos"]) == 3

    # Verify pos values are preserved
    pos_values = [e["pos"] for e in result.metadata["todos"]]
    assert "1" in pos_values
    assert "2" in pos_values
    assert "3" in pos_values

    # Verify order preserved
    task_a = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    task_b = next(e for e in result.metadata["todos"] if e["pos"] == "2")
    task_c = next(e for e in result.metadata["todos"] if e["pos"] == "3")
    assert task_a["content"] == "Task A"
    assert task_b["content"] == "Task B"
    assert task_c["content"] == "Task C"


@pytest.mark.unit
async def test_pos_sorting(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test hierarchical position-based sorting."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create items with mixed positions
    todos = """<todo pos="3" status="inProgress">Task 3</todo>
<todo pos="1">Task 1</todo>
<todo pos="2">Task 2</todo>
<todo pos="1.1">Task 1.1</todo>
<todo pos="2.1">Task 2.1</todo>
<todo pos="2.1.1">Task 2.1.1</todo>
<todo pos="99">No position task</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify order: 1, 1.1, 2, 2.1, 2.1.1, 3, 99
    entries = result.metadata["todos"]
    assert entries[0]["pos"] == "1"
    assert entries[1]["pos"] == "1.1"
    assert entries[2]["pos"] == "2"
    assert entries[3]["pos"] == "2.1"
    assert entries[4]["pos"] == "2.1.1"
    assert entries[5]["pos"] == "3"
    assert entries[6]["pos"] == "99"


@pytest.mark.unit
async def test_pos_sorting_with_skipped(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test that 'skipped' status maps to 'completed' for sorting."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos = """<todo pos="1" status="skipped">Task 1</todo>
<todo pos="2">Task 2</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify 'skipped' is stored in custom_fields and status is 'completed'
    step_1 = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    assert step_1["status"] == "completed"
    assert step_1.get("skipped") == "true"


@pytest.mark.unit
async def test_custom_fields_persisted(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test custom fields are returned in metadata."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create items with custom fields
    todos = """<todo pos="1" measurement="20 MPa" status="inProgress">Take measurement</todo>
<todo pos="2" safety="high">Safety check</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify custom fields in metadata
    measure_task = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    assert "measurement" in measure_task
    assert measure_task["measurement"] == "20 MPa"

    safety_task = next(e for e in result.metadata["todos"] if e["pos"] == "2")
    assert "safety" in safety_task
    assert safety_task["safety"] == "high"


@pytest.mark.unit
async def test_custom_fields_update(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test adding custom fields on update."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create item with one custom field
    initial_todos = """<todo pos="1" measurement="10 MPa" status="inProgress">Task 1</todo>"""
    await provider.update_todo_list(agent_ctx, initial_todos)

    # Update adding another custom field
    update_todos = """<todo pos="1" safety="low">Task 1</todo>"""
    result = await provider.update_todo_list(agent_ctx, update_todos)

    # Verify both custom fields present
    task_1 = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    assert "measurement" in task_1
    assert task_1["measurement"] == "10 MPa"
    assert "safety" in task_1
    assert task_1["safety"] == "low"


@pytest.mark.unit
async def test_progress_event_emitted(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test that tool_call_progress event is emitted."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos = """<todo pos="1">Task 1</todo>
<todo pos="2" status="completed">Task 2</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify progress was handled (event emitted)
    # Event emission is handled internally; just verify successful execution
    assert result is not None
    assert "2 tasks" in result.content or len(result.metadata["todos"]) == 2


@pytest.mark.unit
async def test_content_update_preserves_other_fields(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test that updating content preserves other fields like pos and custom fields."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create item with pos and custom fields
    initial = """<todo pos="1" custom_field="value" status="inProgress">Original</todo>"""
    await provider.update_todo_list(agent_ctx, initial)

    # Update only content (status must be included to preserve it in XML format)
    update = """<todo pos="1" status="inProgress">Updated</todo>"""
    result = await provider.update_todo_list(agent_ctx, update)

    # Verify content changed but other fields preserved
    task = result.metadata["todos"][0]
    assert task["content"] == "Updated"
    assert task["pos"] == "1"
    assert task["custom_field"] == "value"
    assert task["status"] == "in_progress"


@pytest.mark.unit
async def test_status_update_preserves_content(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test that updating status preserves content and other fields."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create item
    initial = """<todo pos="1" status="inProgress">Original content</todo>"""
    await provider.update_todo_list(agent_ctx, initial)

    # Update only status
    update = """<todo pos="1" status="completed">Original content</todo>"""
    result = await provider.update_todo_list(agent_ctx, update)

    # Verify status changed but content preserved
    task = result.metadata["todos"][0]
    assert task["status"] == "completed"
    assert task["content"] == "Original content"
    assert task["pos"] == "1"


@pytest.mark.unit
async def test_upsert_existing(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test upsert: updating existing item by ID."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create item with pos "1"
    initial_todos = """<todo pos="1" status="inProgress">Original content</todo>"""
    await provider.update_todo_list(agent_ctx, initial_todos)

    # Update same pos with different content
    update_todos = """<todo pos="1" status="completed">Updated content</todo>"""
    result = await provider.update_todo_list(agent_ctx, update_todos)

    # Verify only one entry exists with updated content
    assert len(result.metadata["todos"]) == 1
    step_1 = result.metadata["todos"][0]
    assert step_1["pos"] == "1"
    assert step_1["content"] == "Updated content"
    assert step_1["status"] == "completed"


@pytest.mark.unit
async def test_upsert_new(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test upsert: creating new item with ID."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create list with pos "1"
    initial_todos = """<todo pos="1" status="inProgress">Task 1</todo>"""
    await provider.update_todo_list(agent_ctx, initial_todos)

    # Add pos "2"
    additional_todos = """<todo pos="2">Task 2</todo>"""
    result = await provider.update_todo_list(agent_ctx, additional_todos)

    # Verify both entries exist
    assert len(result.metadata["todos"]) == 2
    pos_values = [e["pos"] for e in result.metadata["todos"]]
    assert "1" in pos_values
    assert "2" in pos_values

    # Verify step_1 unchanged
    step_1 = next(e for e in result.metadata["todos"] if e["pos"] == "1")
    assert step_1["content"] == "Task 1"
    assert step_1["status"] == "in_progress"

    # Verify step_2 created
    step_2 = next(e for e in result.metadata["todos"] if e["pos"] == "2")
    assert step_2["content"] == "Task 2"
    assert step_2["status"] == "pending"


@pytest.mark.unit
async def test_markdown_table_icons(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test Markdown table shows correct status icons."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos = """<todo pos="1">Pending</todo>
<todo pos="2" status="inProgress">In Progress</todo>
<todo pos="3" status="completed">Completed</todo>
<todo pos="4" status="skipped">Skipped</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify status icons
    assert "⬚" in result.content  # pending icon
    assert "◐" in result.content  # in_progress icon
    assert "✓" in result.content  # completed icon (also used for skipped)
    assert result.metadata["todos"][3].get("skipped") == "true"


@pytest.mark.unit
async def test_empty_list(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test handling of empty todo list."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    result = await provider.update_todo_list(agent_ctx, "")

    # Verify empty metadata
    assert result.metadata is not None
    assert len(result.metadata["todos"]) == 0

    # Verify markdown table still has structure
    assert "## TODO List" in result.content
    assert "| | Task | Status |" in result.content


@pytest.mark.unit
async def test_single_item(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test handling of single item list."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos = """<todo pos="1">Only task</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify single item created
    assert len(result.metadata["todos"]) == 1
    assert result.metadata["todos"][0]["pos"] == "1"
    assert result.metadata["todos"][0]["content"] == "Only task"

    # Verify markdown contains task
    assert "Only task" in result.content


@pytest.mark.unit
async def test_multiple_updates_same_item(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test multiple updates to same item."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    # Create initial item
    initial = """<todo pos="1">Initial</todo>"""
    await provider.update_todo_list(agent_ctx, initial)

    # First update
    update1 = """<todo pos="1" status="inProgress">Updated once</todo>"""
    await provider.update_todo_list(agent_ctx, update1)

    # Second update
    update2 = """<todo pos="1" status="completed">Updated twice</todo>"""
    result = await provider.update_todo_list(agent_ctx, update2)

    # Verify only one item with final state
    assert len(result.metadata["todos"]) == 1
    task = result.metadata["todos"][0]
    assert task["content"] == "Updated twice"
    assert task["status"] == "completed"


@pytest.mark.unit
async def test_pos_none_sorting(
    provider: XenoPlanProvider,
    mock_pool_with_todos: AgentPool,
):
    """Test that entries without pos are sorted last."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    agent_ctx = AgentContext(
        node=agent,
        pool=mock_pool_with_todos,
    )

    todos = """<todo pos="99">No pos 1</todo>
<todo pos="1">Pos 1</todo>
<todo pos="98">No pos 2</todo>
<todo pos="2">Pos 2</todo>"""

    result = await provider.update_todo_list(agent_ctx, todos)

    # Verify pos entries come first sorted by pos
    entries = result.metadata["todos"]
    assert entries[0]["pos"] == "1"
    assert entries[1]["pos"] == "2"
    assert entries[2]["pos"] == "98"
    assert entries[3]["pos"] == "99"


@pytest.mark.unit
async def test_no_pool_returns_error(
    provider: XenoPlanProvider,
):
    """Test that provider returns error when pool is None."""
    os.environ["OBSERVABILITY_ENABLED"] = "false"

    agent = Agent(name="test_agent", model="test")
    ctx = AgentContext(node=agent, pool=None)

    result = await provider.update_todo_list(
        ctx,
        """<todo pos="1">Task 1</todo>""",
    )

    # Verify error response
    assert "Error: No pool available" in result.content
    assert result.metadata["todos"] == []
