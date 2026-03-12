"""QuestionForUser provider for asking questions to users in standard AgenticCoding."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from agentpool.resource_providers import ResourceProvider
from agentpool.resource_providers.base import ProviderKind
from agentpool_config.context import CONFIG_DIR

from xeno_agent.tools.question_for_user import question_for_user
from xeno_agent.utils.tool_schema import load_tool_schema

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agentpool.tools.base import Tool


class QuestionForUserProvider(ResourceProvider):
    """Provides question_for_user tool for agent-user interaction.

    This provider creates the question_for_user tool which allows
    agents to ask general questions to users, supporting
    schema_override/name_override/description_override parameters
    through YAML configuration.
    """

    kind: ProviderKind = "tools"

    def __init__(
        self,
        name: str = "question_for_user",
        schemas: dict[str, str] | None = None,
    ) -> None:
        """Initialize question_for_user provider.

        Args:
            name: The name of the provider (default: "question_for_user")
            schemas: Optional dictionary mapping tool names to schema file paths.
                Expected key: "question_for_user"
                Example: {"question_for_user": "path/to/schema.yaml"}
                Paths are resolved relative to config directory using CONFIG_DIR context.

        """
        super().__init__(name=name)

        # Extract schema path from schemas dictionary
        question_for_user_schema = None
        if schemas and (schema_path := schemas.get("question_for_user")) is not None:
            # Resolve path using CONFIG_DIR context (RFC-0009 compliant)
            schema_path_resolved = Path(schema_path)
            if not schema_path_resolved.is_absolute():
                config_dir = CONFIG_DIR.get()
                if config_dir is not None:
                    schema_path_resolved = Path(str(config_dir)) / schema_path_resolved
            question_for_user_schema = load_tool_schema(str(schema_path_resolved))

        self.question_for_user_schema = question_for_user_schema

    @override
    async def get_tools(self) -> Sequence[Tool]:
        """Get question_for_user tool.

        Returns:
            Sequence containing the question_for_user tool.
            The tool can be customized with schema_override/name_override/
            description_override parameters through create_tool().

        """
        return [
            self.create_tool(
                question_for_user,
                category="other",
                schema_override=self.question_for_user_schema,
            ),
        ]
