---
rfc_id: RFC-009
title: 为 `task` 工具扩展 `skills` 参数
status: DRAFT
author: Assistant
reviewers: []
created: 2026-02-18
last_updated: 2026-02-18
decision_date:
---

# RFC-009: 为 `task` 工具扩展 `skills` 参数

## 1. 概述

本 RFC 提议在 `task` 委派工具中增加一个 `skills` 参数（默认为空数组）。当父 Agent 委派子任务给子 Agent 时，可以直接通过此参数指定该子任务应该使用的技能列表，从而在子任务执行时自动将技能指令注入到子 Agent 的上下文中。

**预期结果**:
- 子任务级别的技能注入，无需更改 Agent/会话配置
- 使单次子任务可以使用专为该任务设计的技能（如 "诊断规划报告生成"）
- 更灵活的技能组合和复用

**使用示例**:
```
用户请求: "帮我生成挖掘机故障的诊断规划报告"

父 Agent 思考: 我需要委派给 report_expert，
并且使用 "诊断规划报告生成" 技能来规范输出格式

工具调用:
- task(agent_or_team="report_expert", 
       prompt="生成挖掘机液压系统故障诊断规划", 
       skills=["诊断规划报告生成"],
       description="生成诊断规划报告")
```

## 2. 背景与上下文

### 2.1 当前系统状态

当前 `SubagentTools.task()` 方法签名：

```python
# agentpool_toolsets/builtin/subagent_tools.py

async def task(
    self,
    ctx: AgentContext,
    agent_or_team: str,
    prompt: str,
    description: str,
    async_mode: bool = False,
) -> dict[str, Any]:
    # ... 实现
```

子任务执行流程：
1. 获取目标节点（Agent/Team）
2. 生成子会话 ID
3. 调用 `node.run_stream(prompt, session_id=child_session_id, ...)`
4. 流式返回结果

**当前限制**: 无法为单个子任务指定专属技能，技能只能通过 Session/Agent 级配置。

### 2.2 相关文档

- [RFC-004: Skills Refactor](./004_skills_refactor.md) - 技能系统架构
- `agentpool_toolsets/builtin/skills.py` - SkillsTools 工具集

### 2.3 术语表

| 术语 | 定义 |
|-----|------|
| Skill | 可复用的 Agent 工作流或技术模式，存储于 `SKILL.md` 文件 |
| Task Tool | `SubagentTools.task()` 工具，用于委派子任务 |
| Skill Injection | 将技能指令动态注入到 Agent 上下文 |
| Child Session | 子 Agent 任务的独立会话 |
| Target Node | 被委派的 Agent 或 Team |

## 3. 问题陈述

### 3.1 当前痛点

**场景 A: 报告生成任务需要特定格式技能**
- 父 Agent: fault_expert
- 子任务: 生成诊断规划报告
- 需要的技能: "诊断规划报告生成"（定义了报告的结构、字段、格式）
- **问题**: 当前无法只为这个子任务加载该技能，需要修改 report_expert 的全局配置

**场景 B: 多步骤任务，每步需要不同技能**
- Step 1: 数据收集 → 需要 "systematic-debugging"
- Step 2: 报告生成 → 需要 "diagnostic-report-template"
- Step 3: 代码生成 → 需要 "code-generation-patterns"
- **问题**: 无法灵活切换技能组合

### 3.2 问题影响

- **灵活性缺失**: 无法按需组合技能
- **配置膨胀**: 需要为每种技能组合创建专用 Agent
- **技能污染**: 所有子任务共享相同技能，可能不够精准

## 4. 目标与非目标

### 4.1 目标

- 支持在 `task` 工具调用时指定子任务专用技能列表
- 技能指令动态注入到子 Agent 的 prompt/上下文中
- 保持向后兼容，不传递 skills 时不改变行为

### 4.2 非目标

- 修改 Session/Agent 级技能配置机制
- 支持动态修改技能内容（技能本身是静态的）
- 支持技能嵌套或技能继承

## 5. 评估标准

