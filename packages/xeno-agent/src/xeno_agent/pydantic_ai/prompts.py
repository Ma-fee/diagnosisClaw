import logging

from xeno_agent.pydantic_ai.interfaces import SkillLoader
from xeno_agent.pydantic_ai.models import AgentConfig, FlowConfig

logger = logging.getLogger(__name__)


class PromptBuilder:
    def __init__(self, agent_config: AgentConfig, flow_config: FlowConfig, skill_loader: SkillLoader | None = None):
        self.agent_config = agent_config
        self.flow_config = flow_config
        self.skill_loader = skill_loader

    def build_system_prompt(self) -> str:
        parts = []

        # Layer 1: Identity
        parts.append(f"Role: {self.agent_config.role}")
        parts.append(f"Backstory: {self.agent_config.backstory}")

        # Layer 2: Flow Context
        parts.append(f"\nContext: {self.flow_config.name}")
        parts.append(f"Instructions: {self.flow_config.global_instructions}")

        # Layer 3: Delegation
        rules = self.flow_config.delegation_rules.get(self.agent_config.identifier, {})
        # Flow rules override agent defaults if present
        allowed = rules.get("allow_delegation_to", self.agent_config.allow_delegation_to)

        if allowed:
            parts.append("\nYou have the ability to delegate tasks to the following agents:")
            parts.extend(f"- {agent}" for agent in allowed)
        else:
            parts.append("\nYou cannot delegate tasks to other agents.")

        # Layer 4: Skills
        if self.agent_config.skills and self.skill_loader:
            parts.append("\nYou have the following skills available:")
            for skill_id in self.agent_config.skills:
                try:
                    skill_xml = self.skill_loader.render_skill(skill_id, {})
                    parts.append(skill_xml)
                except Exception:
                    logger.exception(f"Failed to load skill: {skill_id}")

        return "\n".join(parts)
