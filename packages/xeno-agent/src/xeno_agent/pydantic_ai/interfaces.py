from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class AgentResult:
    data: str
    metadata: dict[str, Any]


@runtime_checkable
class AgentRuntime(Protocol):
    """Executes agent logic and handles routing."""

    async def invoke(self, agent_id: str, message: str, **kwargs: Any) -> AgentResult:
        """Invoke an agent directly."""
        ...

    async def delegate(self, target_agent: str, task: str, **kwargs: Any) -> AgentResult:
        """Delegate a task to another agent."""
        ...


@runtime_checkable
class StatePersistence(Protocol):
    """Saves and loads session state."""

    async def save_state(self, session_id: str, state: dict[str, Any]) -> None: ...

    async def load_state(self, session_id: str) -> dict[str, Any] | None: ...


@runtime_checkable
class ConfigLoader(Protocol):
    """Loads agent definitions."""

    def load_agent_config(self, agent_id: str) -> dict[str, Any]: ...

    def list_agents(self) -> list[str]: ...


@runtime_checkable
class WorkflowLoader(Protocol):
    """Loads workflow definitions."""

    def load_flow_config(self, flow_id: str) -> dict[str, Any]: ...


@runtime_checkable
class SkillLoader(Protocol):
    """Loads and renders capabilities."""

    def load_skill(self, skill_id: str) -> dict[str, Any]:
        """Load raw skill definition."""
        ...

    def render_skill(self, skill_id: str, context: dict[str, Any]) -> str:
        """Render skill template with context."""
        ...


@runtime_checkable
class ToolRegistry(Protocol):
    """Manages available tools."""

    def get_tool(self, tool_name: str) -> Any: ...

    def list_tools(self) -> list[str]: ...
