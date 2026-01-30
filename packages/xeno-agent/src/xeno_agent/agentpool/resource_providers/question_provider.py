"""Question provider for asking follow-up questions to users."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from agentpool.resource_providers import ResourceProvider
from agentpool.resource_providers.base import ProviderKind

from xeno_agent.tools.ask_followup_question import ask_followup_question
from xeno_agent.utils.tool_schema import load_tool_schema

if TYPE_CHECKING:
    from collections.abc import Sequence

    from agentpool.tools.base import Tool


class QuestionProvider(ResourceProvider):
    """Provides follow-up question tools for agent-user interaction.

    This provider creates the ask_followup_question tool which allows
    agents to ask questions to users with suggestions, supporting
    schema_override/name_override/description_override parameters
    through YAML configuration.
    """

    kind: ProviderKind = "tools"

    def __init__(self, name: str = "question", schemas: dict[str, str] | None = None) -> None:
        """Initialize question provider.

        Args:
            name: The name of the provider (default: "question")
            schemas: Optional dictionary mapping tool names to schema file paths.
                Expected key: "ask_followup_question"
                Example: {"ask_followup_question": "path/to/schema.yaml"}
                Paths can be relative to this file's directory.

        """
        super().__init__(name=name)

        # Get the directory containing this file for resolving relative paths
        this_file_dir = Path(__file__).parent

        # Extract schema path from schemas dictionary
        ask_followup_question_schema = None
        if schemas and (schema_path := schemas.get("ask_followup_question")) is not None:
            # Resolve path relative to this file if not absolute
            schema_path_resolved = Path(schema_path)
            if not schema_path_resolved.is_absolute():
                schema_path_resolved = this_file_dir / schema_path_resolved
            ask_followup_question_schema = load_tool_schema(str(schema_path_resolved))

        self.ask_followup_question_schema = ask_followup_question_schema

    @override
    async def get_tools(self) -> Sequence[Tool]:
        """Get question tools.

        Returns:
            Sequence containing the ask_followup_question tool.
            The tool can be customized with schema_override/name_override/
            description_override parameters through create_tool().

        """
        return [
            self.create_tool(
                ask_followup_question,
                category="other",
                schema_override=self.ask_followup_question_schema,
            ),
        ]
