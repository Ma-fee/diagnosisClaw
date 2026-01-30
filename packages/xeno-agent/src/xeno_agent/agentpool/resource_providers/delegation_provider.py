"""Delegation provider for xeno-agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from agentpool.agents.base_agent import BaseAgent
from agentpool.agents.context import AgentContext
from agentpool.agents.events import (
    StreamCompleteEvent,
    SubAgentEvent,
    ToolCallStartEvent,
)
from agentpool.common_types import SupportsRunStream
from agentpool.delegation import Team, TeamRun
from agentpool.resource_providers import StaticResourceProvider
from agentpool.tools.exceptions import ToolError

from xeno_agent.utils.tool_schema import load_tool_schema

if TYPE_CHECKING:
    pass


MAX_DELEGATION_DEPTH = 5


class XenoDelegationProvider(StaticResourceProvider):
    """Provider for delegation tools."""

    def __init__(
        self,
        name: str = "delegation",
        schemas: dict[str, str] | None = None,
    ) -> None:
        """Initialize the delegation provider.

        Args:
            name: The name of the provider.
            schemas: Optional dictionary mapping tool names to schema file paths.
                Expected keys: "new_task", "attempt_completion"
                Example: {"new_task": "/path/to/new_task_schema.yaml", "attempt_completion": "/path/to/attempt_completion_schema.json"}
                Paths can be relative to this file's directory.
        """
        super().__init__(name=name)

        # Get the directory containing this file for resolving relative paths
        this_file_dir = Path(__file__).parent

        # Extract schema paths from schemas dictionary
        new_task_schema = None
        attempt_completion_schema = None
        if schemas:
            if (new_task_schema_path := schemas.get("new_task")) is not None:
                # Resolve path relative to this file if not absolute
                schema_path = Path(new_task_schema_path)
                if not schema_path.is_absolute():
                    schema_path = this_file_dir / schema_path
                new_task_schema = load_tool_schema(str(schema_path))

            if (attempt_completion_schema_path := schemas.get("attempt_completion")) is not None:
                # Resolve path relative to this file if not absolute
                schema_path = Path(attempt_completion_schema_path)
                if not schema_path.is_absolute():
                    schema_path = this_file_dir / schema_path
                attempt_completion_schema = load_tool_schema(str(schema_path))

        # Load schema overrides for delegation tools
        # Pass full schema to create_tool
        self.add_tool(
            self.create_tool(
                self.new_task,
                name_override=new_task_schema.get("name") if new_task_schema else None,
                description_override=new_task_schema.get("description") if new_task_schema else None,
                category="other",
                schema_override=new_task_schema,
            ),
        )

        self.add_tool(
            self.create_tool(
                self.attempt_completion,
                name_override=attempt_completion_schema.get("name") if attempt_completion_schema else None,
                description_override=attempt_completion_schema.get("description") if attempt_completion_schema else None,
                category="other",
                schema_override=attempt_completion_schema,
            ),
        )

    async def new_task(
        self,
        ctx: AgentContext,
        mode: str,
        task: str,
        expected_output: str,
    ) -> str:
        """Delegate a task to another agent.

        Args:
            ctx: Agent context
            mode: The specialized mode for the new task
            task: The task description
            expected_output: Description of the expected output

        Returns:
            The result of the delegated task
        """
        # Handle parameter name compatibility: use RFC parameters if provided, otherwise use legacy parameters
        resolved_agent_name = mode
        resolved_task = task
        resolved_expected_output = expected_output

        if resolved_agent_name is None:
            raise ToolError("Either 'mode' or 'agent_name' parameter must be provided")
        if resolved_task is None:
            raise ToolError("Either 'message' or 'task' parameter must be provided")
        if resolved_expected_output is None:
            raise ToolError("'expected_output' parameter must be provided")

        # Type narrowing: after the check above, resolved_agent_name is guaranteed to be str
        target_agent: str = resolved_agent_name
        target_task: str = resolved_task
        target_expected_output: str = resolved_expected_output

        # Handle delegation depth
        current_depth = 0
        if isinstance(ctx.data, dict):
            current_depth = int(ctx.data.get("delegation_depth", 0))

        if current_depth >= MAX_DELEGATION_DEPTH:
            return f"Error: Max delegation depth ({MAX_DELEGATION_DEPTH}) reached."

        # Get agent from pool
        if ctx.pool is None:
            raise ToolError("No agent pool available")

        if target_agent not in ctx.pool.nodes:
            available = ", ".join(ctx.pool.nodes.keys())
            return f"Error: Agent '{target_agent}' not found. Available: {available}"

        node = ctx.pool.nodes[target_agent]

        # Determine source type for events
        source_type: Literal["agent", "team_parallel", "team_sequential"] = "agent"
        if isinstance(node, Team):
            source_type = "team_parallel"
        elif isinstance(node, TeamRun):
            source_type = "team_sequential"
        elif isinstance(node, BaseAgent):
            source_type = "agent"

        # Prepare dependencies with incremented depth
        new_deps = {"delegation_depth": current_depth + 1}
        if isinstance(ctx.data, dict):
            new_deps = {**ctx.data, **new_deps}

        # Format prompt with task and expected output
        formatted_prompt = f"<task>{target_task}</task>\n<expected_output>{target_expected_output}</expected_output>"

        final_result = ""

        # Check if node supports streaming
        if not isinstance(node, SupportsRunStream):
            raise ToolError(f"Node {target_agent} does not support streaming")

        # Run subagent stream
        stream = node.run_stream(formatted_prompt, deps=new_deps)

        async for event in stream:
            # Intercept attempt_completion
            if isinstance(event, ToolCallStartEvent) and event.tool_name == "attempt_completion":
                # Capture the 'result' parameter from tool input
                args = event.raw_input
                final_result = str(args.get("result", ""))
                # Break the loop to stop consuming the stream
                break

                # Handle SubAgentEvent wrapping
            if isinstance(event, SubAgentEvent):
                nested_event = SubAgentEvent(
                    source_name=event.source_name,
                    source_type=event.source_type,
                    event=event.event,
                    depth=event.depth + current_depth + 1,
                )
                await ctx.events.emit_event(nested_event)
            else:
                # Wrap other events
                subagent_event = SubAgentEvent(
                    source_name=target_agent,
                    source_type=source_type,
                    event=event,
                    depth=current_depth + 1,
                )
                await ctx.events.emit_event(subagent_event)

            # Capture final result from StreamCompleteEvent if attempt_completion wasn't used
            if isinstance(event, StreamCompleteEvent) and not final_result:
                final_result = str(event.message.content) if event.message.content else ""

        return final_result

    async def attempt_completion(self, _ctx: AgentContext, result: str) -> str:
        """Complete the task and return the result.

        Args:
            _ctx: Agent context (unused)
            result: The result of the task

        Returns:
            The provided result
        """
        return result
