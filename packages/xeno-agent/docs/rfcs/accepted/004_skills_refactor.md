# RFC-004: Skills 系统重构 - 兼容 Claude Skills 标准

| Status | Proposed |
| :--- | :--- |
| **Author** | Antigravity (Sisyphus) |
| **Date** | 2026-01-19 |
| **Scope** | Skills System, Claude Skills Compatibility |
| **Related RFCs** | 001, 003 |

---

## 1. 执行摘要

### 1.1 目标

将 xeno-agent 的 skills 系统重构为兼容 Claude Skills 标准的设计，实现**无层次依赖**、**易于扩展**、**角色绑定清晰**的能力管理系统。

### 1.2 动机

**当前问题**:
- ❌ **概念混淆**: Tool 和 Skill 混为一谈
- ❌ `skills/registry.py` 把 `SwitchModeTool`、`NewTaskTool` 等控制流工具当作 skills 注册
- ❌ Meta Tools 和 Skills 未解耦
- ❌ 缺少 ToolLoader（工具说明管理）
- ❌ YAML 配置中 capability 语义不明确

**重构价值**:
- ✅ **无层级依赖**: Capability、Task、Skill、Tool 四者平行，都关联到 Role
- ✅ **Claude 兼容**: Skills 使用 Claude Skills 标准 YAML frontmatter + Markdown 格式
- ✅ **解耦设计**: Meta Tools 作为纯工具，Skills 作为能力指导
- ✅ **清晰绑定**: 四个组件独立配置，由 Agent 组装
- ✅ **ToolLoader 双重作用**: (1) 加载工具说明传递给 LLM，(2) 加载可执行工具实例
- ✅ **灵活配置**: Skills 目录可配置，避免与代码仓库的 `.claude` 冲突
- ✅ **易于扩展**: 新增 Skill 或 Task 创建文件夹 + 定义文件即可（无需修改 Python 代码）

### 1.3 范围

**包含**:
- 创建 ToolLoader 管理工具说明和实例
- 实现 SkillLoader 兼容 Claude Skills SKILL.md 格式
- 支持可配置的 skills 和 tasks 目录
- 更新 XenoAgentBuilder.from_yaml() 组装四个独立组件
- 迁移现有定义到标准格式

**不包含**:
- MCP Server 集成（保留现有 `mcp_tool.py`，由 ToolLoader 加载）
- Engine 层集成（如糊搜索、图灵机器人等）
- 高级 Skill 功能（hooks、progressive disclosure 等）

---

## 2. Claude Skills 标准分析

### 2.1 官方标准

Claude Skills 是 Anthropic 官方定义的**可扩展能力模块化系统**：

**核心特性**:
- **文件系统**: Skills 存储为文件夹（而非 Python 代码）
- **SKILL.md**: 每个 skill 的入口点（必须包含 YAML frontmatter）
- **Markdown 指令**: 使用自然语言描述技能的工作流程、约束、示例
- **可扩展资源**: 支持 `references/`、`scripts/`、`examples/` 目录
- **Prompt Expansion**: Skill 被加载时，其 Markdown 指令被注入到 LLM 上下文

**SKILL.md 格式**:

```yaml
---
name: skill-name
description: Single-line description of what this skill does
allowed-tools:
  - search_engine
  - collect_metrics
---

# Skill Title

## When to Use
[描述何时使用此技能]

## Instructions
[详细的工作流程和指导]

## Examples
[使用示例]

## Guidelines
[使用约束和最佳实践]
```

**文件结构示例**:

```
skill-name/
├── SKILL.md                    # 必需：主指令文件
├── references/                   # 可选：参考文档
│   ├── diagnostic_mindset.md
│   └── search_strategies.md
├── scripts/                     # 可选：可执行脚本
│   └── collect_metrics.py
└── examples/                    # 可选：使用示例
    └── typical_fault_case.md
```

### 2.2 设计哲学

1. **非代码优先**: Skills 是 prompt expansion，非可执行代码
2. **渐进式披露**: 附加文件在需要时才读取（Progressive Disclosure）
3. **人类可读**: 直接编辑 Markdown 文件，无需编程知识
4. **独立可测试**: 每个 Skill 可独立加载和测试