| 标准 | 权重 | 描述 | 最低要求 |
|-----|------|------|---------|
| 向后兼容性 | High | 现有 task 调用无需修改 | 100% 向后兼容 |
| 实现复杂度 | Medium | 需要修改的代码量 | 涉及 <=3 个核心文件 |
| 性能影响 | Medium | 子任务启动时间增加 | 延迟增加 < 5% |
| 可维护性 | Medium | 代码清晰度和隔离性 | 不破坏现有架构 |
| 用户体验 | High | Agent 开发便利性 | 直观易用 |

## 6. 方案分析

### 6.1 方案 A: Task Level Skill Injection（推荐）

**描述**: 在 `task` 工具中添加 `skills` 参数，在子任务开始前将技能指令动态注入到子 Agent 的系统上下文中。

**实现方式**:
1. `task()` 方法接受 `skills: list[str]` 参数
2. 在调用 `node.run_stream()` 前，先加载技能指令
3. 将技能指令作为 `system_prompt_suffix` 或特定消息注入

**优点**:
- 瓦粒度的技能组合
- 不影响其他子任务或会话
- 实现简单，利用现有技能加载机制

**缺点**:
- 子 Agent 无法"看到"这些技能为"可用技能"（只注入指令）
- 需要使用 `load_skill` 工具调用来动态确认

**评估**:

| 标准 | 得分 | 说明 |
|-----|------|------|
| 向后兼容性 | 5/5 | 默认空数组，不影响现有调用 |
| 实现复杂度 | 4/5 | 涉及 2-3 个文件 |
| 性能影响 | 4/5 | 多一次技能加载 |
| 可维护性 | 4/5 | 逻辑清晰但需维护注入点 |
| 用户体验 | 5/5 | 直观易用 |

**工作量估计**: 1-2 天

---

### 6.2 方案 B: Task-Level Skills Config Override

**描述**: 允许 `task` 调用时临时覆写目标 Agent 的技能配置。

**实现方式**:
- 在子会话创建时，使用临时修改的 `SkillsToolsetConfig`
- 影响 `SkillsTools` 工具的行为

**优点**:
- 子 Agent 可以正常调用 `load_skill` 发现新技能

**缺点**:
- 需要修改 Agent/Session 的初始化流程
- 实现复杂度高，容易引入并发问题

**评估**: 实现复杂度 2/5，不推荐

---

### 6.3 方案对比总览

| 方案 | 向后兼容 | 实现复杂度 | 性能 | 可维护性 | 用户体验 | 总分 |
|-----|---------|-----------|------|---------|---------|-----|
| A | 5 | 4 | 4 | 4 | 5 | 22/25 |
| B | 4 | 2 | 3 | 2 | 4 | 15/25 |

## 7. 推荐方案

**推荐方案 A**：Task Level Skill Injection

## 8. 技术设计

### 8.1 API 变更

#### 8.1.1 Task 工具签名

```python
# agentpool_toolsets/builtin/subagent_tools.py

async def task(
    self,
    ctx: AgentContext,
    agent_or_team: str,
    prompt: str,
    description: str,
    async_mode: bool = False,
    skills: list[str] | None = None,  # 新增参数
) -> dict[str, Any]:
    """Execute a task on an agent or team with optional skill injection.

    Args:
        agent_or_team: The agent or team to execute the task
        prompt: The task instructions for the agent or team
        description: A short (3-5 words) description of the task
        async_mode: If True, run in background and return task ID
        skills: Optional list of skill names to inject into the task context.
                These skills will be loaded and their instructions appended
                to the system context before the task starts.
                Example: ["诊断规划报告生成", "systematic-debugging"]

    Returns:
        Structured output containing result and metadata
    """
```

### 8.2 实现细节

#### 8.2.1 主实现流程

