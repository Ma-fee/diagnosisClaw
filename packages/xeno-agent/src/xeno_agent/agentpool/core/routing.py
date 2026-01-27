"""Routing tools for Xeno agent system.

This module provides PydanticAI-compatible tool functions for managing
agent interaction flow and delegation in the Xeno multi-agent system.

Tools:
- ask_followup: Request additional information from user
- attempt_completion: Signal that agent has completed its task
- switch_mode: Transition session to a different role
- new_task: Delegate a sub-task to another role
- update_todo: Update the session's internal todo list
"""

from __future__ import annotations

from pydantic_ai import RunContext

from xeno_agent.agentpool.core.deps import XenoAgentDeps


def ask_followup(ctx: RunContext[XenoAgentDeps], question: str) -> str:
    """Signal that the agent needs more information from the user.

    This tool is used when the agent requires additional context,
    clarification, or specific details to proceed with the task.

    Args:
        ctx: RunContext containing XenoAgentDeps
        question: The specific question or information request from the user

    Returns:
        A confirmation message indicating the question was presented

    Example:
        >>> ask_followup(ctx=ctx, question="What is the device model number?")
        "Asking user: What is the device model number?"
    """
    # Access deps for future implementation
    _ = ctx.deps

    # In a real implementation, this would:
    # 1. Store the question in session state
    # 2. Emit an event to the user interface
    # 3. Wait for user response
    # For now, return a formatted confirmation

    return f"Asking user: {question}"


def attempt_completion(ctx: RunContext[XenoAgentDeps], answer: str) -> str:
    """Signal that the agent has completed its task or answered the query.

    This tool indicates that the agent has successfully completed
    the requested task or provided the requested information.

    Args:
        ctx: RunContext containing XenoAgentDeps
        answer: The final answer or completion message

    Returns:
        A confirmation message indicating completion

    Example:
        >>> attempt_completion(ctx=ctx, answer="The device is model X-2000 with firmware v3.2.1")
        "Task completed: The device is model X-2000 with firmware v3.2.1"
    """
    # Access deps for future implementation
    _ = ctx.deps

    # In a real implementation, this would:
    # 1. Store the completion in session history
    # 2. Emit a completion event
    # 3. Mark task as complete
    # For now, return a formatted confirmation

    return f"Task completed: {answer}"


def switch_mode(ctx: RunContext[XenoAgentDeps], target: str) -> str:
    """Transition the current session to a different role in the Xeno system.

    This tool is used to switch from one agent role to another,
    preserving the conversation context. Valid targets are role IDs
    from the Xeno configuration (e.g., "qa", "fault", "equipment", "material").

    Args:
        ctx: RunContext containing XenoAgentDeps with access to configuration
        target: The role ID to switch to (e.g., "fault", "equipment")

    Returns:
        A confirmation message indicating the role transition

    Raises:
        ValueError: If the target role is not found in the configuration

    Example:
        >>> switch_mode(ctx=ctx, target="fault")
        "Switched to Fault Expert role"

    >>> switch_mode(ctx=ctx, target="equipment")
        "Switched to Equipment Expert role"
    """
    deps = ctx.deps

    # Validate that the target role exists in the configuration
    target_role = deps.xeno_config.get_role(target)

    if target_role is None:
        # Try to find a partial match or provide helpful error
        available_roles = list(deps.xeno_config.roles.keys())
        available_str = ", ".join(available_roles)
        return f"Cannot switch: Role '{target}' not found. Available roles: {available_str}"

    # In a real implementation, this would:
    # 1. Update the session's active role
    # 2. Emit a mode change event
    # 3. Prepare the new role's context

    role_name = target_role.name
    return f"Switched to {role_name} role (ID: {target})"


def new_task(ctx: RunContext[XenoAgentDeps], target: str, task: str) -> str:
    """Delegate a new sub-task to another role in the Xeno system.

    This tool enables inter-agent delegation where one agent assigns
    a specific task to another agent role. The target agent
    will execute the task independently.

    Args:
        ctx: RunContext containing XenoAgentDeps with access to agent pool
        target: The role ID to delegate to (e.g., "fault", "equipment", "material")
        task: A clear description of the task to delegate

    Returns:
        A confirmation message indicating the task was delegated

    Example:
        >>> new_task(ctx=ctx, target="fault", task="Analyze the error code E-404 on the device")
        "Delegated to Fault Expert: Analyze the error code E-404 on the device"

    >>> new_task(ctx=ctx, target="material", task="Find technical documentation for model X-2000")
        "Delegated to Material Assistant: Find technical documentation for model X-2000"
    """
    deps = ctx.deps

    # Validate that the target role exists in the configuration
    target_role = deps.xeno_config.get_role(target)

    if target_role is None:
        # Provide helpful error message with available roles
        available_roles = list(deps.xeno_config.roles.keys())
        available_str = ", ".join(available_roles)
        return f"Cannot delegate: Role '{target}' not found. Available roles: {available_str}"

    # In a real implementation, this would:
    # 1. Use deps.agent_pool to get the target agent
    # 2. Create a new session or delegate within current session
    # 3. Track the delegation relationship
    # 4. Emit a task delegation event

    role_name = target_role.name
    return f"Delegated to {role_name}: {task}"


def update_todo(ctx: RunContext[XenoAgentDeps], item: str, status: str) -> str:
    """Update the session's internal todo list.

    This tool allows agents to track progress on complex tasks
    by adding or updating todo items. Valid statuses include
    "pending", "in_progress", "completed", "blocked".

    Args:
        ctx: RunContext containing XenoAgentDeps
        item: The todo item description
        status: The status of the todo item (e.g., "pending", "in_progress", "completed")

    Returns:
        A confirmation message indicating the todo list was updated

    Example:
        >>> update_todo(ctx=ctx, item="Investigate thermal paste condition", status="pending")
        "Todo updated: [pending] Investigate thermal paste condition"

        >>> update_todo(ctx=ctx, item="Check firmware version", status="completed")
        "Todo updated: [completed] Check firmware version"
    """
    # Access deps for future implementation
    _ = ctx.deps

    # In a real implementation, this would:
    # 1. Access or create session's todo list
    # 2. Add or update the todo item
    # 3. Track timestamps for each status change
    # 4. Emit a todo update event

    # Validate common status values (case-insensitive)
    valid_statuses = ["pending", "in_progress", "completed", "blocked"]
    normalized_status = status.lower().replace("-", "_")

    # Provide guidance if status is unusual
    if normalized_status not in valid_statuses:
        valid_str = ", ".join(valid_statuses)
        warning = f" (Note: unusual status '{status}', valid statuses: {valid_str})"
    else:
        warning = ""

    return f"Todo updated: [{status}] {item}{warning}"
