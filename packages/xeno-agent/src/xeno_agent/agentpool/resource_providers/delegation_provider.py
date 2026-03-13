"""Delegation provider for xeno-agent."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from agentpool import ChatMessage
from agentpool.agents.base_agent import BaseAgent
from agentpool.agents.context import AgentContext
from agentpool.agents.events import (
    SpawnSessionStart,
    StreamCompleteEvent,
    SubAgentEvent,
    ToolCallCompleteEvent,
    ToolCallStartEvent,
)
from agentpool.common_types import SupportsRunStream
from agentpool.delegation import Team, TeamRun
from agentpool.resource_providers import StaticResourceProvider
from agentpool.tools.exceptions import ToolError
from agentpool_config.context import CONFIG_DIR
from pydantic_ai import RunContext
from pydantic_ai.tools import ToolDefinition

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
        enabled_tools: list[str] | None = None,
    ) -> None:
        """Initialize the delegation provider.

        Args:
            name: The name of the provider.
            schemas: Optional dictionary mapping tool names to schema file paths.
                Expected keys: "new_task", "attempt_completion"
                Example: {"new_task": "/path/to/new_task_schema.yaml", "attempt_completion": "/path/to/attempt_completion_schema.json"}
                Paths are resolved relative to config directory using CONFIG_DIR context.
            enabled_tools: Optional list of tools to enable. If None or empty, all tools are enabled.
                Expected values: "new_task", "attempt_completion"
                Example: ["new_task"] for main agent, ["attempt_completion"] for subagent
        """
        super().__init__(name=name)

        # Extract schema paths from schemas dictionary
        new_task_schema = None
        attempt_completion_schema = None
        if schemas:
            if (new_task_schema_path := schemas.get("new_task")) is not None:
                # Resolve path using CONFIG_DIR context (RFC-0009 compliant)
                schema_path = Path(new_task_schema_path)
                if not schema_path.is_absolute():
                    config_dir = CONFIG_DIR.get()
                    if config_dir is not None:
                        schema_path = Path(str(config_dir)) / schema_path
                new_task_schema = load_tool_schema(str(schema_path))

            if (attempt_completion_schema_path := schemas.get("attempt_completion")) is not None:
                # Resolve path using CONFIG_DIR context (RFC-0009 compliant)
                schema_path = Path(attempt_completion_schema_path)
                if not schema_path.is_absolute():
                    config_dir = CONFIG_DIR.get()
                    if config_dir is not None:
                        schema_path = Path(str(config_dir)) / schema_path
                attempt_completion_schema = load_tool_schema(str(schema_path))

        # Load schema overrides for delegation tools
        # Pass full schema to create_tool
        # Check which tools should be enabled
        if enabled_tools is None or len(enabled_tools) == 0:
            # Enable all tools if not specified
            tools_to_enable = ["new_task", "attempt_completion"]
        else:
            tools_to_enable = enabled_tools

        # Add new_task tool if enabled
        if "new_task" in tools_to_enable:
            new_task_tool = self.create_tool(
                self.new_task,
                name_override=new_task_schema.get("name") if new_task_schema else None,
                description_override=new_task_schema.get("description") if new_task_schema else None,
                category="switch_mode",
                schema_override=new_task_schema,
            )
            new_task_tool.prepare = self.prepare_new_task
            self.add_tool(new_task_tool)

        # Add attempt_completion tool if enabled
        if "attempt_completion" in tools_to_enable:
            self.add_tool(
                self.create_tool(
                    self.attempt_completion,
                    name_override=attempt_completion_schema.get("name") if attempt_completion_schema else None,
                    description_override=attempt_completion_schema.get("description") if attempt_completion_schema else None,
                    category="other",
                    schema_override=attempt_completion_schema,
                ),
            )

    async def prepare_new_task(
        self,
        ctx: RunContext[AgentContext],
        tool_def: ToolDefinition,
    ) -> ToolDefinition:
        """Prepare new_task tool description dynamically.

        Args:
            ctx: Run context with AgentContext as deps
            tool_def: The tool definition to customize

        Returns:
            The customized tool definition
        """
        # Handle case where ctx.deps is None (e.g., during tool registration/setup)
        if not ctx.deps or not ctx.deps.pool:
            return tool_def

        pool = ctx.deps.pool
        current_agent_name = ctx.deps.node.name if ctx.deps.node else None

        # Strip existing # Available Modes: section from tool_def.description
        description = tool_def.description or ""
        if "# Available Modes:" in description:
            description = description.split("# Available Modes:")[0].strip()

        # Iterate pool.nodes, skipping the current agent
        modes_section = "\n\n# Available Modes:"
        for name, node in pool.nodes.items():
            if name == current_agent_name:
                continue

            # Appends available agents and their descriptions to the tool description
            node_description = getattr(node, "description", "") or ""
            modes_section += f"\n- {name}: {node_description}"

        tool_def.description = description + modes_section
        return tool_def

    async def _format_skills_instructions(
        self,
        skills_manager,
        skill_names: list[str],
    ) -> str:
        """Format skills as XML instructions for subagent context."""
        skill_sections = []

        for skill_name in skill_names:
            skill = skills_manager.get_skill(skill_name)
            if not skill:
                available = ", ".join(skills_manager.list_skills())
                raise ToolError(f"Skill '{skill_name}' not found. Available: {available}")

            instruction_content = skill.load_instructions()
            skill_base_path = str(skill.skill_path)

            # Try to make path relative
            try:
                project_root = Path.cwd()
                skill_rel_path = Path(skill_base_path).relative_to(project_root)
                skill_base_path = str(skill_rel_path)
            except ValueError:
                pass  # Keep absolute if can't make relative

            skill_sections.append(f'<skill-instruction name="{skill_name}" base="{skill_base_path}">\n{instruction_content}\n</skill-instructions>\n')

        if not skill_sections:
            return ""

        return "\n".join(skill_sections)

    async def new_task(
        self,
        ctx: AgentContext,
        mode: str,
        message: str,
        expected_output: str = "",
        load_skills: list[str] | None = None,
    ) -> str:
        """Delegate a task to another agent.

        Args:
            ctx: Agent context
            mode: The specialized mode for the new task
            message: The task description
            expected_output: Description of the expected output

        Returns:
            The result of the delegated task
        """
        # Handle parameter name compatibility: use RFC parameters if provided, otherwise use legacy parameters
        resolved_agent_name = mode
        resolved_task = message
        # resolved_expected_output = expected_output
        # Note: Use task_description (not message) to avoid name collision with StreamCompleteEvent.message

        if resolved_agent_name is None:
            raise ToolError("Either 'mode' or 'agent_name' parameter must be provided")
        if resolved_task is None:
            raise ToolError("Either 'message' or 'task' parameter must be provided")
        # if resolved_expected_output is None:
        # raise ToolError("'expected_output' parameter must be provided")

        # Type narrowing: after the check above, resolved_agent_name is guaranteed to be str
        target_agent: str = resolved_agent_name
        target_task: str = resolved_task
        # target_expected_output: str = resolved_expected_output

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

        # Fetch and format skill instructions
        skills_content = ""
        if load_skills:
            skills_manager = getattr(ctx.pool, "skills", None)
            if skills_manager:
                skills_content = await self._format_skills_instructions(skills_manager, load_skills)

        formatted_prompt = f"""<task>
{target_task}
</task>