```python
# agentpool_toolsets/builtin/subagent_tools.py

async def task(
    self,
    ctx: AgentContext,
    agent_or_team: str,
    prompt: str,
    description: str,
    async_mode: bool = False,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    from agentpool import Team, TeamRun
    from agentpool.agents.base_agent import BaseAgent
    from agentpool.common_types import SupportsRunStream

    if ctx.pool is None:
        raise ToolError("Agent needs to be in a pool to execute tasks")

    if agent_or_team not in ctx.pool.nodes:
        raise ModelRetry(
            f"No agent or team found with name: {agent_or_team}. "
            f"Available nodes: {', '.join(ctx.pool.nodes.keys())}"
        )

    node = ctx.pool.nodes[agent_or_team]
    # ... 确定 source_type ...

    child_session_id = identifier.ascending("session")
    parent_session_id = ctx.node.session_id or identifier.ascending("session")

    # === 新增：技能注入 ===
    skill_instruction_suffix = ""
    if skills:
        skill_instructions = await self._load_skills_instructions(ctx, skills)
        if skill_instructions:
            skill_instruction_suffix = "\n\n## Task-Specific Skills\n\n" + skill_instructions
    # ====================

    logger.info(
        "Executing task",
        agent_or_team=agent_or_team,
        description=description,
        async_mode=async_mode,
        skills=skills or [],
    )

    # ... 发送 SpawnSessionStart 事件 ...

    if async_mode:
        # ... async 模式处理 ...
        # 需要确保技能指令被传递
        pass

    # Sync mode
    # === 修改：构建增强的 prompt ===
    enhanced_prompt = self._build_prompt_with_skills(prompt, skill_instruction_suffix)
    # ==============================

    return await _stream_task(
        ctx,
        source_name=agent_or_team,
        source_type=source_type,
        stream=node.run_stream(
            enhanced_prompt,  # 使用增强后的 prompt
            session_id=child_session_id,
            parent_session_id=parent_session_id,
        ),
        # ... 其他参数 ...
    )
```

#### 8.2.2 技能加载方法

```python
# agentpool_toolsets/builtin/subagent_tools.py

async def _load_skills_instructions(
    self,
    ctx: AgentContext,
    skill_names: list[str],
) -> str:
    """加载指定技能的指令并格式化为字符串。
    
    Args:
        ctx: Agent context with access to pool.skills
        skill_names: List of skill names to load
        
    Returns:
        Formatted skill instructions or empty string if none found
    """
    if ctx.pool is None:
        return ""
    
    instructions_parts: list[str] = []
    deduped_skills = list(dict.fromkeys(skill_names))  # 去重
    
    for skill_name in deduped_skills:
        try:
            # 使用 pool 的 SkillsManager 获取技能
            skills_manager = ctx.pool.skills
            
            # 确保技能目录已注册
            # 注意：这可能需要 async，取决于实现
            
            # 获取技能说明
            skill = skills_manager.get_skill(skill_name)
            skill_instructions = skills_manager.get_skill_instructions(skill_name)
            
            instructions_parts.append(
                f"### Skill: {skill_name}\n"
                f"{skill_instructions}\n"
            )
            
        except KeyError:
            logger.warning("Skill not found, skipping", skill_name=skill_name)
            # 可选：在结果中包含错误信息
            instructions_parts.append(
                f"### Skill: {skill_name}\n"
                f"*Note: This skill could not be loaded*\n"
            )
        except Exception as e:
            logger.warning("Failed to load skill", skill_name=skill_name, error=e)
    
    return "\n".join(instructions_parts)
```

#### 8.2.3 Prompt 构建

```python
def _build_prompt_with_skills(
    self,
    base_prompt: str,
    skills_section: str,
    placement: Literal["prefix", "suffix"] = "suffix",
) -> str:
    """将技能指令合并到用户 prompt 中。
    
    选择:
    - suffix (推荐): 技能指令放在 prompt 末尾，作为上下文补充
    - prefix: 技能指令放在 prompt 开头，优先级更高
    
    对于报告生成类技能，suffix 模式更合适，
    因为用户的核心指令应该优先。
    """
    if not skills_section:
        return base_prompt
    
    if placement == "prefix":
        return f"{skills_section}\n\n---\n\n{base_prompt}"
    else:  # suffix
        return f"{base_prompt}\n\n---\n\n{skills_section}"
```

