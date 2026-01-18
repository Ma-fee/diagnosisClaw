from crewai.tools import BaseTool

from ..skills.builtin.diagnostic_tools import (
    CollectMetricsTool,
    DeepInspectTool,
    QueryKnowledgeBaseTool,
    QueryLogsTool,
)
from ..skills.builtin.meta_tools import AskFollowupTool, AttemptCompletionTool, NewTaskTool, SwitchModeTool
from ..skills.builtin.search_tools import SearchEngineTool


class SkillRegistry:
    """
    Centralized registry for skills (tools) and their instruction prompts.
    Used by XenoAgentBuilder to inject skills into agent configurations.
    """

    _skills: dict[str, tuple[BaseTool, str]] = {}

    @classmethod
    def register(cls, name: str, tool: BaseTool, instruction: str):
        """
        Register a skill with the registry.

        Args:
            name: Unique identifier for the skill
            tool: The CrewAI BaseTool instance
            instruction: The instruction prompt to append to the agent's backstory
        """
        cls._skills[name] = (tool, instruction)

    @classmethod
    def get(cls, name: str) -> tuple[BaseTool, str]:
        """
        Retrieve a skill by name.

        Args:
            name: The skill identifier

        Returns:
            A tuple of (BaseTool, instruction)

        Raises:
            ValueError: If the skill is not found
        """
        if name not in cls._skills:
            raise ValueError(f"Skill '{name}' not found in registry. Registered skills: {list(cls._skills.keys())}")
        return cls._skills[name]

    @classmethod
    def list_skills(cls) -> dict[str, str]:
        """
        List all registered skills with their descriptions.

        Returns:
            Dictionary mapping skill names to tool descriptions
        """
        return {name: tool.description for name, (tool, _) in cls._skills.items()}

    @classmethod
    def clear(cls):
        """Clear all registered skills (useful for testing)."""
        cls._skills.clear()


def register_builtin_skills(registry: SkillRegistry):
    """Registers core meta-tools and diagnostic tools."""
    # Meta Tools
    registry.register("switch_mode", SwitchModeTool(), "Use to switch roles.")

    registry.register("new_task", NewTaskTool(), "Use to delegate subtasks.")

    registry.register("attempt_completion", AttemptCompletionTool(), "Use to complete task.")

    registry.register("ask_followup_question", AskFollowupTool(), "Use to ask user questions.")

    # Diagnostic tools
    registry.register("collect_metrics", CollectMetricsTool(), "Collect system metrics and monitoring data.")
    registry.register("query_logs", QueryLogsTool(), "Query and analyze system logs.")
    registry.register("query_knowledge_base", QueryKnowledgeBaseTool(), "Query diagnostic knowledge base.")
    registry.register("deep_inspect", DeepInspectTool(), "Perform deep inspection of system components.")

    # Search tools
    registry.register("search_engine", SearchEngineTool(), "Search for technical documents and specifications.")
