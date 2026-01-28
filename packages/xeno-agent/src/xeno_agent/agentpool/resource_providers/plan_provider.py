"""Plan provider for Xeno agent with custom todo list support.

Implements incremental todo list updates with custom ID support,
position-based sorting, and custom field persistence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, cast, override

from agentpool.agents.context import AgentContext
from agentpool.agents.events import TextContentItem
from agentpool.resource_providers import ResourceProvider
from agentpool.resource_providers.plan_provider import PlanEntry
from agentpool.tools.base import ToolResult
from agentpool.utils.streams import TodoEntry, TodoStatus, TodoTracker
from defusedxml.ElementTree import ParseError, fromstring

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agentpool.tools.base import Tool


logger = logging.getLogger(__name__)


STATUS_ICONS = {"pending": "⬚", "in_progress": "◐", "completed": "✓", "skipped": "⊘"}

# Extended status type that includes "skipped"
XenoTodoStatus = Literal["pending", "in_progress", "completed", "skipped"]


@dataclass
class XenoTodoEntry(TodoEntry):
    """Extended TodoEntry with position and custom fields.

    Adds position tracking and custom metadata to base TodoEntry
    for Xeno-specific todo list management.
    """

    pos: str | None = None
    """Optional position/sort order (e.g., '1', '1.1')."""

    custom_fields: dict[str, Any] = field(default_factory=dict)
    """Custom fields like 'measurement', 'safety', etc."""


def _map_status(status: str | None) -> TodoStatus:
    """Map XML status attribute to TodoStatus.

    Args:
        status: Status string from XML (inProgress, completed, skipped, or None)

    Returns:
        Valid TodoStatus value
    """
    if status == "inProgress":
        return "in_progress"
    if status == "completed":
        return "completed"
    if status == "skipped":
        return "completed"
    return "pending"  # Default (notStarted)


class XenoPlanProvider(ResourceProvider):
    """Provider for Xeno-specific todo list management.

    Provides incremental todo list updates with custom ID support,
    position-based sorting, and custom field persistence.
    """

    kind = "tools"

    def __init__(self, name: str | None = None, owner: str | None = None) -> None:
        """Initialize with optional name parameter.

        Args:
            name: Optional name for the provider (defaults to "xeno_plan").
            owner: Optional owner for the provider.
        """
        super().__init__(name=name or "xeno_plan", owner=owner)

    def _get_tracker(self, agent_ctx: AgentContext) -> TodoTracker | None:
        """Get the TodoTracker from the pool."""
        if agent_ctx.pool is not None:
            return agent_ctx.pool.todos
        return None

    @override
    async def get_tools(self) -> Sequence[Tool]:
        """Get Xeno plan management tools."""
        return [self.create_tool(self.update_todo_list, category="other")]

    def _sort_entries(self, entries: list[XenoTodoEntry]) -> list[XenoTodoEntry]:
        """Sort entries by pos field.

        Args:
            entries: List of entries to sort

        Returns:
            Sorted entries (entries with pos first, then without pos)
        """

        def sort_key(entry: XenoTodoEntry) -> tuple[bool, tuple[int, ...]]:
            # Entries with pos go first (True), without pos last (False)
            if entry.pos is None:
                return (True, (()))

            # Convert "1.2.3" to tuple (1, 2, 3) for proper sorting
            try:
                parts = tuple(int(p) for p in entry.pos.split("."))
            except (ValueError, AttributeError):
                # If pos is not numeric, treat it as 0
                return (False, (0,))
            else:
                return (False, parts)

        return sorted(entries, key=sort_key)

    async def _emit_plan_update(self, agent_ctx: AgentContext) -> None:
        """Emit plan update event."""
        tracker = self._get_tracker(agent_ctx)
        if tracker is None:
            return

        # Get XenoTodoEntry instances and convert to PlanEntry for event
        entries = [
            PlanEntry(
                content=entry.content,
                priority=entry.priority,
                status=entry.status,
            )
            for entry in tracker.entries
            if isinstance(entry, XenoTodoEntry)
        ]

        await agent_ctx.events.plan_updated(entries)

    async def update_todo_list(
        self,
        agent_ctx: AgentContext,
        todos: str,
        message: str | None = None,
    ) -> ToolResult:
        """Incrementally manage a TODO list by tracking only changes.

        Supports creation, status updates, and position-based sorting.
        Custom IDs and fields are preserved across updates.

        Args:
            agent_ctx: Agent execution context
            todos: XML string with one or more <todo> tags for incremental updates.
                   Each <todo> tag must have a 'pos' attribute.
            message: Optional message associated with update

        Returns:
            ToolResult with markdown table and metadata containing todos
        """
        tracker = self._get_tracker(agent_ctx)
        if tracker is None:
            return ToolResult(
                content="Error: No pool available for todo tracking",
                metadata={"todos": []},
            )

        # Wrap todos in root tag for XML parsing
        wrapped = f"<root>{todos}</root>"

        try:
            root = fromstring(wrapped)
        except ParseError as e:
            return ToolResult(
                content=f"Error parsing XML todos: {e}",
                metadata={"todos": []},
            )

        # Process each todo element
        for todo_elem in root.findall("todo"):
            # Extract required pos attribute
            pos = todo_elem.get("pos")
            if pos is None:
                continue  # Skip todos without pos (invalid per RFC)

            # Extract optional status attribute
            status_attr = todo_elem.get("status")

            # Extract tag text content as task description
            content = todo_elem.text or ""

            # Extract custom fields (other attributes beyond pos and status)
            custom_fields = {k: v for k, v in todo_elem.attrib.items() if k not in ("pos", "status")}

            # Handle "skipped" status - store in custom_fields
            if status_attr == "skipped":
                custom_fields["skipped"] = "true"

            # Search for existing entry by pos
            existing_entry: XenoTodoEntry | None = None
            for entry in tracker.entries:
                if isinstance(entry, XenoTodoEntry) and entry.pos == pos:
                    existing_entry = entry
                    break

            if existing_entry:
                # Update existing entry
                if content:
                    existing_entry.content = content
                existing_entry.status = cast(TodoStatus, _map_status(status_attr))  # type: ignore[arg-type]
                existing_entry.custom_fields.update(custom_fields)
            else:
                # Create new entry with pos as id
                new_entry = XenoTodoEntry(
                    id=pos,  # Use pos as unique identifier
                    content=content,
                    status=cast(TodoStatus, _map_status(status_attr)),  # type: ignore[arg-type]
                    pos=pos,
                    custom_fields=custom_fields,
                )
                # Add directly to tracker.entries to bypass ID generation
                # Cast to TodoEntry to satisfy type checker
                tracker.entries.append(cast(TodoEntry, new_entry))  # type: ignore[arg-type]

        # Sort entries by pos field (in-place modification)
        xeno_entries = [e for e in tracker.entries if isinstance(e, XenoTodoEntry)]
        # Cast back to satisfy list invariance
        # XenoTodoEntry extends TodoEntry but type checker doesn't handle list invariance
        tracker.entries[:] = cast(list[TodoEntry], self._sort_entries(xeno_entries))  # type: ignore[arg-type]

        # Emit plan update event
        await self._emit_plan_update(agent_ctx)

        # Build summary for user feedback
        entry_count = len(tracker.entries)
        title = f"Updated todo list with {entry_count} task"
        if entry_count != 1:
            title += "s"

        # Format as markdown table
        lines = ["## TODO List", ""]
        lines.append("| | Task | Status |")
        lines.append("|---|---|---|")

        for entry in tracker.entries:
            if isinstance(entry, XenoTodoEntry):
                icon = STATUS_ICONS.get(entry.status, "?")
                content = entry.content
                lines.append(f"| {icon} | {content} | {entry.status} |")

        plan_text = "\n".join(lines)

        # Emit progress
        await agent_ctx.events.tool_call_progress(
            title=title,
            items=[TextContentItem(text=plan_text)],
        )

        # Convert to list format for metadata (including custom fields)
        todos_list = []
        for e in tracker.entries:
            if isinstance(e, XenoTodoEntry):
                todo_dict = {
                    "id": e.id,
                    "content": e.content,
                    "status": e.status,
                }
                if e.pos is not None:
                    todo_dict["pos"] = e.pos
                if e.custom_fields:
                    todo_dict.update(e.custom_fields)
                todos_list.append(todo_dict)

        return ToolResult(content=plan_text, metadata={"todos": todos_list})
