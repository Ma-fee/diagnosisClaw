import os
from pathlib import Path
from typing import Any

from crewai import LLM, Agent

from xeno_agent.config_loader import ConfigLoader
from xeno_agent.core.skill_loader import SkillLoader
from xeno_agent.core.tool_loader import ToolLoader
from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


class XenoAgentBuilder:
    """
    Builder for CrewAI Agents with Xeno-specific prompt injection.
    """

    def __init__(self, role_name: str, config_loader: ConfigLoader | None = None) -> None:
        self._role = role_name
        self._config_loader = config_loader
        self._goal = ""
        self._backstory = ""
        self._tools: list[str] = []
        self._skills: list[str] = []
        self._llm = None
        self._allow_delegation = False
        self._verbose = True
        self._capabilities: list[str] = []
        self._constraints: list[str] = []
        self._example = ""
        self._thought_process = ""

        # Loaders
        self._tool_loader = ToolLoader()
        self._skill_loader = SkillLoader()

    def with_goal(self, goal: str) -> "XenoAgentBuilder":
        self._goal = goal
        return self

    def with_backstory(self, backstory: str) -> "XenoAgentBuilder":
        self._backstory = backstory
        return self

    def with_tool(self, *tools: str) -> "XenoAgentBuilder":
        self._tools.extend(tools)
        return self

    def with_skill(self, *skills: str) -> "XenoAgentBuilder":
        self._skills.extend(skills)
        return self

    def with_llm(self, llm: Any) -> "XenoAgentBuilder":
        self._llm = llm
        return self

    def from_yaml(self, yaml_path: str) -> "XenoAgentBuilder":
        """
        从 YAML 配置文件水化构建器。

        Args:
            yaml_path: 角色 YAML 文件路径 (config/roles/*.yaml)

        Returns:
            水化后的 XenoAgentBuilder 实例
        """
        if self._config_loader is None:
            config_root = Path(__file__).parent.parent.parent.parent / "config"
            logger.info(f"Using default config_root: {config_root}")
            self._config_loader = ConfigLoader(str(config_root))

        # Extract role_name from yaml_path (supports both full path and role name)
        yaml_file = Path(yaml_path)
        role_name = yaml_file.stem  # Removes .yaml or .yml suffix

        # 加载 YAML 配置 (with role_name, not full path)
        config = self._config_loader.load_role_config(role_name)

        # 设置角色名称 - 优先使用identifier字段, 否则使用name
        mode_slug = config.get("identifier") or role_name
        self._role = config.get("name", mode_slug)

        # 设置基本属性
        self._goal = config.get("goal", "")
        self._backstory = config.get("backstory", "")
        self._thought_process = config.get("thought_process", "")

        # 设置工具列表 (tools 字段)
        tools = config.get("tools", [])
        for tool_name in tools:
            self.with_tool(tool_name)

        # 设置技能列表 (skills 字段) - NEW
        skills = config.get("skills", [])
        for skill_name in skills:
            self.with_skill(skill_name)

        # 设置 capabilities (用于验证和 prompt 注入)
        self._capabilities = config.get("capabilities", [])
        # 设置约束和示例, 用于 prompt 注入
        self._constraints = config.get("constraints", [])
        self._example = config.get("example", "")

        logger.info(f"Hydrated agent '{self._role}' (mode_slug: {mode_slug}) from {yaml_path}")
        logger.debug(f"  Goal: {self._goal}")
        logger.debug(f"  Capabilities: {self._capabilities}")
        logger.debug(f"  Tools: {tools}")
        logger.debug(f"  Skills: {skills}")

        return self

    def build(self) -> Agent:
        """
        Constructs the CrewAI Agent.
        """
        # 1. Load Tools
        agent_tools = self._tool_loader.get_tool_instances(self._tools)

        # 2. Load Skills instructions
        skill_instructions = []
        loaded_skills = self._skill_loader.load_all()

        for skill_name in self._skills:
            if skill_name in loaded_skills:
                skill = loaded_skills[skill_name]
                skill_instructions.append(f"### {skill.metadata.name}\n{skill.metadata.description}\n\n{skill.instructions}")
            else:
                logger.warning(f"Skill '{skill_name}' not found.")

        # 3. Compile backstory
        prompt_parts = [self._backstory]

        if self._thought_process:
            prompt_parts.append(f"## Thought Process\n{self._thought_process}")

        if self._constraints:
            constraints_text = "\n".join([f"- {c}" for c in self._constraints])
            prompt_parts.append(f"## Constraints\n{constraints_text}")

        if self._capabilities:
            caps_text = "\n".join([f"- {c}" for c in self._capabilities])
            prompt_parts.append(f"## Capabilities\n{caps_text}")

        # Add skills instructions
        if skill_instructions:
            skills_text = "\n\n".join(skill_instructions)
            prompt_parts.append(f"## Skills and Instructions\n{skills_text}")

        if self._example:
            prompt_parts.append(f"## Examples\n{self._example}")

        full_backstory = "\n\n".join(prompt_parts)

        # Ensure LLM is set for function calling
        llm_instance = self._llm
        if llm_instance is None:
            model_name = os.environ.get("OPENAI_MODEL_NAME", "gpt-4")
            llm_instance = LLM(model=model_name)

        return Agent(
            role=self._role,
            goal=self._goal,
            backstory=full_backstory,
            tools=agent_tools,
            llm=llm_instance,
            function_calling_llm=llm_instance,
            allow_delegation=self._allow_delegation,
            verbose=self._verbose,
        )
