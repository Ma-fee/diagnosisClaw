"""
Dynamic tool generation from configuration.
"""

from typing import Any

from crewai.tools import BaseTool
from pydantic import Field, create_model

from .tools.mcp_tool import GenericMCPTool


class DynamicToolFactory:
    """Factory for creating tools from configuration."""

    @staticmethod
    def create_tool(name: str, config: dict[str, Any], implementation_class: type[BaseTool] | None = None) -> BaseTool:
        """
        Create a tool instance.

        Args:
            name: Tool name
            config: Tool configuration
            implementation_class: Optional Python class implementing the tool logic
        """
        description = config.get("description", "")
        parameters = config.get("parameters", {})

        # 1. Generate Pydantic args_schema if parameters are defined
        args_schema = None
        if parameters:
            fields = {}
            for param_name, param_def in parameters.items():
                # Map simple types to Python types
                type_map = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}
                py_type = type_map.get(param_def.get("type", "string"), str)

                # Create Field definition
                default = param_def.get("default", ...)
                desc = param_def.get("description", "")
                fields[param_name] = (py_type, Field(default=default, description=desc))

            args_schema = create_model(f"{name}Schema", **fields)

        # 2. Check source type
        source = config.get("source", "python")

        if source == "mcp":
            mcp_config = config.get("mcp", {})
            tool = GenericMCPTool(
                name=name,
                description=description,
                mcp_url=mcp_config.get("url"),
                mcp_tool_name=mcp_config.get("tool_name"),
            )
            if args_schema:
                tool.args_schema = args_schema
            return tool

        # 3. Default to Python implementation
        if implementation_class:
            tool = implementation_class()
            tool.name = name
            tool.description = description
            if args_schema:
                tool.args_schema = args_schema
            return tool

        # 4. Fallback: try to load python class from config strings if provided
        module_name = config.get("python_module")
        class_name = config.get("python_class")

        if module_name and class_name:
            import importlib

            module = importlib.import_module(module_name)
            tool_class = getattr(module, class_name)
            tool = tool_class()
            tool.name = name
            tool.description = description
            # Don't override args_schema if the class already defines it, unless needed
            # But usually custom classes define their own. We'll skip forcing it for now.
            return tool

        raise NotImplementedError(f"Cannot create tool {name}: No implementation found.")
