"""Toolset for delegation tools."""

from __future__ import annotations

from typing import override

from agentpool.resource_providers import StaticResourceProvider

from .delegation_provider import XenoDelegationProvider


class XenoDelegationToolset(StaticResourceProvider):
    """Toolset providing delegation capabilities."""

    def __init__(self, name: str = "delegation") -> None:
        """Initialize the delegation toolset.

        Args:
            name: The name of the toolset.
        """
        super().__init__(name=name)
        self._provider: XenoDelegationProvider = XenoDelegationProvider(name=name)

    @override
    async def get_tools(self):
        """Get tools from the delegation provider."""
        return await self._provider.get_tools()