<expected_output>
{expected_output}
</expected_output>"""
        # Format prompt with skills prepended
        if skills_content:
            formatted_prompt = f"{skills_content}\n\n" + formatted_prompt

        final_result = ""

        # Generate a unique session ID for this subagent session (RFC-0015)
        child_session_id = str(uuid4())
        parent_session_id = ctx.node.session_id
        tool_call_id = ctx.tool_call_id

        # Check if node supports streaming
        if not isinstance(node, SupportsRunStream):
            raise ToolError(f"Node {target_agent} does not support streaming")

        # try:
        # Run subagent stream
        stream = node.run_stream(formatted_prompt, deps=new_deps)

        # Emit SpawnSessionStart before streaming begins (RFC-0014)
        spawn_event = SpawnSessionStart(
            child_session_id=child_session_id,
            parent_session_id=parent_session_id or "",
            tool_call_id=tool_call_id,
            spawn_mechanism="task",
            source_name=target_agent,
            source_type=source_type,
            depth=current_depth + 1,
            description=f"# Task\n{target_task}\n\n# Expected Output\n{expected_output}",
            # metadata={
            #     "prompt": target_task[:201] if len(target_task) > 200 else target_task,
            # },
        )
        await ctx.events.emit_event(spawn_event)

        async for event in stream:
            match event:
                # Track when attempt_completion is called and stop subagent execution
                case ToolCallStartEvent(tool_name="attempt_completion", raw_input=args):
                    # Capture the 'result' parameter from tool input
                    final_result = str(args.get("result", ""))
                    # Stop subagent from continuing execution
                    break

                # Track when attempt_completion completes and capture final result
                case ToolCallCompleteEvent(tool_name="attempt_completion", tool_result=completion_result):
                    # Capture the final result from the completed tool call
                    final_result = str(completion_result) if completion_result else ""
                    await ctx.events.emit_event(
                        SubAgentEvent(
                            source_name=target_agent,
                            source_type=source_type,
                            event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                            child_session_id=child_session_id,
                        ),
                    )
                    # Stop subagent from continuing execution
                    break

                # Handle SubAgentEvent wrapping - preserve child_session_id for navigation
                case SubAgentEvent(
                    source_name=source_name,
                    source_type=source_type,
                    event=inner_event,
                    child_session_id=inner_child_session_id,
                ):
                    nested_event = SubAgentEvent(
                        source_name=source_name,
                        source_type=source_type,
                        event=inner_event,
                        child_session_id=inner_child_session_id or child_session_id,
                    )
                    await ctx.events.emit_event(nested_event)

                # Capture final result from StreamCompleteEvent if attempt_completion wasn't used
                case StreamCompleteEvent(message=final_message):  # type: ignore[reportAssignmentType, reportAttributeAccessIssue]
                    if final_message and final_message.content:  # type: ignore[reportAttributeAccessIssue]
                        final_result = str(final_message.content)  # type: ignore[reportAttributeAccessIssue]
                    await ctx.events.emit_event(
                        SubAgentEvent(
                            source_name=target_agent,
                            source_type=source_type,
                            event=StreamCompleteEvent(message=ChatMessage(content=final_result, role="assistant")),
                            child_session_id=child_session_id,
                        ),
                    )
                    # Stop subagent from continuing execution
                    break

                # Wrap other events with session tracking (RFC-0015)
                case _:
                    subagent_event = SubAgentEvent(
                        source_name=target_agent,
                        source_type=source_type,
                        event=event,
                        depth=current_depth + 1,
                        child_session_id=child_session_id,
                    )
                    await ctx.events.emit_event(subagent_event)
        # except (GeneratorExit, asyncio.CancelledError):
        #     # Stream was cancelled by break statement, which is expected behavior
        #     # when attempt_completion is detected. This prevents cleanup code from
        #     # running in a different async task context.
        #     pass

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
