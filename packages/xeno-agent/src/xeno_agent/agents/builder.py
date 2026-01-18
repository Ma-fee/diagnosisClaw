from typing import Any

from crewai import Agent

from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


class XenoAgentBuilder:
    """
    Builder for CrewAI Agents with Xeno-specific prompt injection.
    """

    def __init__(self, role_name: str, skill_registry: Any):
        self._role = role_name
        self._skill_registry = skill_registry
        self._goal = ""
        self._backstory = ""
        self._skills: list[str] = []
        self._llm = None
        self._allow_delegation = False
        self._verbose = True

    def with_goal(self, goal: str) -> "XenoAgentBuilder":
        self._goal = goal
        return self

    def with_backstory(self, backstory: str) -> "XenoAgentBuilder":
        self._backstory = backstory
        return self

    def with_skill(self, skill_name: str) -> "XenoAgentBuilder":
        self._skills.append(skill_name)
        return self

    def with_llm(self, llm: Any) -> "XenoAgentBuilder":
        self._llm = llm
        return self

    def build(self) -> Agent:
        """
        Constructs the CrewAI Agent.
        """
        tools = []
        instructions = []

        # Hydrate skills
        for skill in self._skills:
            try:
                tool, instr = self._skill_registry.get(skill)
                tools.append(tool)
                instructions.append(f"## Skill: {skill}\n{instr}")
            except ValueError as e:
                logger.warning(f"Warning: {e}")

        # Compile backstory
        full_backstory = f"{self._backstory}\n\n" + "\n\n".join(instructions)

        return Agent(role=self._role, goal=self._goal, backstory=full_backstory, tools=tools, llm=self._llm, allow_delegation=self._allow_delegation, verbose=self._verbose)
