from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPServerStdio, MCPServerStreamableHTTP

from xeno_agent.pydantic_ai.interfaces import ConfigLoader, SkillLoader
from xeno_agent.pydantic_ai.models import FlowConfig
from xeno_agent.pydantic_ai.prompts import PromptBuilder
from xeno_agent.pydantic_ai.runtime import RuntimeDeps, delegate_task
from xeno_agent.pydantic_ai.skills import SkillRegistry


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

    async def create(self, agent_id: str, flow_config: FlowConfig) -> Agent[RuntimeDeps, str]:
        if agent_id in self._agent_cache:
            return self._agent_cache[agent_id]

        # 1. Load Agent Config
        agent_config = self.config_loader.load_agent_config(agent_id)

        # 2. Build Agent
        mcp_servers = []
        if agent_config.tools.mcp_servers:
            for srv in agent_config.tools.mcp_servers:
                if isinstance(srv, str):
                    mcp_servers.append(MCPServerStreamableHTTP(srv))
                elif srv.url:
                    mcp_servers.append(
                        MCPServerStreamableHTTP(
                            srv.url,
                            headers=srv.headers,
                            sse_read_timeout=srv.read_timeout,
                            tool_prefix=srv.tool_prefix,
                            timeout=srv.timeout,
                            allow_sampling=srv.allow_sampling,
                            log_level=srv.log_level,
                        ),
                    )
                elif srv.command:
                    mcp_servers.append(
                        MCPServerStdio(
                            srv.command,
                            args=srv.args,
                            env=srv.env,
                            cwd=srv.cwd,
                            tool_prefix=srv.tool_prefix,
                            timeout=srv.timeout,
                            allow_sampling=srv.allow_sampling,
                            log_level=srv.log_level,
                        ),
                    )

        agent = Agent(self.model, deps_type=RuntimeDeps, mcp_servers=mcp_servers)

        # 3. Attach System Prompt
        builder = PromptBuilder(agent_config, flow_config, self.skill_loader)

        @agent.system_prompt
        def render_system_prompt(ctx: RunContext[RuntimeDeps]) -> str:
            return builder.build_system_prompt()

        # 4. Attach Tools
        # Attach delegation tool (Universal)
        agent.tool(delegate_task)

        # Attach Agent-specific skills
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
