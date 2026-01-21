import inspect
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import create_model


class AnthropicSkillLoader:
    """Loads skill definitions from Anthropic-style XML files."""

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)

    def load_skill(self, skill_id: str) -> dict[str, Any]:
        """Load raw skill definition from XML."""
        xml_path = self.base_path / f"{skill_id}.xml"
        if not xml_path.exists() and not skill_id.endswith(".xml"):
            # Try with .xml suffix if not present
            xml_path = self.base_path / f"{skill_id}.xml"

        if not xml_path.exists():
            raise FileNotFoundError(f"Skill file not found: {xml_path}")

        tree = ET.parse(xml_path)  # noqa: S314
        root = tree.getroot()

        if root.tag != "skill_definition":
            raise ValueError(f"Invalid skill definition in {xml_path}")

        name = root.findtext("name", "")
        description = root.findtext("description", "")

        parameters = []
        params_node = root.find("parameters")
        if params_node is not None:
            parameters.extend(
                {
                    "name": param.get("name"),
                    "type": param.get("type"),
                    "required": param.get("required") == "true",
                    "description": param.findtext("description", ""),
                }
                for param in params_node.findall("parameter")
            )

        return {"name": name, "description": description, "parameters": parameters, "raw_xml": ET.tostring(root, encoding="unicode")}

    def render_skill(self, skill_id: str, context: dict[str, Any] | None = None) -> str:
        """Render skill definition as XML string."""
        skill_data = self.load_skill(skill_id)
        return skill_data["raw_xml"]


class SkillRegistry:
    """Registry for mapping skill names to executable Python functions."""

    def __init__(self):
        self.registry: dict[str, Callable] = {}

    def register(self, skill_name: str, func: Callable, expected_params: list[str] | dict[str, str] | None = None):
        """Register a function as a skill and validate its signature."""
        if expected_params:
            sig = inspect.signature(func)
            func_params = sig.parameters

            missing_params = []
            if isinstance(expected_params, list | dict):
                missing_params.extend(param_name for param_name in expected_params if param_name not in func_params)

            if missing_params:
                # Create a dynamic model to trigger a real ValidationError
                fields: dict[str, Any] = dict.fromkeys(missing_params, (Any, ...))
                model = create_model("Parameter mismatch", **fields)
                model()  # Missing required fields

        self.registry[skill_name] = func

    def get(self, skill_name: str) -> Callable:
        """Retrieve a registered skill function."""
        if skill_name not in self.registry:
            raise KeyError(f"Skill '{skill_name}' not found in registry")
        return self.registry[skill_name]
