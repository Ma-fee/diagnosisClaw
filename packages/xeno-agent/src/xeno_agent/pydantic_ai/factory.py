from pydantic_ai import Agent, RunContext

from xeno_agent.pydantic_ai.interfaces import ConfigLoader, SkillLoader
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.prompts import PromptBuilder
from xeno_agent.pydantic_ai.runtime import RuntimeDeps, delegate_task


class AgentFactory:
    def __init__(
        self,
        config_loader: ConfigLoader,
        skill_loader: SkillLoader | None = None,
        model: str = "openai:gpt-4o",
    ):
        self.config_loader = config_loader
        self.skill_loader = skill_loader
        self.model = model

    def create(self, agent_id: str, flow_config: FlowConfig) -> Agent[RuntimeDeps, str]:
        # 1. Load Agent Config
        agent_config = self.config_loader.load_agent_config(agent_id)

        # 2. Build Agent
        agent = Agent(self.model, deps_type=RuntimeDeps)

        # 3. Attach System Prompt
        builder = PromptBuilder(agent_config, flow_config, self.skill_loader)

        @agent.system_prompt
        def render_system_prompt(ctx: RunContext[RuntimeDeps]) -> str:
            return builder.build_system_prompt()

        # 4. Attach Tools
        # Attach delegation tool (Universal)
        agent.tool(delegate_task)

        return agent
