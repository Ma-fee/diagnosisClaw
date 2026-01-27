"""Delegation provider for xeno-agent."""

from __future__ import annotations

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

if TYPE_CHECKING:
    pass


MAX_DELEGATION_DEPTH = 5


class XenoDelegationProvider(StaticResourceProvider):
    """Provider for delegation tools."""

    def __init__(self, name: str = "delegation") -> None:
        """Initialize the delegation provider.

        Args:
            name: The name of the provider.
        """
        super().__init__(name=name)
        self.add_tool(self.create_tool(self.new_task, category="other"))
        self.add_tool(self.create_tool(self.attempt_completion, category="other"))

    async def new_task(
        self,
        ctx: AgentContext,
        agent_name: str,
        task: str,
        expected_output: str,
    ) -> str:
        """Delegate a task to another agent.

        Args:
            ctx: Agent context
            agent_name: Name of the agent to delegate to
            task: The task description
            expected_output: Description of the expected output

        Returns:
            The result of the delegated task
        """
        # Handle delegation depth
        current_depth = 0
        if isinstance(ctx.data, dict):
            current_depth = int(ctx.data.get("delegation_depth", 0))

        if current_depth >= MAX_DELEGATION_DEPTH:
            return f"Error: Max delegation depth ({MAX_DELEGATION_DEPTH}) reached."

        # Get agent from pool
        if ctx.pool is None:
            raise ToolError("No agent pool available")

        if agent_name not in ctx.pool.nodes:
            available = ", ".join(ctx.pool.nodes.keys())
            return f"Error: Agent '{agent_name}' not found. Available: {available}"

        node = ctx.pool.nodes[agent_name]

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

        # Format prompt
        formatted_prompt = f"<task>{task}</task>\n<expected_output>{expected_output}</expected_output>"

        final_result = ""

        # Check if node supports streaming
        if not isinstance(node, SupportsRunStream):
            raise ToolError(f"Node {agent_name} does not support streaming")

        # Run subagent stream
        stream = node.run_stream(formatted_prompt, deps=new_deps)

        async for event in stream:
            # Intercept attempt_completion
            if isinstance(event, ToolCallStartEvent) and event.tool_name == "attempt_completion":
                # Capture result and stop execution
                args = event.raw_input
                # Result might be in 'result' arg
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
                    source_name=agent_name,
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