### 8.3 Async 模式处理

对于 `async_mode=True`，技能注入需要在任务开始前完成：

```python
if async_mode:
    # 创建后台任务
    task = asyncio.create_task(
        _stream_task_to_fs_with_skills(
            fs=fs,
            task_id=task_id,
            source_name=agent_or_team,
            stream=node.run_stream(
                enhanced_prompt,
                session_id=child_session_id,
                parent_session_id=parent_session_id,
            ),
            skills_prefix=skill_instruction_suffix,  # 传递技能信息
        ),
        name=f"async_task_{task_id}",
    )
```

### 8.4 使用示例

**示例 1: 诊断报告生成**
```python
# 父 Agent 调用
await self.task(
    ctx=ctx,
    agent_or_team="report_expert",
    prompt="分析挖掘机液压系统故障数据并生成诊断规划",
    description="生成故障诊断报告",
    skills=["诊断规划报告生成"],
)

# 子 Agent (report_expert) 接收到的完整 prompt:
"""
分析挖掘机液压系统故障数据并生成诊断规划

---

## Task-Specific Skills

### Skill: 诊断规划报告生成

# 诊断规划报告生成

## 报告结构要求

### 1. 基本信息
- 设备型号
- 故障现象描述
- 发生时间/工况

### 2. 诊断步骤规划
- Step 1: 初步检查
- Step 2: 详细检测
...

## 输出格式
请严格按照上述结构生成 Markdown 格式的诊断规划报告。
"""
```

**示例 2: 多技能组合**
```python
await self.task(
    ctx=ctx,
    agent_or_team="debug_expert",
    prompt="排查电路板故障",
    skills=[
        "systematic-debugging",      # 系统化的故障排查方法
        "electronics-debugging",     # 电子电路专用工具使用
        "safety-protocols",         # 安全操作规范
    ],
)
```

## 9. 实现计划

### 9.1 文件变更清单

| 文件路径 | 变更类型 | 描述 |
|---------|---------|------|
| `agentpool_toolsets/builtin/subagent_tools.py` | 修改 | 添加 `skills` 参数和注入逻辑 |
| `agentpool/tool_schemas/TaskTool.json` | 修改 | 更新工具 schema（如有） |

### 9.2 里程碑

**Phase 1: 核心实现 (Day 1)**
- [ ] 修改 `SubagentTools.task()` 方法签名
- [ ] 实现 `_load_skills_instructions()` 方法
- [ ] 实现 `_build_prompt_with_skills()` 方法
- [ ] 集成到 sync 和 async 模式

**Phase 2: 测试 (Day 1-2)**
- [ ] 单元测试：`skills` 参数为 None/空/有效/无效
- [ ] 集成测试：端到端任务委派带技能
- [ ] 性能测试：技能加载 overhead

**Phase 3: 文档 (Day 2)**
- [ ] 更新 API 文档
- [ ] 添加使用示例

### 9.3 回滚策略

- 功能完全向后兼容
- 问题发生时，只需不传 `skills` 参数即可回退
- 代码层面无破坏性变更

## 10. 未解决问题

| 问题 | 当前想法 | 决策需要 |
|-----|---------|---------|
| 技能加载失败策略 | 记录 warning，继续执行 | 是否应该阻止任务？ |
| 技能指令位置 | suffix（prompt 后） | 是否支持 prefix 选项？ |
| 技能去重逻辑 | 保持传入顺序去重 | 是否需要排序？ |
| 异步模式技能显示 | 不显示在启动消息中 | 是否应该记录？ |

## 11. 决策记录

### 11.1 待决策

- [ ] 本 RFC 是否被接受？
- [ ] 技能加载失败时是否应该阻止任务？
- [ ] 是否需要支持技能指令前缀/后缀位置选择？

---

**状态**: DRAFT - 等待技术评审  
**更新记录**:
| 日期 | 版本 | 变更 |
|-----|------|------|
| 2026-02-18 | v0.1 | 初始草稿 - Task Level Skill Injection |
