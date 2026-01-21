"""
Configuration loader for agents, tools, and flows.
"""

from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    def __init__(self, config_root: str):
        self.config_root = Path(config_root)
        self.roles_dir = self.config_root / "roles"
        self.tools_dir = self.config_root / "tools"
        self.flow_dir = self.config_root / "flow"

    def load_role_config(self, role_name: str) -> dict[str, Any]:
        """Load role configuration from YAML."""
        config_path = self.roles_dir / f"{role_name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Role configuration not found: {config_path}")

        with config_path.open("r") as f:
            return yaml.safe_load(f)

    def load_tool_config(self, tool_name: str) -> dict[str, Any]:
        """Load tool configuration from YAML."""
        config_path = self.tools_dir / f"{tool_name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Tool configuration not found: {config_path}")

        with config_path.open("r") as f:
            return yaml.safe_load(f)

    def load_flow_config(self, flow_name: str) -> dict[str, Any]:
        """Load flow configuration from YAML."""
        config_path = self.flow_dir / f"{flow_name}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Flow configuration not found: {config_path}")

        with config_path.open("r") as f:
            return yaml.safe_load(f)

    def list_available_roles(self) -> list[str]:
        """List all available roles."""
        return [f.stem for f in self.roles_dir.glob("*.yaml")]

    def list_available_tools(self) -> list[str]:
        """List all available tools."""
        return [f.stem for f in self.tools_dir.glob("*.yaml")]

    def list_available_flows(self) -> list[str]:
        """List all available flows."""
        return [f.stem for f in self.flow_dir.glob("*.yaml")]