---

## 3. 当前实现分析

### 3.1 问题：概念混淆

当前 `skills/registry.py` 将所有东西都注册为 "skills":

```python
# src/xeno_agent/skills/registry.py

class SkillRegistry:
    def register_builtin_skills(registry: SkillRegistry):
        # ❌ Meta Tools 被当做 "skills" 注册
        registry.register("switch_mode", SwitchModeTool(), "Use to switch roles.")
        registry.register("new_task", NewTaskTool(), "Use to delegate subtasks.")
        # ...
```

**问题分析**:
- **SwitchModeTool** → 应该是 **Tool**（控制流工具）
- **Fault Analysis capability** → 应该是 **Skill**（prompt expansion）
- 当前没有 **ToolLoader** 管理工具说明

### 3.2 问题：缺少 ToolLoader

ToolLoader 应该有两个作用：
1. **加载工具说明**（description、parameters 等，用于传递给 LLM）
2. **加载工具实例**（CrewAI BaseTool，用于执行）

但没有实现统一的管理机制。

### 3.3 问题：Capability 语义不明确

```yaml
# config/roles/fault_expert.yaml
capabilities:
  - fault_analysis          # ❌ 只是人类可读的字符串，无绑定逻辑
  - task_orchestration
```

职责不明：是"必须具备"？还是"可以使用"？还是"白名单"？

### 3.4 当前架构的局限性

```
┌─────────────────────────────────────┐
│   Agent (Role)                  │
│   YAML: name, goal, skills[]    │
└──────────────┬──────────────────┘
               │ 直接从 SkillRegistry 获取 tools
               ▼
┌─────────────────────────────────────┐
│   SkillRegistry (混为一谈）      │
│   - SwitchModeTool (是 Tool? Skill?)
│   - CollectMetricsTool (是 Tool?  Skill?)
└─────────────────────────────────────┘
```

**问题**:
- 无法区分 "Tool" 和 "Skill"
- 缺少 "Capability" 抽象层
- 无法声明 "Task"
- 无法并行配置四个独立组件

---

## 4. 提议：平行四层架构

### 4.1 核心架构（无层级关系）

```
                ┌───────────────────────────────────┐
                │        Agent (Role)          │
                │  YAML: capabilities[], tasks[] │
                │        tools[], skills[]        │
                └───────────────┬───────────────┘
                                │ 1. 四个平行配置都关联到 Role
        ┌───────────────┼───────────────┬───────────────┬───────────────┐
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌───────────┐ ┌─────────────┐ ┌─────────────┐
│ Capability  │ │   Task    │ │   Skill     │ │   Tool      │
│ (声明能力）  │ │  (CrewAI)  │ │ (Claude SKILL)│ │ (CrewAI Tool)│
│ capabilities │ │ description │ │  SKILL.md   │ │  BaseTool   │
│  [] 字符串   │ │expected_out │ │  instructions │ │             │
└─────────────┘ └───────────┘ └─────────────┘ └─────────────┘
        │               │               │               │
        └───────────────┼───────────────┴───────────────┴───────────────┘
                       │
                       ▼
              ┌─────────────┐
              │ Agent 构建  │
              │  组装这些    │
              │  组件        │
              └─────────────┘
```

**核心原则**：
- **平行关系**: Capability、Task、Skill、Tool 四者是平行的，互不引用
- **关联到 Role**: 四者都通过 Agent Role 的 YAML 配置进行绑定
- **无层次依赖**: 彼此之间没有包含或派生关系

### 4.2 四层独立定义

| Layer | 定义 | 用途 | 存储位置 |
|-------|------|------|----------|
| **Capability** | 字符串数组 | 声明式能力描述（用于校验或文档） | YAML `capabilities: []` 字段 |
| **Task** | CrewAI Task | 执行单元，描述 + expected_output | YAML `tasks: []` 字段 |
| **Tool** | CrewAI BaseTool | 原子操作（被执行） | ToolLoader 加载 |
| **Skill** | Claude SKILL.md | Prompt expansion（指令） | SkillLoader 加载 |

