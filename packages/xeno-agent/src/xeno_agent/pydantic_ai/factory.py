from typing import TYPE_CHECKING

from pydantic_ai import Agent, RunContext

from xeno_agent.pydantic_ai.interfaces import ConfigLoader, SkillLoader
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.prompts import PromptBuilder
from xeno_agent.pydantic_ai.runtime import RuntimeDeps, delegate_task
from xeno_agent.pydantic_ai.skills import SkillRegistry

if TYPE_CHECKING:
    from xeno_agent.pydantic_ai.tool_manager import FlowToolManager


class AgentFactory:
    def __init__(
        self,
        config_loader: ConfigLoader,
        skill_loader: SkillLoader | None = None,
        skill_registry: SkillRegistry | None = None,
        model: str = "openai:gpt-4o",
    ):
        self.config_loader = config_loader
        self.skill_loader = skill_loader
        self.skill_registry = skill_registry
        self.model = model
        self._agent_cache: dict[str, Agent[RuntimeDeps, str]] = {}

    async def create(
        self,
        agent_id: str,
        flow_config: FlowConfig,
        tool_manager: "FlowToolManager",
        use_cache: bool = True,
    ) -> Agent[RuntimeDeps, str]:
        if use_cache and agent_id in self._agent_cache:
            return self._agent_cache[agent_id]

        # 1. Load Agent Config
        agent_config = self.config_loader.load_agent_config(agent_id)

        # 2. Resolve Tools
        # AgentConfig.tools is now list[str] - using tool_manager to get Tool objects
        tools = tool_manager.get_tools(agent_config.tools)

        # 3. Build Agent
        agent = Agent(self.model, deps_type=RuntimeDeps, tools=tools)

        # 4. Attach System Prompt
        builder = PromptBuilder(agent_config, flow_config, self.skill_loader)

        @agent.system_prompt
        def render_system_prompt(ctx: RunContext[RuntimeDeps]) -> str:
            return builder.build_system_prompt()

        # 5. Attach Universal Delegation Tool
        agent.tool(delegate_task)

        # 6. Attach Agent-specific skills
        if agent_config.skills and self.skill_registry:
            for skill_id in agent_config.skills:
                try:
                    skill_func = self.skill_registry.get(skill_id)
                    agent.tool(skill_func)
                except KeyError:
                    # Skill not registered in Python, though it might be in XML
                    continue

        self._agent_cache[agent_id] = agent
        return agent
