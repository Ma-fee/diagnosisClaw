"""Dependencies for PydanticAI agents in Xeno system.

This module defines dependency injection pattern for Xeno agents,
following PydanticAI's RunContext convention for agent dependencies.

Dependencies are injected into agent tools and handlers to provide access to:
- Xeno configuration
- Agent pool for delegation
- Session management
- Tool registry
- Storage providers
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Self

    from agentpool.agents.context import AgentContext
    from agentpool.delegation import AgentPool
    from agentpool.storage import StorageManager
    from agentpool.tools import ToolManager

    from xeno_agent.agentpool.core.config import (
        RoleType,
        RoleTypeLiteral,
        XenoConfig,
        XenoRoleConfig,
    )


class XenoAgentDeps:
    """Dependencies for Xeno PydanticAI agents.

    This class provides dependencies that can be injected into PydanticAI
    agent tools and handlers via RunContext, following AgentPool pattern.

    Example:
        ```python
        @agent.tool
        async def get_diagnosis(
            fault_symptom: str,
            ctx: RunContext[XenoAgentDeps],
        ) -> str:
            deps = ctx.deps
            # Access configuration and agent pool
            config = deps.xeno_config
            pool = deps.agent_pool
            ...
        ```

    Attributes:
        xeno_config: The complete Xeno system configuration
        role_config: Configuration for current agent's role
        agent_pool: AgentPool instance for inter-agent delegation
        storage_manager: Storage manager for interaction tracking
        tool_manager: Tool manager for tool registration
    """

    def __init__(
        self,
        xeno_config: XenoConfig,
        role_config: XenoRoleConfig,
        agent_pool: AgentPool | None = None,
        storage_manager: StorageManager | None = None,
        tool_manager: ToolManager | None = None,
    ) -> None:
        """Initialize Xeno agent dependencies.

        Args:
            xeno_config: Complete Xeno system configuration
            role_config: Configuration for current agent's role
            agent_pool: Optional AgentPool for delegation
            storage_manager: Optional storage manager for tracking
            tool_manager: Optional tool manager
        """
        self._xeno_config = xeno_config
        self._role_config = role_config
        self._agent_pool = agent_pool
        self._storage_manager = storage_manager
        self._tool_manager = tool_manager

    @property
    def xeno_config(self) -> XenoConfig:
        """Get complete Xeno system configuration.

        Returns:
            The XenoConfig instance containing all 4 roles
        """
        return self._xeno_config

    @property
    def role_config(self) -> XenoRoleConfig:
        """Get configuration for current agent's role.

        Returns:
            The XenoRoleConfig for this specific agent role
        """
        return self._role_config

    @property
    def agent_pool(self) -> AgentPool | None:
        """Get AgentPool instance for delegation.

        The AgentPool allows delegating to other Xeno roles:
        - Q&A Assistant can delegate to Fault Expert
        - Fault Expert can delegate to Equipment Expert or Material Assistant
        - Equipment Expert can delegate to Material Assistant

        Returns:
            AgentPool instance or None if not configured
        """
        return self._agent_pool

    @property
    def storage_manager(self) -> StorageManager | None:
        """Get storage manager for interaction tracking.

        Returns:
            StorageManager instance or None if not configured
        """
        return self._storage_manager

    @property
    def tool_manager(self) -> ToolManager | None:
        """Get tool manager.

        Returns:
            ToolManager instance or None if not configured
        """
        return self._tool_manager

    async def __aenter__(self) -> Self:
        """Enter async context manager.

        Returns:
            Self for use in async with statements
        """
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """Exit async context manager.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred

        Returns:
            None to suppress exceptions, False to propagate
        """
        # Cleanup resources if needed
        if self._storage_manager is not None:
            await self._storage_manager.__aexit__(exc_type, exc_val, exc_tb)

        return None

    def get_other_role(self, role_id: str) -> XenoRoleConfig | None:
        """Get configuration for another role in the system.

        This is useful for delegation scenarios where one agent needs
        to reference another role's configuration.

        Args:
            role_id: The role identifier to look up (e.g., "qa", "fault")

        Returns:
            The XenoRoleConfig for the specified role, or None if not found
        """
        return self._xeno_config.get_role(role_id)

    def get_roles_by_type(self, role_type: RoleType | RoleTypeLiteral | str) -> list[XenoRoleConfig]:
        """Get all roles of a specific type.

        Args:
            role_type: The role type to filter by (e.g., RoleType.QA_ASSISTANT or "qa_assistant")

        Returns:
            List of XenoRoleConfig instances matching type
        """
        # XenoConfig.get_roles_by_type handles both RoleType enum and string
        return self._xeno_config.get_roles_by_type(role_type)

    def get_agent_context(self) -> AgentContext[Any] | None:
        """Get current agent context if available.

        This provides access to agent-specific state and execution context.

        Returns:
            AgentContext instance or None if not available
        """
        if self._agent_pool is not None:
            # The agent pool maintains context for active agents
            # This is a placeholder - actual implementation would need
            # to access the context from the agent pool
            return None

        return None