### 4.3 ToolLoader 双重作用

#### 作用 1：加载工具说明（传递给 LLM）

```python
# src/xeno_agent/core/tool_loader.py

class ToolLoader:
    """
    ToolLoader 的两个作用：
    1. 加载工具的说明、字段说明等（用于传递给大模型）
    2. 如果未提供，采用默认项目路径下的内容（config/tools/builtin/）
    3. 外部的 mcp 工具
    """

    @classmethod
    def load_tool_descriptions(cls) -> Dict[str, dict]:
        """
        加载工具说明，用于传递给 LLM。

        返回格式：
        {
            "tool_name": {
                "name": "工具名称",
                "description": "工具描述（详细）",
                "parameters": {
                    "param1": "参数说明",
                    ...
                },
                "metadata": {
                    "source": "builtin|mcp",
                    "category": "meta|functional"
                }
            },
            ...
        }
        """
        pass
```

**工具说明结构**:

```yaml
# config/tools/builtin/switch_mode.yaml
name: switch_mode
description: 切换到指定的角色/模式
parameters:
  mode_slug:
    type: string
    description: 目标模式的 slug（如 fault_expert）
    required: true
  reason:
    type: string
    description: 切换原因说明
    required: true
metadata:
  category: meta
  usage: |
    1. QA Assistant → Fault Expert: 检测到复杂故障
    2. Fault Expert → Equipment Expert: 需要物理指导
```

#### 作用 2：加载逻辑

```python
class ToolLoader:
    def _load_builtin_tools(self):
        """加载内置工具（默认从 config/tools/builtin/）。"""
        builtin_dir = Path("config/tools/builtin")
        for tool_yaml in builtin_dir.glob("*.yaml"):
            tool_desc = yaml.safe_load(tool_yaml.read_text())
            # 检查是否有对应的 Python 实现
            tool_class = self._find_tool_implementation(tool_desc["name"])
            if tool_class:
                self._tools[tool_desc["name"]] = tool_class()
            else:
                logger.warning(f"Tool {tool_desc['name']} has description but no implementation")

    def _load_mcp_tools(self):
        """加载 MCP 工具（外部）。"""
        from .mcp_tool import MCPToolManager
        manager = MCPToolManager()
        mcp_tools = manager.list_tools()
        for tool in mcp_tools:
            self._tools[tool["name"]] = MCPTool(tool)
```

**说明**：
- **内置工具**: YAML 说明 + Python 实现
- **MCP 工具**: 从 MCP 服务器动态加载
- **其它工具**: 不支持（因为没有逻辑实现）

---

## 5. 角色配置示例

### 5.1 Fault Expert 配置

```yaml
# config/roles/fault_expert.yaml

name: Fault Expert
role: 故障诊断编排与协调专家
goal: 系统化分析复杂故障，规划诊断步骤，协调子任务执行
backstory: 你是资深的机械故障诊断专家，擅长系统化思维和协作调度。

# Capabilities: 声明式能力描述（用于校验）
capabilities:
  - 故障诊断
  - 任务协调
  - 诊断工具访问

# Tasks: CrewAI Task 对象
tasks:
  - description: 进行系统化的故障诊断，收集信息，分析原因
    expected_output: 完整的诊断报告

  - description: 生成清晰、结构化的诊断报告
    expected_output: Markdown 格式的报告

# Tools: 可用工具列表（从 ToolLoader 加载）
tools:
  - switch_mode   # 切换角色
  - new_task      # 委派子任务
  - collect_metrics  # 收集指标
  - query_logs    # 查询日志
  - search_engine # 搜索文档

# Skills: Claude Skills (prompt expansion)
skills:
  - fa_skill_fault_analysis
  - fa_skill_task_orchestration

thought_process: |
  1. 接收用户故障描述，初步分析
  2. 制定诊断计划
  3. 子任务委派策略
  4. 综合与决策
```

### 5.2 QA Assistant 配置

