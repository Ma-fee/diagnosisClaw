# Oh-My-OpenCode 主 Agent 调用机制调研

> 调研日期: 2026-01-22  
> 项目: oh-my-opencode (oh-my-zsh for ClaudeCode)

## 目录

- [1. 架构概览](#1-架构概览)
- [2. delegate_task 工具详解](#2-delegate_task-工具详解)
- [3. Category vs Agent 调用方式](#3-category-vs-agent-调用方式)
- [4. Background Task 执行机制](#4-background-task-执行机制)
- [5. Sisyphus 调用其他 Agent 的时机](#5-sisyphus-调用其他-agent-的时机)
- [6. Atlas/Momus/Metis/Prometheus 协作流程](#6-atlasmomusmetisprometheus-协作流程)
- [7. Background Output 阻塞模式](#7-background-output-阻塞模式)
- [8. 关键代码路径](#8-关键代码路径)

---

## 1. 架构概览

```
用户请求
    │
    ▼
┌─────────────────────────────────┐
│   Sisyphus（主代理）            │
│   src/agents/sisyphus.ts       │
└───────────┬─────────────────┘
            │
    ┌───────┴───────┬───────────────┬───────────────┐
    │               │               │               │
    ▼               ▼               ▼               ▼
delegate_task   delegate_task   delegate_task   /start-work
（category）    （agent）      （background）    command
    │               │               │               │
    ▼               ▼               ▼               ┼
Sisyphus-J    explore/lib    Background    ┌───────────┴────┐
-{category}     rarian后台     Manager     │  Atlas（编排器） │
    │               │               │                  │
    ▼               ▼               │                  ▼
同步执行          并行运行          │        .sisyphus/plans/
    │               │              │        {plan}.md
    ▼               ▼              │                  │
返回结果          task_id         │                  ▼
（验证 QA）       通知父会话   │          读取 todo list
                                  │                  │
                                  │        ┌─────────┴────────┐
                                  │        │                  │
                                  │        ▼                  ▼
                                  │  delegate_task   delegate_task
                                  │  （并行任务）   （resume 失败）
                                  │        │                  │
                                  │        └──────────────────┘
```

### 核心设计理念

| 理念 | 说明 |
|------|------|
| **并行探索，顺序实现** | Explore/Librarian 并行，核心任务同步 |
| **Fire-and-forget** | Background task 启动后立即返回，不阻塞主线 |
| **强制验证** | 每个委托任务完成后必须运行 lsp_diagnostics/test |
| **智慧累积** | Atlas 执行时通过 Notepad累积学习 |

---

## 2. delegate_task 工具详解

**文件**: `src/tools/delegate-task/tools.ts` (886 行)

### 2.1 三种调用参数

| 方式 | 参数 | 生成的会话 | 用途 |
|------|------|------------|------|
| **Category** | `category="visual"`, `skills=[]` | `Sisyphus-Junior-visual` | 按领域分类任务，使用优化模型 |
| **Agent** | `subagent_type="oracle"`, `skills=[]` | 直接调用 `oracle` | 访问预定义专家代理 |
| **Resume** | `resume="session_id"`, `prompt="..."` | 继续之前会话 | 保留完整上下文，节省 token |

### 2.2 同步 vs 异步执行

```typescript
// 异步模式 (run_in_background=true)
if (run_in_background === true) {
  // 立即返回 task_id，不等待
  return manager.launch(launchInput)
  
  // 使用场景: 并行探索，多任务同时进行
}

// 同步模式 (run_in_background=false，默认)
if (run_in_background === false) {
  // 等待任务完成，返回完整结果
  const session = await client.session.create({ ... })
  const result = await pollUntilComplete(session.id)
  
  // 使用场景: 必须等待结果才能继续
}
```

### 2.3 完整执行流程（同步模式）

```typescript
// src/tools/delegate-task/tools.ts:683-755
async function executeSync(sessionID, prompt) {
  // 1. 创建子会话
  const session = await client.session.create({ ... })
  
  // 2. 发送提示
  await client.session.prompt({
    path: { id: session.id },
    body: {
      noReply: true,
      parts: [{ type: "text", text: prompt }],
    },
  })
  
  // 3. 轮询等待完成 (2秒间隔，最多10分钟)
  while (true) {
    const status = await client.session.status({ path: { id: session.id } })
    
    if (status.data.type === "idle") {
      // 检测消息稳定性 (3次稳定 = 完成)
      if (isMessageStable(session.id, 3)) {
        break
      }
    }
    await delay(2000)
  }
  
  // 4. 提取结果
  return await extractResult(session.id)
}
```

---

## 3. Category vs Agent 调用方式

### 3.1 Categories（领域分类系统）

**文件**: `src/tools/delegate-task/constants.ts`

| Category | 模型 | 描述 | 温度 |
|----------|------|------|------|
| `visual-engineering` | `google/gemini-3-pro-preview` | Frontend, UI/UX, design | 0.5 |
| `ultrabrain` | `openai/gpt-5.2-codex` (xhigh) | 深度逻辑推理，复杂架构 | 按配置 |
| `artistry` | `google/gemini-3-pro-preview` (max) | 高度创意/艺术任务 | 0.5 |
| `quick` | `anthropic/claude-haiku-4-5` | 简单任务 | 0.5 |
| `unspecified-low` | `anthropic/claude-sonnet-4-5` | 不适配类别，低复杂度 | 0.5 |
| `unspecified-high` | `anthropic/claude-opus-4-5` (max) | 不适配类别，高复杂度 | 0.1 |
| `writing` | `google/gemini-3-flash-preview` | 文档撰写、技术写作 | 0.5 |

### 3.2 Category 提示词注入

每个 category 都会追加领域特定的系统提示：

```markdown
<Category_Context>
You are working on VISUAL/UI tasks.
Design-first mindset:
- Bold aesthetic choices over safe defaults
- Unexpected layouts, asymmetry, grid-breaking elements
- Cohesive color palettes with sharp accents
...
</Category_Context>
```

### 3.3 Direct Agents（直接调用专家）

| Agent | 模型 | 成本 | 用途 |
|-------|------|------|------|
| `explore` | `opencode/grok-code` | FREE | 代码库探索（Contextual Grep） |
| `librarian` | `opencode/glm-4.7-free` | CHEAP | 外部资源查询（Reference Grep） |
| `oracle` | `openai/gpt-5.2` | EXPENSIVE | 高智商调试和架构咨询 |
| `metis` | `anthropic/claude-sonnet-4-5` | EXPENSIVE | 预规划分析 |
| `momus` | `anthropic/claude-sonnet-4-5` | EXPENSIVE | 计划审查 |
| `multimodal-looker` | `google/gemini-3-flash` | CHEAP | PDF/图像分析 |

### 3.4 Explore vs Librarian 对比

| 维度 | Explore | Librarian |
|------|---------|-----------|
| **搜索范围** | OUR codebase | EXTERNAL 资源 |
| **用途** | 找项目内模式 | 找官方文档/OSS 示例 |
| **触发** | "find X in our code" | "how to use [lib]" |
| **执行方式** | 总是 background=true | 总是 background=true |
| **并行** | ✅ 多角度并行 | ✅ 多来源并行 |

---

## 4. Background Task 执行机制

### 4.1 核心流程

```
主线 Agent (Sisyphus)
    ↓
delegate_task(run_in_background=true, ...)
    ↓
立即返回 task_id (不阻塞!)
    ↓
主线继续执行其他操作...
    │
    └─→ BackgroundManager 启动后台轮询 (2秒间隔)
         ├─ 检查 session.status === "idle"
         ├─ 检测消息稳定性 (3次稳定 = 完成)
         ├─ 检查 todo 状态
         └─ 超时处理 (30分钟 TTL)
```

### 4.2 BackgroundManagerLaunch

**文件**: `src/features/background-agent/manager.ts`

```typescript
// manager.ts:87-149
async launch(input: LaunchInput): Promise<BackgroundTask> {
  // 1. 创建任务对象
  const task: BackgroundTask = {
    id: `bg_${crypto.randomUUID().slice(0, 8)}`,
    status: "pending",
    queuedAt: new Date(),
    description: input.description,
    prompt: input.prompt,
    agent: input.agent,
    parentSessionID: input.parentSessionID,
    parentMessageID: input.parentMessageID,
    // ... 其他字段
  }
  
  // 2. 加入队列
  this.tasks.set(task.id, task)
  this.pendingByParent.set(input.parentSessionID, new Set([...]))
  
  // 3. Fire-and-forget: 立即返回
  return task
}
```

### 4.3 轮询检测逻辑

```typescript
// manager.ts:1140-1274
private async pollRunningTasks(): Promise<void> {
  this.pruneStaleTasksAndNotifications()
  
  const statusResult = await this.client.session.status()
  const allStatuses = statusResult.data as Record<string, { type: string }>
  
  for (const task of this.tasks.values()) {
    if (task.status !== "running") continue
    
    // 方法1: 检测 session.idle
    if (sessionStatus?.type === "idle") {
      const hasValidOutput = await this.validateSessionHasOutput(sessionID)
      const hasIncompleteTodos = await this.checkSessionTodos(sessionID)
      
      if (hasValidOutput && !hasIncompleteTodos) {
        await this.tryCompleteTask(task, "polling (idle status)")
        continue
      }
    }
    
    // 方法2: 消息稳定性检测 (3次稳定 = 完成)
    const currentMsgCount = messages.length
    const elapsedMs = Date.now() - startedAt.getTime()
    
    if (elapsedMs >= MIN_STABILITY_TIME_MS) {  // 5秒
      if (task.lastMsgCount === currentMsgCount) {
        task.stablePolls = (task.stablePolls ?? 0) + 1
        if (task.stablePolls >= 3) {  // 3次稳定
          await this.tryCompleteTask(task, "stability detection")
        }
      }
    }
    task.lastMsgCount = currentMsgCount
  }
}
```

### 4.4 通知机制

```typescript
// manager.ts:897-1009
private async notifyParentSession(task: BackgroundTask): Promise<void> {
  const pendingSet = this.pendingByParent.get(task.parentSessionID)
  const remainingCount = pendingSet?.size ?? 0
  const allComplete = remainingCount === 0
  
  // 单任务完成: 静默通知 (noReply=true)
  // 全部完成: 完整通知
  await this.client.session.prompt({
    path: { id: parentSessionID },
    body: {
      noReply: !allComplete,  // ← 关键：单任务不打断主线
      parts: [{ type: "text", text: notification }],
    },
  })
}
```

### 4.5 关键边界检查

| Guard | 检查点 | 行为 |
|-------|--------|------|
| **MIN_IDLE_TIME_MS** | 5秒内忽略 idle | 防止过早完成 |
| **validateSessionHasOutput** | 必须有实际文本输出 | 防止空结果 |
| **checkSessionTodos** | 不能有未完成 todo | 等待任务完成 |
| **稳定性检测** | 消息3次无变化 | 确认真正完成 |

---

## 5. Sisyphus 调用其他 Agent 的时机

### 5.1 Phase 0 - Intent Gate（触发条件）

**文件**: `src/agents/sisyphus.ts` (Phase 0)

```markdown
## Phase 0 - Intent Gate

### Key Triggers（必须立即响应的触发器）:

1. **Skill 匹配** → 立即调用 skill 工具
   - 触发: "playwright", "frontend-ui-ux", "git-master"
   - 动作: `skill(name="playwright")`

2. **Explore/Librarian 相关** → 用作 peer 工具
   - 触发: "find patterns", "where is X", "how do I use [lib]"
   - 动作: `delegate_task(subagent_type="explore", run_in_background=true)`

3. **2+ 模块涉及** → 启动探索
   - 触发: 跨模块任务
   - 动作: 多个 explore/librarian 并行

4. **GitHub 提及** → 完整工作周期
   - 触发: "@sisyphus look into X"
   - 动作: 调查 → 实现 → PR 创建
```

### 5.2 Phase 2A - 探索与研究

```markdown
## Phase 2A - Exploration & Research

### 决策流程:
1. 启动 Explore Agents（代码库内搜索）
   - `delegate_task(subagent_type="explore", run_in_background=true, prompt="...")`
   
2. 启动 Librarian Agents（外部资源）
   - `delegate_task(subagent_type="librarian", run_in_background=true, prompt="...")`
   
3. 继续工作，立即继续
   - 不等待，探索结果通过系统通知获取

### 委托前必须声明（MANDATORY）:
对于每个 delegate_task 调用：
1. Category 选择理由
2. 技能评估（包含/省略原因）
3. 预期输出
```

### 5.3 Sisyphus 完整提示词结构

```markdown
# Sisyphus Prompt (src/agents/sisyphus.ts:516-599)

## Phase 0 - Intent Gate
├─ Key Triggers（技能匹配、探索、GitHub）
└─ Step 1-3: 分类和验证

## Phase 1 - Codebase Assessment
└─ 评估代码库成熟度（Disciplined/Transitional/Legacy）

## Phase 2A - Exploration & Research
├─ Explore Agent（Contextual Grep）
├─ Librarian Agent（Reference Grep）
├─ Oracle（High-IQ Consultant）
└─ Parallel Execution（默认）

## Phase 2B - Implementation
├─ 7段式委托提示
├─ Code Changes 规则
└─ Verification（证据要求）

## Phase 2C - Failure Recovery
└─ 3次失败后停止 → 咨询 Oracle

## Phase 3 - Completion
└─ 完成标准检查清单
```

---

## 6. Atlas/Momus/Metis/Prometheus 协作流程

### 6.1 Prometheus 规划流程

**文件**: `src/agents/prometheus-prompt.ts` (1197 行)

```mermaid
Interview Mode（默认）
    ↓
收集用户需求
    ↓
并行启动探索 agents (explore + librarian)
    ↓
运行 Self-Clearance Check
    ↓
所有需求清晰？
    ├─ 是 → Auto-Transition
    └─ 否 → 继续提问（Interviewee Mode）

Auto-Transition
    ↓
Metis Consultation（强制）
    ↓
生成工作计划
    ↓
展示摘要
    ↓
用户选择：
    ├─ Start Work → 交付 Atlas 执行
    └─ High Accuracy → Momus 循环
```

### 6.2 Metis（预规划分析）

**文件**: `src/agents/metis.ts`

```markdown
## Metis - Pre-Planning Consultant

### Phase 0: Intent Classification（强制第一步）
├─ Refactoring
├─ Build from Scratch
├─ Mid-sized Task
├─ Collaborative
├─ Architecture
└─ Research

### Phase 1: Intent-Specific Analysis
├─ BEFORE analyzing → 启动 explore/librarian
├─ 分析完成 → 提出问题
└─ 输出给 Prometheus 的指令

### Output Format:
├─ Intent Classification
├─ Pre-Analysis Findings
├─ Questions for User
├─ Identified Risks
├─ Directives for Prometheus
└─ Recommended Approach
```

### 6.3 Momus（高精度审查）

**文件**: `src/agents/momus.ts`

```markdown
## Momus - Plan Reviewer

### 审查标准（9条必须满足）:
□ 100% 的文件引用经验证
□ 零关键的文件验证失败
□ 关键上下文已记录
□ ≥80% 任务有清晰参考来源
□ ≥90% 任务有具体验收标准
□ 零任务需要关于业务逻辑/关键架构的假设
□ 计划提供清晰的全局图
□ 零关键红旗
□ 主动模拟显示核心任务可执行

### Momus Review Loop:
while (true) {
  result = delegate_task(agent="Momus", prompt=plan)
  
  if (result.verdict === "OKAY") {
    break  // 计划通过
  }
  
  // 必须修复问题并重新提交
  fixIssues(result.feedback)
  regeneratePlan()
  // 不接受任何借口，只有"OKAY"是出口
}
```

### 6.4 Atlas（编排器执行）

**文件**: `src/agents/atlas.ts` (1384 行)

```mermaid
Atlas Orchestrator 触发条件:
  ├─ 用户提供 todo list 路径 (.sisyphus/plans/{name}.md)
  ├─ 需要多代理协调
  └─ 需要并行任务执行

STEP 0: 注册跟踪 TODO
└─ todowrite([...])

STEP 1: 读取和分析 Todo List
├─ 读取 .sisyphus/plans/{name}.md
├─ 解析所有 [ ] 任务
├─ 提取并行性信息
└─ 构建并行化图谱

STEP 2: 初始化累积智慧
└─ 创建 .sisyphus/notepads/{plan}/

STEP 3: 任务执行循环
├─ 3.0: 检查可并行任务 → 并行启动多个 delegate_task
├─ 3.1: 选择下一个任务 (Category vs Agent)
├─ 3.2: 准备 7 段式提示（强制）
├─ 3.3: 调用 delegate_task（background=false，必须）
├─ 3.4: 项目级 QA 验证
│  ├─ lsp_diagnostics
│  ├─ build/test
│  ├─ 手动检查文件
│  └─ 收集证据
├─ 3.5: 处理失败（resume 最多 3 次）
└─ 3.6: 循环控制

STEP 4: 最终报告
└─ 生成完成报告
```

### 6.5 智慧累积系统

```bash
.sisyphus/notepads/{plan-name}/
├─ learnings.md      # 发现的模式、约定、成功方法
├─ decisions.md     # 架构选择、权衡
├─ issues.md        # 问题、阻碍、bug
├─ verification.md  # 测试结果、验证结果
└─ problems.md      # 未解决问题、技术债务
```

**协议**:
1. **BEFORE 每次委托** → 读取 notepad
2. **INCLUDE 在每个提示中** → 作为 "INHERITED WISDOM"
3. **AFTER 每个任务完成** → 指示子代理追加发现
4. **子代理是无状态的** → 必须每次传递所有上下文

---

## 7. Background Output 阻塞模式

**文件**: `src/tools/background-task/tools.ts`

### 7.1 Tool Schema

```typescript
// schema 定义（暴露给大模型）
args: {
  task_id: tool.schema.string().describe("Task ID to get output from"),
  block: tool.schema.boolean().optional().describe("Wait for completion (default: false)"),
  timeout: tool.schema.number().optional().describe("Max wait time in ms (default: 60000, max: 600000)"),
}
```

### 7.2 两种模式对比

| 模式 | 参数 | 行为 | 场景 |
|------|------|------|------|
| **非阻塞** | `block=false`（默认） | 立即返回状态，不等待 | 可并行做其他工作 |
| **阻塞** | `block=true` | 等待任务完成或超时 | 必须等待结果 |

### 7.3 阻塞模式实现

```typescript
// src/tools/background-task/tools.ts:353-371
if (!shouldBlock) {
  return formatTaskStatus(task)  // 立即返回状态
}

// Blocking: poll until completion or timeout
const startTime = Date.now()

while (Date.now() - startTime < timeoutMs) {  // 默认 60s，最大 600s
  await delay(1000)  // 每秒轮询
  
  const currentTask = manager.getTask(args.task_id)
  if (currentTask.status === "completed") {
    return await formatTaskResult(currentTask, client)
  }
  
  if (currentTask.status === "error" || currentTask.status === "cancelled") {
    return formatTaskStatus(currentTask)
  }
}

// Timeout exceeded
return `Timeout exceeded (${timeoutMs}ms). Task still ${finalTask.status}.`
```

### 7.4 使用建议

```typescript
// 场景1: 并行探索，多角度搜索 → 非阻塞
task1_id = background_task(agent="explore", prompt="Find auth middleware")
task2_id = background_task(agent="explore", prompt="Find routing patterns")

doSomeIndependentWork()  // 继续做其他事

// 场景2: 必须等待结果 → 阻塞
auth_result = background_output(task_id=task1_id, block=true)
routing_result = background_output(task_id=task2_id, block=true)

implementFeature(auth_result, routing_result)
```

**设计者建议**: `block=true` 很少需要，因为系统会自动通知完成。但对于"必须等待结果才能继续"的场景，保留了阻塞能力。

---

## 8. 关键代码路径

| 功能 | 文件 | 关键函数/代码行 |
|------|------|----------------|
| **委托工具入口** | `src/tools/delegate-task/tools.ts:568-883` | `createDelegateTask()`, `execute()` |
| **Category 解析** | `src/tools/delegate-task/tools.ts:110-149` | `resolveCategoryConfig()` |
| **Skill 注入** | `src/tools/delegate-task/tools.ts:206-214` | `resolveMultipleSkills()` |
| **同步执行** | `src/tools/delegate-task/tools.ts:683-755` | `pollUntilComplete()` |
| **异步后台** | `src/tools/delegate-task/tools.ts:636-647` | `manager.launch()` |
| **BackgroundManager** | `src/features/background-agent/manager.ts` | `launch()`, `pollRunningTasks()` |
| **Background Output** | `src/tools/background-task/tools.ts:320-384` | `createBackgroundOutput()` |
| **Atlas Hook** | `src/hooks/atlas/index.ts:436-771` | `createAtlasHook()` |
| **自动继续** | `src/hooks/atlas/index.ts:453-510` | `injectContinuation()` |
| **验证提醒** | `src/hooks/atlas/index.ts:181-190` | `buildVerificationReminder()` |
| **Agent 工厂** | `src/agents/utils.ts:134-241` | `createBuiltinAgents()` |
| **动态提示** | `src/agents/sisyphus.ts:516-599` | `buildDynamicSisyphusPrompt()` |
| **Atlas 提示** | `src/agents/atlas.ts:1336-1355` | `createAtlasAgent()` |
| **Metis 提示** | `src/agents/metis.ts:281-292` | `createMetisAgent()` |
| **Momus 提示** | `src/agents/momus.ts:392-415` | `createMomusAgent()` |
| **Prometheus** | `src/agents/prometheus-prompt.ts:110-216` | Interview Mode, Metis/Momus |

---

## 总结

### 核心原则

1. **并行探索，顺序实现** - Explore/Librarian 并行，结果用于指导后续实现
2. **Fire-and-forget** - Background task 启动后立即返回，主线继续工作
3. **强制验证** - 每个委托任务完成后必须运行 lsp_diagnostics/build/test
4. **阻塞可选** - `background_output(block=true)` 允许同步等待
5. **计划-审查-执行** - Prometheus → Metis/Momus → Atlas 质量保证流程

### Agent 调用决策树

```
需要委托任务？
    │
    ├─ 是 → 领域特定工作？
    │         ├─ 是 → category 参数
    │         └─ 否 → subagent_type 参数
    │
    └─ 否 → 结束

执行方式？
    │
    ├─ 必须等结果 → background=false / block=true
    └─ 可并行工作 → background=true（非阻塞）

选哪个 Agent？
    │
    ├─ 代码库搜索 → explore
    ├─ 外部资源 → librarian
    ├─ 专家咨询 → oracle
    ├─ 预规划分析 → metis
    ├─ 计划审查 → momus
    └─ 执行 todo list → atlas
```
