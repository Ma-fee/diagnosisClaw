from collections.abc import Callable
from pathlib import Path

import yaml
from crewai.tools import BaseTool

from ..skills.builtin.diagnostic_tools import (
    CollectMetricsTool,
    DeepInspectTool,
    QueryKnowledgeBaseTool,
    QueryLogsTool,
)
from ..skills.builtin.meta_tools import AskFollowupTool, AttemptCompletionTool, NewTaskTool, SwitchModeTool
from .builder import XenoAgentBuilder


class AgentRegistry:
    """
    Centralized registry for agents.

    Stores agent creation functions keyed by mode_slug.
    """

    def __init__(self):
        self._agents: dict[str, Callable] = {}

    def register(self, mode_slug: str, creator: Callable):
        """
        Register an agent creator function.

        Args:
            mode_slug: The unique identifier for this agent mode
            creator: A function that takes (llm=None) and returns a CrewAI Agent
        """
        self._agents[mode_slug] = creator

    def get(self, mode_slug: str, llm=None):
        """
        Retrieve an agent from the registry.

        Args:
            mode_slug: The agent mode to retrieve
            llm: The LLM instance to use (passed to creator)

        Returns:
            A CrewAI Agent instance

        Raises:
            ValueError: If mode not found
        """
        if mode_slug not in self._agents:
            available = list(self._agents.keys())
            raise ValueError(f"Agent mode '{mode_slug}' not found. Available modes: {available}")
        return self._agents[mode_slug](llm=llm)

    def list_modes(self):
        """
        List all registered agent modes.

        Returns:
            Dictionary mapping mode_slug to agent creator function
        """
        return self._agents.copy()


class SkillRegistry:
    """
    Registry for tools and their instruction prompts.
    """

    def __init__(self):
        self._skills: dict[str, tuple[BaseTool, str]] = {}

    def register(self, name: str, tool: BaseTool, instruction: str):
        self._skills[name] = (tool, instruction)

    def get(self, name: str) -> tuple[BaseTool, str]:
        if name not in self._skills:
            raise ValueError(f"Skill '{name}' not found in registry.")
        return self._skills[name]


def register_builtin_skills(registry: SkillRegistry):
    """Registers core meta-tools and diagnostic tools."""
    registry.register("switch_mode", SwitchModeTool(), "Use to switch roles.")
    registry.register("new_task", NewTaskTool(), "Use to delegate subtasks.")
    registry.register("attempt_completion", AttemptCompletionTool(), "Use to complete task.")
    registry.register("ask_followup_question", AskFollowupTool(), "Use to ask user questions.")

    # Diagnostic tools
    registry.register("collect_metrics", CollectMetricsTool(), "Collect system metrics and monitoring data.")
    registry.register("query_logs", QueryLogsTool(), "Query and analyze system logs.")
    registry.register("query_knowledge_base", QueryKnowledgeBaseTool(), "Query diagnostic knowledge base.")
    registry.register("deep_inspect", DeepInspectTool(), "Perform deep inspection of system components.")


def load_agent_from_yaml(yaml_path: str, agent_registry: AgentRegistry, skill_registry: SkillRegistry, llm=None):
    """
    Load an agent from a YAML file and register it.

    Args:
        yaml_path: Path to YAML file
        agent_registry: Registry to register the agent to
        skill_registry: Registry to resolve skills from
        llm: The LLM instance to use (passed to builder)

    YAML format:
        role: "Agent Name"
        goal: "Agent goal"
        backstory: "Agent backstory"
        skills:
          - skill_name
    """
    yaml_path_obj = Path(yaml_path)
    with yaml_path_obj.open("r") as f:
        data = yaml.safe_load(f)

    # Extract mode_slug from filename (remove _agent.yaml suffix)
    mode_slug = yaml_path_obj.stem.replace("_agent", "").replace("_agent", "").replace("_yaml", "").replace("_yml", "")

    # Create builder with role_name from role field or mode_slug
    role_name = data.get("role", mode_slug.title())

    # Register creation function that rebuilds the agent each time
    def create_agent_creator(agent_data, mode):
        def creator(llm=None):
            builder = XenoAgentBuilder(role_name, skill_registry)
            if "goal" in data:
                builder.with_goal(data["goal"])
            if "backstory" in data:
                builder.with_backstory(data["backstory"])
            if "skills" in data:
                for skill in data["skills"]:
                    builder.with_skill(skill)
            builder.with_llm(llm)
            return builder.build()

        return creator

    agent_registry.register(mode_slug, create_agent_creator(data, mode_slug))

    return mode_slug