```yaml
# config/roles/qa_assistant.yaml

name: Q&A Assistant
role: 意图识别与网关分发
goal: 快速识别用户问题类型并路由到合适的专家
backstory: 你是机械故障诊断系统的前台，负责区分简单问答和复杂故障诊断。

capabilities:
  - 意图识别
  - 请求路由

tasks:
  - description: 快速判断问题类型并路由
    expected_output: 路由决策

tools:
  - switch_mode
  - new_task

skills:
  - fa_skill_intent_classification
```

---

## 6. AgentBuilder 组装

```python
# src/xeno_agent/agents/builder.py

from ..core.tool_loader import ToolLoader
from ..core.skill_loader import SkillLoader

class XenoAgentBuilder:
    @classmethod
    def from_yaml(cls, config: dict[str, Any], llm=None) -> Agent:
        """
        从 YAML 配置构建 Agent，组装四个独立组件。

        组件来源：
        1. capabilities: 声明式描述（可选，用于文档或校验）
        2. tasks: CrewAI Task 列表
        3. tools: 从 ToolLoader 加载
        4. skills: 从 SkillLoader 加载（Claude SKILL.md）
        """

        # 1. 解析基础字段
        name = config["name"]
        role = config["role"]
        goal = config["goal"]
        backstory = config.get("backstory", "")
        thought_process = config.get("thought_process", "")

        # 2. 加载 Tools
        tool_loader = ToolLoader()
        tools = tool_loader.get_tool_instances()
        tool_descriptions = tool_loader.load_tool_descriptions()

        # 3. 加载 Skills
        skill_loader = SkillLoader()
        skills = skill_loader.load_all()

        # 4. 组装所有 instructions
        instructions_parts = [backstory]
        if thought_process:
            instructions_parts.append(f"\n\n## 思考过程\n{thought_process}")

        # 5. 注入 Skill instructions
        specified_skills = config.get("skills", [])
        skills_prompt = cls._merge_skills(skills, specified_skills)
        if skills_prompt:
            instructions_parts.append(f"\n\n## 你的技能和能力\n{skills_prompt}")

        # 6. 构造 CrewAI Agent
        return Agent(
            role=role,
            goal=goal,
            backstory="\n".join(instructions_parts),
            tools=tools,
            llm=llm,
            verbose=config.get("verbose", True)
        )

    @classmethod
    def _merge_skills(cls, all_skills: Dict, specified: List):
        """合并指定的 Skill instructions。"""
        parts = []
        for skill_name in specified:
            if skill_name in all_skills:
                skill = all_skills[skill_name]
                parts.append(f"### {skill.metadata.name}\n\n")
                parts.append(skill.instructions)
                parts.append("\n\n")
        return "".join(parts)
```

---

## 7. 实施计划

### Phase 1: 创建 ToolLoader (P0 - 1天)

#### Task 1.1: 创建 ToolLoader 基础结构

**File**: `src/xeno_agent/core/tool_loader.py`

**任务**:
- [ ] 实现 `ToolLoader` 类
- [ ] 实现 `_load_builtin_tools()` 方法（从 `config/tools/builtin/`）
- [ ] 实现 `_load_mcp_tools()` 方法
- [ ] 实现 `load_tool_descriptions()` 方法

**验证**:
```python
from xeno_agent.core.tool_loader import ToolLoader

loader = ToolLoader()
descriptions = loader.load_tool_descriptions()

assert "switch_mode" in descriptions
assert descriptions["switch_mode"]["parameters"]["mode_slug"]["required"] == True
```

#### Task 1.2: 迁移 meta_tools 到独立类

