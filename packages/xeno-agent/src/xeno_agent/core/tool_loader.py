from pathlib import Path
from typing import Any

import yaml
from crewai.tools import BaseTool

from xeno_agent.tool_factory import DynamicToolFactory
from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


class ToolLoader:
    """
    ToolLoader manages the loading of tools from configuration and external sources.

    Roles:
    1. Load tool descriptions for LLM context (load_tool_descriptions).
    2. Load executable tool instances for CrewAI agents (get_tool_instances).
    """

    def __init__(self, tools_dir: str = "packages/xeno-agent/config/tools/builtin"):
        # Support running from root or package dir
        self.tools_dir = Path(tools_dir)
        if not self.tools_dir.exists():
            # Try relative to package root if running as module
            self.tools_dir = Path(__file__).parent.parent.parent.parent / "config/tools/builtin"

        self._tool_configs: dict[str, dict[str, Any]] = {}
        self._tool_instances: dict[str, BaseTool] = {}
        self._loaded = False

    def load_tool_descriptions(self) -> dict[str, dict[str, Any]]:
        """
        Load tool descriptions for LLM context.

        Returns:
            Dict mapping tool names to their description dictionaries.
        """
        if not self._loaded:
            self._load_tools()

        descriptions = {}
        for name, config in self._tool_configs.items():
            descriptions[name] = {
                "name": config.get("name"),
                "description": config.get("description"),
                "parameters": config.get("parameters", {}),
                "metadata": config.get("metadata", {}),
            }
        return descriptions

    def get_tool_instances(self, tool_names: list[str] | None = None) -> list[BaseTool]:
        """
        Get executable tool instances.

        Args:
            tool_names: Optional list of tool names to retrieve. If None, returns all.

        Returns:
            List of BaseTool instances.
        """
        if not self._loaded:
            self._load_tools()

        if tool_names is None:
            return list(self._tool_instances.values())

        tools = []
        for name in tool_names:
            if name in self._tool_instances:
                tools.append(self._tool_instances[name])
            else:
                logger.warning(f"Requested tool '{name}' not found.")
        return tools

    def _load_tools(self) -> None:
        """Load all tools from configuration directory."""
        if not self.tools_dir.exists():
            logger.warning(f"Tools directory not found: {self.tools_dir}")
            return

        for tool_yaml in self.tools_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(tool_yaml.read_text())
                name = config.get("name")
                if not name:
                    continue

                self._tool_configs[name] = config

                # Create instance using factory
                try:
                    tool = DynamicToolFactory.create_tool(name, config)
                    self._tool_instances[name] = tool
                except Exception:
                    logger.exception(f"Failed to create tool instance for {name}")

            except Exception:
                logger.exception(f"Failed to load tool config {tool_yaml}")

        self._loaded = True
