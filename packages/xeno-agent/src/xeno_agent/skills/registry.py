from crewai.tools import BaseTool


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
