"""
Decorator for configuring tools from YAML files.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import yaml
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, create_model

T = TypeVar("T", bound=type[BaseTool])

# Default config path - in a real app this might be configurable via env or singleton
# Path: .../xeno-agent/src/xeno_agent/core/tool_decorator.py
# 4 parents: core -> xeno_agent -> src -> xeno-agent
DEFAULT_TOOL_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config" / "tools"


def configured_tool(tool_name: str, config_dir: Path = DEFAULT_TOOL_CONFIG_DIR) -> Callable[[T], type[T]]:
    """
    Decorator to configure a tool class from a YAML configuration file.

    Args:
        tool_name: The name of the tool (matches the YAML filename without extension).
        config_dir: Directory containing tool configurations.

    Returns:
        A decorator function that takes the tool class and returns a configured subclass
    """

    def decorator(cls: T) -> type[T]:
        config_path = config_dir / f"{tool_name}.yaml"
        if not config_path.exists():
            # Fallback or warning? For now, raise to be explicit
            raise FileNotFoundError(f"Tool config not found at {config_path}")

        with config_path.open("r") as f:
            config = yaml.safe_load(f)

        # 1. Generate args_schema if parameters are defined
        parameters = config.get("parameters", {})
        args_schema: type[BaseModel] | None = None
        if parameters:
            fields: dict[str, tuple[type, Field]] = {}
            for param_name, param_def in parameters.items():
                # Map simple types to Python types
                type_map: dict[str, type] = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}
                py_type = type_map.get(param_def.get("type", "string"), str)

                # Create Field definition
                default_val = param_def.get("default", ...)
                desc = param_def.get("description", "")

                # Handle required fields (no default) vs optional
                if default_val == ...:
                    fields[param_name] = (py_type, Field(..., description=desc))
                else:
                    fields[param_name] = (py_type, Field(default=default_val, description=desc))

            # Create the schema model
            args_schema = create_model(f"{cls.__name__}Input", **fields)

        # 2. Prepare class attributes and annotations for subclassing
        # Pydantic requires type annotations when overriding fields
        class_attrs: dict[str, Any] = {
            "name": config.get("name", tool_name),
            "description": config.get("description", ""),
            "__module__": cls.__module__,
            "__annotations__": {
                "name": str,
                "description": str,
            },
        }

        if args_schema:
            class_attrs["args_schema"] = args_schema
            class_attrs["__annotations__"]["args_schema"] = type[BaseModel] | None

        # 3. Create a new class inheriting from the decorated class
        return type(cls.__name__, (cls,), class_attrs)

    return decorator