**Files**:
- `src/xeno_agent/tools/meta_tools.py` (新文件）

**任务**:
- [ ] 从 `skills/builtin/meta_tools.py` 移动 content
- [ ] 保留 CrewAI BaseTool 实现
- [ ] 为每个工具创建 YAML 说明文件在 `config/tools/builtin/`

**验证**:
```python
from xeno_agent.tools.meta_tools import SwitchModeTool

tool = SwitchModeTool()
assert hasattr(tool, '_run')
```

---

### Phase 2: 实现 SkillLoader (P0 - 1.5天)

#### Task 2.1: 实现 SKILL.md 解析

**File**: `src/xeno_agent/core/skill_loader.py`

**任务**:
- [ ] 实现 `SkillMetadata` Pydantic 模型
- [ ] 实现 `Skill` Pydantic 模型
- [ ] 实现 `SkillLoader` 类基础结构
- [ ] 实现 `_base_path` 初始化（环境变量 + 配置文件 + 默认）

**验证**:
同前面设计部分...

#### Task 2.2: 迁移所有 Skills 到 Claude 格式

**任务**:
创建 `skills/` 目录结构：
1. `fa_skill_intent_classification/SKILL.md`
2. `fa_skill_fault_analysis/SKILL.md` + `references/`
3. `fa_skill_task_orchestration/SKILL.md`
4. `fa_skill_deep_search/SKILL.md` + `references/`
5. `fa_skill_diagram_analysis/SKILL.md` + `references/`
6. `fa_skill_equipment_knowledge/SKILL.md`
7. `fa_skill_document_parsing/SKILL.md`

---

### Phase 3: 更新 AgentBuilder (P0 - 0.5天)

#### Task 3.1: 集成 ToolLoader

**File**: `src/xeno_agent/agents/builder.py`

**任务**:
- [ ] 添加 `ToolLoader` 初始化
- [ ] 从 ToolLoader 加载工具实例和说明
- [ ] 移除对旧 `SkillRegistry` 的依赖

**验证**:
```python
from xeno_agent.agents.builder import XenoAgentBuilder
from xeno_agent.core.tool_loader import ToolLoader

builder = XenoAgentBuilder()
loader = ToolLoader()

# 验证工具可以加载
tools = loader.get_tool_instances()
assert len(tools) > 0
```

#### Task 3.2: 集成 SkillLoader

**任务**:
- [ ] 添加 `SkillLoader` 初始化
- [ ] 实现 `_merge_skills()` 方法合并 Skill instructions
- [ ] 更新 backstory 构造逻辑

**验证**:
```python
config = {
    "name": "Test Agent",
    "role": "test",
    "goal": "test",
    "skills": ["fa_skill_intent_classification"]
}

agent = XenoAgentBuilder.from_yaml(config)
assert agent is not None
```

---

### Phase 4: 更新 Role 配置 (P1 - 0.5天)

#### Task 4.1: 更新所有 Role YAML

**Files**:
- `config/roles/qa_assistant.yaml`
- `config/roles/fault_expert.yaml`
- `config/roles/equipment_expert.yaml`
- `config/roles/material_assistant.yaml`

**任务**:
- [ ] 移除旧的 `skills` 无意义的绑定
- [ ] 添加新的 `skills` 列表（Claude Skills）
- [ ] 添加 `tasks` 列表（CrewAI Task）
- [ ] 保留 `capabilities` 作为声明式描述

**验证**:
```python
from xeno_agent.config.loader import ConfigLoader

loader = ConfigLoader()
config = loader.load_role_config("config/roles/fault_expert.yaml")

assert "capabilities" in config  # 声明式描述
assert "tasks" in config  # CrewAI Tasks
assert "skills" in config  # Claude Skills
assert "tools" in config  # Tools 从 ToolLoader
```

---

### Phase 5: 清理和文档 (P1 - 1天)

#### Task 5.1: 删除旧的 skills/ 目录

**任务**:
- [ ] 删除 `src/xeno_agent/skills/registry.py`
- [ ] 删除 `src/xeno_agent/skills/builtin/` 目录

#### Task 5.2: 更新文档

**任务**:
- [ ] 更新 RFC-004 本文档
- [ ] 更新 `AGENTS.md` 说明新架构
- [ ] 添加 `ARCHITECTURE.md` 说明平行四层架构

---

### Phase 6: 集成测试 (P1 - 1天)

#### Task 6.1: 单元测试

**Files**:
- `tests/test_tool_loader.py`
- `tests/test_skill_loader.py`
- `tests/test_builder.py`

**任务**:
- [ ] 测试 ToolLoader 工具说明加载
- [ ] 测试 SkillLoader SKILL.md 解析
- [ ] 测试 AgentBuilder 完整流程

---

## 8. 验收标准

### 8.1 功能验收

- ✅ ToolLoader 可以加载工具说明（传递给 LLM）
- ✅ ToolLoader 可以加载工具实例（CrewAI BaseTool）
- ✅ SkillLoader 可以从配置目录加载 SKILL.md 文件
- ✅ XenoAgentBuilder 组装四个独立组件
- ✅ Skills、Tools、Capalities 互不依赖
- ✅ 所有 4 个 Role YAML 更新并工作

### 8.2 代码质量验收

- ✅ 代码通过 Ruff 检查
- ✅ 代码有完整类型注解
- ✅ 测试覆盖率 > 80%

### 8.3 文档验收

- ✅ RFC-004 文档完整
- ✅ 更新 AGENTS.md 说明新架构
- ✅ 每个 SKILL.md 文件符合 Claude Skills 标准

---

## 9. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|-------|------|----------|
| **四个组件依赖混乱** | 中 | 高 | 明确平行关系，更新文档 |
| **ToolLoader 兼容性** | 低 | 中 | 提供清晰的迁移路径 |
| **Skill Loader 解析错误** | 中 | 中 | 严格遵循 Claude Skills 格式 |
| **性能回归** | 低 | 低 | 性能测试，对比迁移前后指标 |

---

## 10. 文件变更清单

```
packages/xeno-agent/
├── config/
│   ├── roles/
│   │   ├── qa_assistant.yaml           # 修改：添加 tasks, skills
│   │   ├── fault_expert.yaml          # 修改：添加 tasks, skills
│   │   ├── equipment_expert.yaml      # 修改：添加 tasks, skills
│   │   └── material_assistant.yaml    # 修改：添加 tasks, skills
│   └── tools/                       # 新增：工具说明目录
│       └── builtin/                 # 内置工具的 YAML 说明
│           ├── switch_mode.yaml
│           ├── new_task.yaml
│           └── ...
│
├── skills/                          # 新增：Claude Skills 目录
│   ├── fa_skill_intent_classification/
│   │   └── SKILL.md
│   ├── fa_skill_fault_analysis/
│   │   ├── SKILL.md
│   │   └── references/
│   └── ...
│
├── src/xeno_agent/
│   ├── core/
│   │   ├── tool_loader.py             # 新增：工具加载器
│   │   └── skill_loader.py            # 新增：Claude Skills 加载器
│   ├── agents/
│   │   └── builder.py                # 修改：集成 ToolLoader + SkillLoader
│   ├── tools/                         # 重构：从 skills/builtin/ 迁移
│   │   ├── meta_tools.py              # 重命名
│   │   ├── functional_tools.py         # 重命名
│   │   └── mcp_tool.py               # 保留
│   └── skills/                        # 删除：旧的 skills/ 目录
│       └── (废弃)
└── docs/
    └── rfc/
        └── 004_skills_refactor.md  # 本文件
```

---

## 11. Timeline 预估

| Phase | 任务 | 预估 |
|-------|------|------|
| 1.1 | 创建 ToolLoader 基础结构 | 2h |
| 1.2 | 迁移 meta_tools 到独立类 | 2h |
| 2.1 | 实现 SKILL.md 解析 | 3h |
| 2.2 | 迁移所有 Skills | 4h |
| 3.1 | 集成 ToolLoader 到 AgentBuilder | 1h |
| 3.2 | 集成 SkillLoader 到 AgentBuilder | 1.5h |
| 4.1 | 更新 Role YAML | 2h |
| 5.1 | 删除旧的 skills 目录 | 0.5h |
| 5.2 | 更新文档 | 1.5h |
| 6.1 | 集成测试 | 2.5h |

**总计**: ~20 小时（~2.5 个工作日）

---

## 12. 决策

**状态**: ⏳ 待批准

**批准后开始**: Phase 1 Task 1.1
