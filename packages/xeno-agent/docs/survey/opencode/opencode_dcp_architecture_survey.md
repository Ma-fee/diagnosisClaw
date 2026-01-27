# Dynamic Context Pruning (DCP) Plugin - 调研报告

## 执行摘要

本报告详细分析了 OpenCode 的 Dynamic Context Pruning (DCP) 插件的设计和实现。该插件通过智能移除对话历史中过时的工具输出来为 OpenCode 会话节省 token 使用。

**关键发现：**

- 插件采用 Hook 机制与 OpenCode 深度集成
- 自动化策略（去重、写覆盖、错误清理）零 LLM 成本运行
- LLM 驱动工具（discard、extract）实现有损/无损内容精简
- 基于 Placeholder 的消息转换，不删除历史消息
- 多层保护机制防止过度修剪（工具保护、文件保护、轮次保护）

---

## 1. 项目目标与问题域

### 1.1 核心目标

DCP 插件的核心目标是**动态减少对话上下文中的 token 消耗**，同时保持对话质量。主要应用于以下场景：

**适用场景：**

- ✅ 按请求计费（ atención、Antigravity）的 LLM 提供商
- ✅ 长会话（超过 200 K tokens）
- ✅ 需要在长对话历史中维护上下文的场景

**不适用场景：**

- ❌ 缓存计费模式（DCP 降低缓存命中率：65% vs 85%）
- ❌ 短会话（修剪成本大于收益）

### 1.2 解决的核心问题

**问题：** 随着对话进行，历史消息积累导致：

1. Token 消耗指数增长
2. 上下文窗口浪费（重复读取、已废弃的数据）
3. 响应时间增长（输入 token 增加）

**解决方案：** DCP 通过两种机制修剪上下文：

1. **自动策略**：零 LLM 成本，每次请求运行
2. **LLM 驱动工具**：AI 主动决定何时修剪

### 1.3 权衡考虑

| 维度       | 无 DCP | 有 DCP             | 影响           |
| ---------- | ------ | ------------------ | -------------- |
| 缓存命中率 | 85%    | 65%                | 降低 20%       |
| Token 消耗 | 基准   | 减少量到大量       | 长会话显著降低 |
| Token 成本 | 基准   | 按请求计费显著降低 | 计费模型受益   |

**结论：** 在按请求计费的模型上，token 节省的收益超过缓存命中率下降的影响。

---

## 2. 核心架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                  OpenCode Plugin System                 │
│  ┌──────────────────────────────────────────────┐      │
│  │  1. Plugin Initialization               │      │
│  │  - Load config (4-level merge)         │      │
│  │  - Create session state                │      │
│  │  - Register hooks (6 total)             │      │
│  │  - Register tools (discard/extract)      │      │
│  └────────────┬─────────────────────────────┘      │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐      │
│  │  2. Request Lifecycle (Per Request)     │      │
│  ├──────────────────────────────────────────────┤      │
│  │                                             │
│  │  chat.message → cache variant               │      │
│  │                                             │
│  │  experimental.chat.system.transform       │      │
│  │  → Inject pruning instructions             │      │
│  │                                             │
│  │  experimental.chat.messages.transform  (CORE) │      │
│  │  ├─ checkSession                         │      │
│  │  ├─ syncToolCache                       │      │
│  │  ├─ runStrategies:                       │      │
│  │  │   ├─ deduplicate                       │      │
│  │  │   ├─ supersedeWrites                  │      │
│  │  │   └─ purgeErrors                      │      │
│  │  ├─ prune(marked tools)                  │      │
│  │  └─ injectPrunableToolsList              │      │
│  │                                             │
│  │  LLM Response:                            │      │
│  │  - AI calls discard/extract (optional)      │      │
│  │  - Tools validated, marked, notify      │      │
│  │                                             │
│  │  command.execute.before                 │      │
│  │  → Handle /dcp commands                  │      │
│  └──────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
```

### 2.2 插件入口点

**主入口：** `index.ts`

插件通过 `@opencode-ai/plugin` SDK 实现异步插件接口：

```typescript
const plugin: Plugin = async (ctx: PluginInput) => {
    // 1. 配置加载（4 级合并）
    const config = getConfig(ctx)

    if (!config.enabled) return {}

    // 2. 创建依赖
    const logger = new Logger(config.debug)
    const state = createSessionState()

    // 3. Hook 注册
    return {
        // 系统 Prompt 注入
        "experimental.chat.system.transform": createSystemPromptHandler(...),

        // 核心：消息转换流水线
        "experimental.chat.messages.transform": createChatMessageTransformHandler(...),

        // 缓存模型 variant
        "chat.message": async (input) => { state.variant = input.variant },

        // 工具注册：discard/extract
        "tool": {
            discard: createDiscardTool(...),
            extract: createExtractTool(...)
        },

        // 配置变更：注册命令和工具
        "config": async (opencodeConfig) => { /* mutate */ },

        // 命令处理：/dcp context/stats/help
        "command.execute.before": createCommandExecuteHandler(...),
    }
}
```

### 2.3 Hook 执行时序

```
Startup:          config (注册工具和命令)
                  ↓
Per Message:      chat.message (缓存 variant)
                  ↓
Per Request:      experimental.chat.system.transform (注入修剪指令)
                  ↓
                  experimental.chat.messages.transform (修剪流水线)
                    ├─ checkSession(检测会话变更、压缩)
                    ├─ syncToolCache(重建工具缓存)
                    ├─ deduplicate(去重策略)
                    ├─ supersedeWrites(写覆盖策略)
                    ├─ purgeErrors(错误清理策略)
                    ├─ prune(应用修剪)
                    └─ injectPrunableTools(注入可修剪列表)
                  ↓
Tool Invocation:   tool hook (discard/extract 执行)
                    ├─ 验证 IDs
                    ├─ 标记修剪
                    ├─ 通知用户
                    └─ 持久化状态
                  ↓
Command:           command.execute.before (/dcp 命令)
```

---

## 3. 关键抽象与数据结构

### 3.1 SessionState（核心状态对象）

```typescript
interface SessionState {
    // 会话标识
    sessionId: string | null // 当前 OpenCode 会话 ID
    isSubAgent: boolean // 子 Agent 检测标记（修剪禁用）

    // 修剪决策
    prune: {
        toolIds: string[] // 已标记修剪的工具 ID 列表
    }

    // 统计数据
    stats: {
        pruneTokenCounter: number // 当前会话的 token 节省
        totalPruneTokens: number // 累计 token 节省
    }

    // 工具缓存
    toolParameters: Map<string, ToolParameterEntry> // 工具元数据缓存

    // 运行时状态
    nudgeCounter: number // 修剪提示计数器
    lastToolPrune: boolean // 上个工具是否是修剪操作
    lastCompaction: number // 最后消息压缩时间戳
    currentTurn: number // 当前对话轮次
    variant: string | undefined // 模型 variant（用于合成消息）
}
```

**设计要点：**

- **单会话隔离**：每个 OpenCode 会话独立状态
- **可变设计**：所有状态原地更新（适用于单线程环境）
- **缓存即源语**：toolParameters 总是从消息重建，不持久化

### 3.2 ToolParameterEntry（工具元数据）

```typescript
interface ToolParameterEntry {
    tool: string // 工具名称（如 "read", "write"）
    parameters: any // 工具输入参数
    status?: ToolStatus // "pending" | "running" | "completed" | "error"
    error?: string // 如果 status 为 "error" 的错误消息
    turn: number // 工具被调用时的轮次
}
```

**索引**：`Map<string, ToolParameterEntry>`，键为 `callID`

### 3.3 WithParts（消息包装）

```typescript
interface WithParts {
    info: Message // OpenCode 消息元数据
    parts: Part[] // 消息部分列表（text、tool、step-start 等）
}
```

**关键属性**：`parts` 数组包含对话的原子元素，DCP 遍历此数组进行修剪决策。

---

## 4. 消息转换流水线

### 4.1 流水线阶段

`experimental.chat.messages.transform` Hook 中执行：

```typescript
export const createChatMessageTransformHandler =
    (client, state, logger, config) => async (_input: {}, output: { messages: WithParts[] }) => {
        // 阶段 1：会话管理
        await checkSession(client, state, logger, output.messages)

        // 阶段 2：工具缓存同步
        syncToolCache(state, config, logger, output.messages)

        // 阶段 3：运行自动策略
        deduplicate(state, logger, config, output.messages)
        supersedeWrites(state, logger, config, output.messages)
        purgeErrors(state, logger, config, output.messages)

        // 阶段 4：应用修剪
        prune(state, logger, config, output.messages)

        // 阶段 5：注入 Prunable-Tools 列表
        insertPruneToolContext(state, config, logger, output.messages)

        // 阶段 6：保存调试上下文
        if (state.sessionId) {
            await logger.saveContext(state.sessionId, output.messages)
        }
    }
```

### 4.2 Placeholder 替换机制

**关键设计**：DCP **不删除消息**，仅用短字符串替换内容

**Placeholder 类型：**

```typescript
// 1. 已完成的工具输出（discard/extract 策略）
const PRUNED_TOOL_OUTPUT_REPLACEMENT =
    "[Output removed to save context - information superseded or no longer needed]"

// 2. 出错工具的输入（purge-errors 策略）
const PRUNED_TOOL_ERROR_INPUT_REPLACEMENT = "[input removed due to failed tool call]"

// 3. Question 工具的输入
const PRUNED_QUESTION_INPUT_REPLACEMENT = "[questions removed - see output for user's answers]"
```

**修剪前（示例）：**

```typescript
{
    type: "tool",
    callID: "call_abc123",
    tool: "read",
    state: {
        status: "completed",
        input: { filePath: "/path/to/file.ts" },
        output: "完整文件内容... (5000 tokens)"
    }
}
```

**修剪后：**

```typescript
{
    type: "tool",
    callID: "call_abc123",
    tool: "read",
    state: {
        status: "completed",
        input: { filePath: "/path/to/file.ts" },
        output: "[Output removed to save context - information superseded or no longer needed]"
    }
}
```

### 4.3 修剪应用逻辑

```typescript
export const prune = (state, logger, config, messages): void => {
    // 1. 修剪已完成工具的输出
    for (const msg of messages) {
        if (isMessageCompacted(state, msg)) continue

        for (const part of msg.parts) {
            if (part.type !== "tool") continue
            if (!state.prune.toolIds.includes(part.callID)) continue
            if (part.state.status !== "completed") continue

            // 替换输出
            part.state.output = PRUNED_TOOL_OUTPUT_REPLACEMENT
        }
    }

    // 2. 修剪 question 工具的输入
    pruneToolInputs(state, logger, messages)

    // 3. 修剪出错工具的输入
    pruneToolErrors(state, logger, messages)
}
```

---

## 5. 自动化修剪策略

### 5.1 去重策略（Deduplication）

**目标**：移除重复的工具调用，仅保留最新的。

**算法流程：**

```typescript
export const deduplicate = (state, logger, config, messages): void => {
    // 1. 构建所有工具 ID 的有序列表
    const allToolIds = buildToolIdList(state, messages, logger)

    // 2. 过滤已修剪和受保护的工具
    const unprunedIds = allToolIds.filter((id) => !alreadyPruned.has(id))

    // 3. 按签名分组（工具名 + 归一化参数）
    const signatureMap = new Map<string, string[]>()

    for (const id of unprunedIds) {
        const metadata = state.toolParameters.get(id)

        const signature = createToolSignature(metadata.tool, metadata.parameters)

        if (!signatureMap.has(signature)) {
            signatureMap.set(signature, [])
        }
        signatureMap.get(signature)!.push(id)
    }

    // 4. 每组仅保留最新（最后）的
    const newPruneIds: string[] = []

    for (const [, ids] of signatureMap.entries()) {
        if (ids.length > 1) {
            // 除最后一个外全部修剪
            const idsToRemove = ids.slice(0, -1)
            newPruneIds.push(...idsToRemove)
        }
    }

    state.prune.toolIds.push(...newPruneIds)
}
```

**签名创建（关键）：**

```typescript
function createToolSignature(tool: string, parameters?: any): string {
    if (!parameters) return tool

    // 1. 归一化：移除 null/undefined
    const normalized = normalizeParameters(parameters)

    // 2. 排序：递归排序对象键，保证顺序无关
    const sorted = sortObjectKeys(normalized)

    // 3. 序列化：tool::{"a":1,"b":2}
    return `${tool}::${JSON.stringify(sorted)}`
}

function normalizeParameters(params: any): any {
    if (typeof params !== "object" || params === null) return params
    if (Array.isArray(params)) return params

    const normalized: any = {}
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== null) {
            normalized[key] = value
        }
    }
    return normalized
}

function sortObjectKeys(obj: any): any {
    if (typeof obj !== "object" || obj === null) return obj
    if (Array.isArray(obj)) return obj.map(sortObjectKeys)

    const sorted: any = {}
    for (const key of Object.keys(obj).sort()) {
        sorted[key] = sortObjectKeys(obj[key])
    }
    return sorted
}
```

**示例：**

```typescript
// Turn 1
read(filePath: "/lib/auth.ts") → [文件内容]

// Turn 5
read(filePath: "/lib/auth.ts") → [文件内容]  ← 修剪：重复调用

// Turn 9
read(filePath: "/lib/auth.ts") → [文件内容]  ← 保留：最新版本
```

**保护机制：**

- 跳过 `config.strategies.deduplication.protectedTools` 列表中的工具
- 跳过匹配 `protectedFilePatterns` 文件路径的操作

### 5.2 写覆盖策略（Supersede Writes）

**目标**：修剪已被后续 read 操作覆盖的 write 工具输入。

**逻辑：** 当文件被写入然后读取时，write 的输入内容冗余（当前状态已由 read 捕获）。

```typescript
export const supersedeWrites = (state, logger, config, messages): void => {
    // 1. 追踪按文件的 write 操作（带时间索引）
    const writesByFile = new Map<string, { id: string; index: number }[]>()

    // 2. 追踪按文件的 read 操作（带时间索引）
    const readsByFile = new Map<string, number[]>()

    for (let i = 0; i < allToolIds.length; i++) {
        const metadata = state.toolParameters.get(allToolIds[i])
        const filePath = getFilePathFromParameters(metadata.parameters)

        if (metadata.tool === "write") {
            writesByFile.set(filePath, [
                ...(writesByFile.get(filePath) || []),
                { id: allToolIds[i], index: i },
            ])
        } else if (metadata.tool === "read") {
            readsByFile.set(filePath, [...(readsByFile.get(filePath) || []), i])
        }
    }

    // 3. 查找被后续 read 覆盖的 write
    const newPruneIds: string[] = []

    for (const [filePath, writes] of writesByFile.entries()) {
        const reads = readsByFile.get(filePath)

        for (const write of writes) {
            // 检查是否有 read 在此 write 之后
            const hasSubsequentRead = reads.some((readIndex) => readIndex > write.index)

            if (hasSubsequentRead) {
                newPruneIds.push(write.id)
            }
        }
    }

    state.prune.toolIds.push(...newPruneIds)
}
```

**示例：**

```typescript
// Turn 3
write(filePath: "/config.json", content: "{...}")  → [config 内容]

// Turn 7
write(filePath: "/config.json", content: "{...}")  → [config 内容]  ← 修剪

// Turn 12
read(filePath: "/config.json")                → [更新后内容]
```

**Edge Case 处理：**

- 多个 write 后接一个 read：所有 write 均被覆盖
- 多个 read 后接一个 write：write 未被覆盖，不修剪
- 无后续 read 的 write：不修剪

### 5.3 错误清理策略（Purge Errors）

**目标**：修剪已失败的旧工具的大输入内容，保留错误消息。

```typescript
export const purgeErrors = (state, logger, config, messages): void => {
    const turnThreshold = config.strategies.purgeErrors.turns // 默认：4

    const newPruneIds: string[] = []

    for (const id of unprunedIds) {
        const metadata = state.toolParameters.get(id)

        // 1. 仅处理 status="error" 的工具
        if (metadata.status !== "error") continue

        // 2. 检查是否足够旧
        const turnAge = state.currentTurn - metadata.turn
        if (turnAge >= turnThreshold) {
            newPruneIds.push(id)
        }
    }

    state.prune.toolIds.push(...newPruneIds)
}
```

**示例：**

```typescript
// Turn 2 (error)
bash(command: "npm test") → Error: test failed

// ... skip 4 turns ...

// Turn 7
bash(command: "npm test") → [input: "[input removed due to failed tool call]"]
                           error: Error: test failed  ← 保留
```

**关键特性：**

- 修剪输入（可能很大）但保留错误消息
- 可配置 `turnThreshold`（默认 4）
- 适用于所有类型的工具（bash、build、test 等）

---

## 6. LLM 驱动工具

### 6.1 Discard 工具（无损修剪）

**目的：** AI 主动删除无需保留的工具输出。

**工具规范：**

```typescript
tool({
    description: DISCARD_TOOL_DESCRIPTION,
    args: {
        ids: tool.schema
            .array(tool.schema.string())
            .describe("首个元素为 reason ('completion'|'noise')，其余为数字 ID"),
    },
    async execute(args, toolCtx) {
        // 1. 解析 reason 和 IDs
        const reason = args.ids[0] // "completion" 或 "noise"
        const numericIds = args.ids.slice(1)

        // 2. 验证（随 executePruneOperation 统一处理）
        return executePruneOperation(ctx, toolCtx, numericIds, reason, "Discard")
    },
})
```

**调用示例：**

```
discard(ids: ["completion", "5", "20", "21"])
```

**Result：**

- ID 5, 20, 21 的工具输出被替换为 placeholder
- 显示通知："Task Complete: ~2.5K tokens saved"
- 无知识保留

### 6.2 Extract 工具（有损精简）

**目的：** 保留精炼知识后移除原始内容。

```typescript
tool({
    description: EXTRACT_TOOL_DESCRIPTION,
    args: {
        ids: tool.schema.array(tool.schema.string()).describe("数字 ID 列表"),
        distillation: tool.schema
            .array(tool.schema.string())
            .describe("必需：精炼内容数组（每 ID 一个）"),
    },
    async execute(args, toolCtx) {
        // 验证 distillation（必需）
        if (!args.distillation || args.distillation.length === 0) {
            throw new Error("Missing distillation")
        }

        return executePruneOperation(
            ctx,
            toolCtx,
            args.ids,
            "extraction",
            "Extract",
            args.distillation,
        )
    },
})
```

**调用示例：**

```
extract(
    ids: ["5", "20"],
    distillation: [
        "Auth flow defined in /lib/auth.ts with JWT token validation",
        "API routes use middleware for rate limiting"
    ]
)
```

**Result：**

- 输出被替换为 placeholder
- 显示通知：包含提取的知识
- **知识保留**：distillation 内容显示为 ignored 消息（如果 `showDistillation` 启用）

**Discard vs Extract 对比：**

| 维度     | Discard                       | Extract                   |
| -------- | ----------------------------- | ------------------------- |
| 知识保留 | 无                            | 有（distillation）        |
| Reason   | 必需（"completion"\|"noise"） | 无需（始终 "extraction"） |
| 可见性   | 仅显示修剪列表                | 显示修剪列表 + 精炼内容   |
| 场景     | 噪音、已完成任务              | 需要稍后参考的见解        |

### 6.3 统一执行逻辑

```typescript
async function executePruneOperation(
    ctx,
    toolCtx,
    ids,
    reason,
    toolName,
    distillation?,
): Promise<string> {
    // 1. 验证 IDs（数字、范围内、在缓存中）
    const numericToolIds = ids.map((id) => parseInt(id, 10))

    const toolIdList: string[] = buildToolIdList(state, messages, logger)

    // 2. 检查受保护工具和文件
    for (const index of numericToolIds) {
        const id = toolIdList[index]
        const metadata = state.toolParameters.get(id)

        // 拒绝受保护工具
        if (protectedTools.includes(metadata.tool)) {
            throw new Error("Invalid IDs: protected tool")
        }

        // 拒绝受保护文件
        if (isProtectedFilePath(filePath, config.protectedFilePatterns)) {
            throw new Error("Invalid IDs: protected file")
        }
    }

    // 3. 标记修剪
    const pruneToolIds = numericToolIds.map((index) => toolIdList[index])
    state.prune.toolIds.push(...pruneToolIds)

    // 4. 计算 token 节省
    state.stats.pruneTokenCounter += calculateTokensSaved(state, messages, pruneToolIds)

    // 5. 发送通知
    await sendUnifiedNotification(
        client,
        logger,
        config,
        state,
        sessionId,
        pruneToolIds,
        toolMetadata,
        reason,
        workingDirectory,
        distillation,
    )

    // 6. 持久化状态
    await saveSessionState(state, logger)

    // 7. 返回结果消息
    return formatPruningResultForTool(pruneToolIds, toolMetadata)
}
```

---

## 7. Prunable-Tools 注入机制

### 7.1 系统提示注入

**时机：** `experimental.chat.system.transform` Hook

```typescript
"experimental.chat.system.transform": createSystemPromptHandler(state, logger, config)
```

**提示内容：**

- 教导 LLM 何时使用 `discard` vs `extract`
- 提供决策框架：
    - "No" → discard（默认用于清理）
    - "Yes" → extract（保留精炼知识）
    - "Uncertain" → extract（ safer）
- 重要要求：**决不公开确认注入的上下文**（静默处理）
- 批量修剪推荐

### 7.2 Prunable-Tools 列表注入

**时机：** `experimental.chat.messages.transform` Hook 阶段 5

```typescript
export const insertPruneToolContext = (state, config, logger, messages): void => {
    // 1. 构建可修剪工具列表
    const prunableToolsList = buildPrunableToolsList(state, config, logger, messages)

    if (!prunableToolsList) return

    // 2. 添加 Nudge 消息（如需）
    let nudgeString = ""
    if (
        config.tools.settings.nudgeEnabled &&
        state.nudgeCounter >= config.tools.settings.nudgeFrequency
    ) {
        nudgeString = "\n" + getNudgeString(config)
    }

    const prunableToolsContent = prunableToolsList + nudgeString

    // 3. 创建合成助手消息
    const lastUserMessage = getLastUserMessage(messages)

    // 关键：不在用户消息后立即注入（等待助手回合）
    const lastMessage = messages[messages.length - 1]
    if (lastMessage?.info?.role === "user") {
        return
    }

    messages.push(
        createSyntheticAssistantMessage(
            lastUserMessage,
            prunableToolsContent,
            state.variant ?? lastUserMessage.info.variant,
        ),
    )
}
```

**构建列表逻辑：**

```typescript
const buildPrunableToolsList = (state, config, logger, messages): string => {
    const lines: string[] = []
    const toolIdList: string[] = buildToolIdList(state, messages, logger)

    state.toolParameters.forEach((toolParameterEntry, toolCallId) => {
        // 过滤：
        // 1. 已修剪的
        if (state.prune.toolIds.includes(toolCallId)) return

        // 2. 受保护工具
        if (protectedTools.includes(toolParameterEntry.tool)) return

        // 3. 受保护文件
        if (isProtectedFilePath(filePath, config.protectedFilePatterns)) return

        // 4. 肯定它存在（而非陈旧缓存）
        const numericId = toolIdList.indexOf(toolCallId)
        if (numericId === -1) return

        // 添加到列表：格式 "0: tool: parameter"
        const paramKey = extractParameterKey(toolParameterEntry.tool, toolParameterEntry.parameters)
        lines.push(`${numericId}: ${paramKey}`)
    })

    if (lines.length === 0) return ""

    return wrapPrunableTools(lines.join("\n"))
}
```

**Nudge 机制：**

```typescript
const getNudgeString = (config: PluginConfig): string => {
    const discardEnabled = config.tools.discard.enabled
    const extractEnabled = config.tools.extract.enabled

    if (discardEnabled && extractEnabled) {
        return loadPrompt(`nudge/nudge-both`)
    } else if (discardEnabled) {
        return loadPrompt(`nudge/nudge-discard`)
    } else {
        return loadPrompt(`nudge/nudge-extract`)
    }
}
```

**内容：**

- 每 N 个工具后（`nudgeFrequency`，如 8）
- 提醒 LLM 管理上下文债务
- 鼓励使用 `discard`/`extract`

**Cooldown 机制：**

```typescript
if (state.lastToolPrune) {
    // 使用 Cooldown 消息代替常规列表
    prunableToolsContent = getCooldownMessage(config)
}

const getCooldownMessage = (config: PluginConfig): string => {
    return `<prunable-tools>
Context management was just performed. Do not use ${toolName} again.
A fresh list will be available after your next tool use.
</prunable-tools>`
}
```

**目的：** 防止 LLM 连续多次修剪，每次等待至少一个新工具调用。

---

## 8. 状态管理与缓存机制

### 8.1 工具缓存（ToolParameter Cache）

**设计原则：** 写一次、读多次的缓存

**同步流程：**

```typescript
export const syncToolCache = (state, config, logger, messages): void => {
    state.nudgeCounter = 0
    let turnCounter = 0

    for (const msg of messages) {
        if (isMessageCompacted(state, msg)) continue

        for (const part of msg.parts) {
            if (part.type === "step-start") {
                turnCounter++
                continue
            }

            if (part.type !== "tool" || !part.callID) continue

            // 1. 轮次保护检查
            const isProtectedByTurn =
                config.turnProtection.enabled &&
                state.currentTurn - turnCounter < config.turnProtection.turns

            // 2. 追踪修剪工具调用
            state.lastToolPrune =
                (part.tool === "discard" || part.tool === "extract") &&
                part.state.status === "completed"

            // 3. Nudge 计数器（用于非修剪、非保护工具）
            if (part.tool === "discard" || part.tool === "extract") {
                state.nudgeCounter = 0 // 修剪后重置
            } else if (!protected && !isProtectedByTurn) {
                state.nudgeCounter++
            }

            // 4. 缓存工具参数（幂等）
            if (!state.toolParameters.has(part.callID)) {
                if (isProtectedByTurn) {
                    continue // 不缓存轮次保护的工具
                }

                state.toolParameters.set(part.callID, {
                    tool: part.tool,
                    properties: part.state?.input ?? {},
                    status: part.state.status,
                    error: part.state.status === "error" ? part.state.error : undefined,
                    turn: turnCounter,
                })
            }
        }
    }

    // 5. FIFO 驱逐（防止无界增长）
    trimToolParametersCache(state)
}
```

**缓存驱逐：**

```typescript
const MAX_TOOL_CACHE_SIZE = 1000

export const trimToolParametersCache = (state): void => {
    if (state.toolParameters.size <= MAX_TOOL_CACHE_SIZE) {
        return
    }

    const keysToRemove = Array.from(state.toolParameters.keys()).slice(
        0,
        state.toolParameters.size - MAX_TOOL_CACHE_SIZE,
    )

    for (const key of keysToRemove) {
        state.toolParameters.delete(key)
    }
}
```

**为什么 1000？**

- 假设 200 轮 × 5 工具/轮 = 1000 次调用
- Map 保留插入顺序，`slice(0, excess)` 移除最旧条目

### 8.2 会话生命周期

```typescript
// 1. 创建新会话状态
export function createSessionState(): SessionState {
    return {
        sessionId: null,
        isSubAgent: false,
        prune: { toolIds: [] },
        stats: { pruneTokenCounter: 0, totalPruneTokens: 0 },
        toolParameters: new Map(),
        nudgeCounter: 0,
        lastToolPrune: false,
        lastCompaction: 0,
        currentTurn: 0,
        variant: undefined,
    }
}

// 2. 检测会话变更
export const checkSession = async (client, state, logger, messages): Promise<void> => {
    const lastSessionId = getLastUserMessage(messages)?.info?.sessionID

    if (state.sessionId !== lastSessionId) {
        await ensureSessionInitialized(client, state, lastSessionId, logger, messages)
    }

    // 检测 OpenCode 消息压缩（总结）
    const lastCompaction = findLastCompactionTimestamp(messages)
    if (lastCompaction > state.lastCompaction) {
        state.toolParameters.clear() // 缓存失效
        state.prune.toolIds = []
        state.lastCompaction = lastCompaction
    }

    // 更新轮次计数
    state.currentTurn = countTurns(state, messages)
}

// 3. 初始化会话
export async function ensureSessionInitialized(
    client,
    state,
    sessionId,
    logger,
    messages,
): Promise<void> {
    if (state.sessionId === sessionId) return

    // 重置状态
    resetSessionState(state)
    state.sessionId = sessionId

    // 检测子 Agent（DCP 对子 Agent 禁用）
    state.isSubAgent = await isSubAgentSession(client, sessionId)

    // 检测压缩时间戳
    state.lastCompaction = findLastCompactionTimestamp(messages)
    state.currentTurn = countTurns(state, messages)

    // 加载持久化状态（仅 prune.toolIds 和 stats）
    const persisted = await loadSessionState(sessionId, logger)
    if (persisted === null) return

    state.prune = {
        toolIds: persisted.prune.toolIds || [],
    }
    state.stats = {
        pruneTokenCounter: persisted.stats?.pruneTokenCounter || 0,
        totalPruneTokens: persisted.stats?.totalPruneTokens || 0,
    }
}
```

### 8.3 状态持久化

**存储路径：**

```
~/.local/share/opencode/storage/plugin/dcp/{sessionId}.json
```

**持久化内容：**

```typescript
interface PersistedSessionState {
    sessionName?: string
    prune: Prune // { toolIds: string[] }
    stats: SessionStats // { pruneTokenCounter, totalPruneTokens }
    lastUpdated: string
}
```

**不持久化：**

- ❌ `toolParameters`（缓存 - 总是从消息重建）
- ❌ `nudgeCounter`（从消息重新计算）
- ❌ `lastToolPrune`（从 messages 读取）
- ❌ `currentTurn`（从 messages 重新计算）
- ❌ `variant`（从 last user message 读取）

**持久化时机：**

```typescript
// 1. LLM 驱动修剪后（discard/extract）
await saveSessionState(state, logger)

// 2. 自动策略不保存（优化）
```

---

## 9. OpenCode 插件集成

### 9.1 Hook 系统集成

DCP 注册 6 个 OpenCode Hook：

| Hook                                   | 目的                 | 时机           | 数据流                                           |
| -------------------------------------- | -------------------- | -------------- | ------------------------------------------------ |
| `config`                               | 注册工具和命令       | 插件加载时     | 输入：`opencodeConfig`，原地修改                 |
| `chat.message`                         | 缓存模型 variant     | 每条消息       | 输入：`{ sessionID, variant }`，无输出           |
| `experimental.chat.system.transform`   | 注入修剪指令         | 每次请求       | 输入：`unknown`，输出：修改 `output.system[]`    |
| `experimental.chat.messages.transform` | **核心**：修剪流水线 | 每次请求       | 输入：`{}`，输出：修改 `output.messages[]`       |
| `tool`                                 | 提供 discard/extract | LLM 调用工具时 | 输入：工具参数，输出：结果消息                   |
| `command.execute.before`               | 处理 /dcp 命令       | 用户输入命令   | 输入：`{ command, arguments }`，抛出错误停止执行 |

### 9.2 配置系统

**配置合并优先级**（后者覆盖前者）：

```
1. 默认配置（代码中硬编码）
   ↓
2. 全局配置（~/.config/opencode/dcp.jsonc）
   ↓
3. 配置目录（$OPENCODE_CONFIG_DIR/dcp.jsonc）
   ↓
4. 项目配置（.opencode/dcp.jsonc）
```

**保护工具配置（合并非覆盖）：**

```typescript
// DEFAULT_PROTECTED_TOOLS
const PROTECTED = [
    "task",
    "todowrite",
    "todoread",
    "discard",
    "extract",
    "batch",
    "write",
    "edit",
    "plan_enter",
    "plan_exit",
]

// 合并策略
for (const strategy of ["deduplication", "supersedeWrites", "purgeErrors"]) {
    config.strategies[strategy].protectedTools = [
        ...DEFAULT_PROTECTED_TOOLS,
        ...(userConfig?.strategies?.[strategy]?.protectedTools || []),
    ]
}
```

### 9.3 命令系统

**可用命令：**

```
/dcp              - 显示可用命令
/dcp context      - 显示当前会话的 token 分解和储蓄
/dcp stats        - 显示跨会话的累计统计
```

**命令处理：**

```typescript
"command.execute.before": createCommandExecuteHandler(...)

if (input.command === "dcp") {
    const subcommand = args[0]?.toLowerCase()

    if (subcommand === "context") {
        await handleContextCommand(...)
        throw new Error("__DCP_CONTEXT_HANDLED__")  // 停止命令执行
    }

    if (subcommand === "stats") {
        await handleStatsCommand(...)
        throw new Error("__DCP_STATS_HANDLED__")
    }

    await handleHelpCommand(...)
    throw new Error("__DCP_HELP_HANDLED__")
}
```

**集成要点：**

- 消息通过 `client.session.prompt()` 发送（带 `ignored: true` 标记）
- 抛出特殊错误以防止 OpenCode 执行命令

---

## 10. notification 系统

### 10.1 通知格式化

**3 种通知级别：**

| 级别       | 配置                            | 内容                                   |
| ---------- | ------------------------------- | -------------------------------------- |
| `off`      | `pruneNotification: "off"`      | 不显示任何通知                         |
| `minimal`  | `pruneNotification: "minimal"`  | 仅显示统计：`~1.2K tokens saved total` |
| `detailed` | `pruneNotification: "detailed"` | 统计 + 修剪列表 + 提取内容             |

**代码：**

```typescript
export async function sendUnifiedNotification(
    client,
    logger,
    config,
    state,
    sessionId,
    pruneToolIds,
    toolMetadata,
    reason,
    workingDirectory,
    distillation,
): Promise<boolean> {
    if (config.pruneNotification === "off") return false

    const message =
        config.pruneNotification === "minimal"
            ? buildMinimalMessage(state, reason, showExtraction)
            : buildDetailedMessage(
                  state,
                  reason,
                  pruneToolIds,
                  toolMetadata,
                  workingDirectory,
                  showExtraction,
              )

    await sendIgnoredMessage(client, sessionId, message, params, logger)
    return true
}
```

### 10.2 通知投递

```typescript
export async function sendIgnoredMessage(client, sessionID, text, params, logger): Promise<void> {
    try {
        await client.session.prompt({
            path: { id: sessionID },
            body: {
                noReply: true, // 不生成 AI 回复
                agent: params.agent,
                model: { providerID, modelID },
                parts: [
                    {
                        type: "text",
                        text: text,
                        ignored: true, // 关键：用户不可见的系统消息
                    },
                ],
            },
        })
    } catch (error) {
        logger.error("Failed to send notification", { error })
    }
}
```

**visible vs ignored：**

- **visible 消息**：用户在 UI 中可见
- **ignored 消息**：注入到 AI 上下文但对用户隐藏（DCP 通知使用此类）

---

## 11. 关键设计模式

### 11.1 Strategy Pattern（策略模式）

**应用**：3 个自动修剪策略（`deduplication`、`supersedeWrites`、`purgeErrors`）

**共享接口：**

```typescript
(strategy) => (
    state: SessionState,
    logger: Logger,
    config: PluginConfig,
    messages: WithParts[]
): void
```

**收益：**

- ✅ 易于添加新策略（遵循相同模式）
- ✅ 独立行为（无需互斥管理）
- ✅ 清晰的单一职责

### 11.2 Middleware Pattern（中间件模式）

**应用**：消息转换流水线

```
Messages → checkSession → syncToolCache → deduplicate → supersedeWrites → purgeErrors → prune → injectContext → LLM
```

每个阶段独立变换消息或状态。

### 11.3 Hook Pattern（钩子模式）

**应用**：6 个 OpenCode 生命周期钩子提供扩展点

**类型：**

- **转换钩子**：`system.transform`、`messages.transform`（修改输入/输出）
- **事件钩子**：`chat.message`、`tool`、`command.execute.before`（响应事件）

### 11.4 Injection Pattern（注入模式）

** Synthetic Assistant Messages：**

- 注入 `<prunable-tools>` 列表到对话上下文
- 注入 Nudge 消息提示上下文管理
- 使用 `context_info` 工具格式（对 LLM 熟悉）
- `ignored: true`（对用户隐藏）

**为什么注入而非修改：**

- 不干扰用户消息流
- 可被 LLM 过滤
- 避免修改 Prompt 结构

### 11.5 Protection Pattern（保护模式）

**3 轮保护机制：**

1. **工具保护**：

```typescript
const protectedTools = [
    "task",
    "todowrite",
    "todoread",
    "discard",
    "extract",
    "batch",
    "write",
    "edit",
    "plan_enter",
    "plan_exit",
]
// 这些工具永不修剪
```

2. **文件保护**：

```typescript
const isProtectedFilePath = (filePath, patterns): boolean => {
    return patterns.some((pattern) => minimatch(filePath, pattern))
}

// 配置 protectedFilePatterns: ["*.secret", "config/*.json"]
```

3. **轮次保护**：

```typescript
const isProtectedByTurn =
    config.turnProtection.enabled && state.currentTurn - toolTurn < config.turnProtection.turns

// 工具在 N 轮内不可修剪
```

### 11.6 Cache Pattern（缓存模式）

**ToolParameter Cache：**

- **存储**：`Map<string, ToolParameterEntry>`（O(1) 查找）
- **驱逐**：FIFO 在 1000 条目
- **索引键**：`callID`（OpenCode 生成的唯一标识符）
- **重建逻辑**：每次请求从消息完全重建（源语原则）

**无缓存失效：**

- 无 TTL、无依赖跟踪
- 简化为：会话变更或压缩时清空

### 11.7 Persistence Pattern（持久化模式）

**持久化策略：**

- **最小化持久化**：仅状态（`prune.toolIds` 和 `stats`），不持久化缓存
- **会话隔离**：每会话一个 JSON 文件
- **即时保存**：LLM 修剪后立即保存
- **延迟加载**：会话初始化时加载，缓存从消息重建

---

## 12. 运行逻辑与数据流

### 12.1 完整请求处理流

```
┌─────────────────────────────────────────────────────────┐
│ 用户输入消息                                         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  OpenCode 触发 Hooks                                │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1: chat.message Hook                         │
│  - 提取 variant（如 "claude-sonnet-4"）         │
│  - 缓存：state.variant = input.variant              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2: experimental.chat.system.transform Hook  │
│  - 合并 system prompts                                │
│  - 注入修剪指令："You must use discard/extract..."│
│  - 跳过内部代理人（标题生成、总结器）          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 3: experimental.chat.messages.transform │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 1: checkSession                     │ │
│  │  - 检测会话变更                            │ │
│  │  - 检测消息压缩（summary）                │ │
│  │  - 更新 currentTurn                         │ │
│  └────────────┬─────────────────────────────┘ │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 2: syncToolCache                 │ │
│  │  - 遍历所有消息                             │ │
│  │  - 统计 step-start（轮次）                 │ │
│  │  - 缓存工具元数据（Map<callID, Entry>）  │ │
│  │  - 追踪 nudgeCounter                        │ │
│  │  - 应对轮次保护                              │ │
│  └────────────┬─────────────────────────────┘ │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 3: runStrategies（自动）         │ │
│  │  ├─ deduplicate()                         │ │
│  │  │   - 按签名分组工具                       │ │
│  │  │   - 保留每组最新（最后）                        │ │
│  │  │   - 添加旧重复到 prune.toolIds           │ │
│  ├─ supersedeWrites()                      │ │
│  │  │   - 追踪 writes 和 reads 按文件             │ │
│  │  │   - 修剪被后续 read 覆盖的 write          │ │
│  └─ purgeErrors()                         │ │
│      │   - 找到 status="error" 的工具              │ │
│      │   - 过滤 turnAge >= threshold              │ │
│      │   - 添加到 prune.toolIds                   │ │
│  └────────────┬─────────────────────────────┘ │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 4: prune()                        │ │
│  │  - 遍历所有消息和部分                       │ │
│  │  - 查找 callID 在 prune.toolIds 中             │ │
│  │  - 替换 output 为 placeholder 字符串         │ │
│  └────────────┬─────────────────────────────┘ │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 5: insertPruneToolContext()        │ │
│  │  - 构建可修剪工具列表（过滤：         │ │
│  │  │     prune.toolIds, protectedTools,      │ │
│  │  │     protectedFiles, turn-protected）    │ │
│  │  - 添加 Nudge 消息（如需）              │ │
│  │  - 创建合成助手消息                       │ │
│  │  - 注入到 messages 数组                     │ │
│  └────────────┬─────────────────────────────┘ │
│               │                                     │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │  Step 6: saveContext（调试）            │ │
│  │  - 保存最小化消息到日志                     │ │
│  │  - 路径：~/.config/opencode/logs/...     │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  OpenCode 发送消息给 LLM                           │
│  - 包含修剪后内容（placeholders）                 │
│  - 包含 <prunable-tools> 列表                    │
│  - 包含系统修剪指令                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  LLM 处理并响应                                   │
│                                                       │
│  主动路径（LLM 调用 discard/extract）：              │
│  ┌──────────────────────────────────────────────┐       │
│  │  executePruneOperation()                  │       │
│  │  - 验证 numeric IDs                        │       │
│  │  - 验证不在 protectedTools                  │       │
│  │  - 验证不在 protectedFiles                  │       │
│  │  - 添加到 state.prune.toolIds              │       │
│  │  - 计算 token 节省（@anthropic-ai/tokenizer）│       │
│  │  - 发送通知（ignored 消息）               │       │
│  │  - 持久化到 ~/.local/share/opencode/...   │       │
│  └───────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 12.2 工具缓存生命周期

```
┌─────────────────────────────────────────────────────────┐
│  messages 数组（输入）                              │
│  [                                                  │
│    { role: "user", parts: [...] },              │
│    { role: "assistant", parts: [...] },         │
│    { role: "assistant", parts: [...] },         │
│    ...                               │
│  ]                                                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  syncToolCache() 遍历                          │
│                                                       │
│  for (msg of messages) {                               │
│      for (part of msg.parts) {                          │
│          if (part.type === "step-start") {               │
│              turnCounter++                               │
│          }                                              │
│                                                       │
│          if (part.type === "tool" && part.callID) {      │
│              if (isProtectedByTurn) {                    │
│                  // 跳过：不在缓存，不修剪              │
│              } else if (!toolParameters.has(part.callID)) { │
│                  // 缓存新条目                                │
│                  toolParameters.set(part.callID, {         │
│                      tool: part.tool,                         │
│                      parameters: part.state.input,                │
│                      status: part.state.status,               │
│                      error: part.state.status === "error" ?    │
│                               part.state.error : undefined,   │
│                      turn: turnCounter                      │
│                  })                                           │
│              }                                                  │
│                                                       │
│              // 追踪 nudgeCounter                            │
│              if (part.tool in ["discard", "extract"]) {      │
│                  nudgeCounter = 0                           │
│              } else if (!isProtectedByTurn) {                │
│                  nudgeCounter++                              │
│          }                                                  │
│      }                                                      │
│  }                                                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  toolParameters Map（输出）                          │
│  Map<callID, ToolParameterEntry>                     │
│                                                       │
│  "call_abc123" → {                                 │
│      tool: "read",                                     │
│      parameters: { filePath: "/lib/auth.ts" },           │
│      status: "completed",                              │
│      error: undefined,                                  │
│      turn: 7                                           │
│  }                                                     │
│                                                       │
│  "call_def456" → {                                 │
│      tool: "write",                                    │
│      parameters: { filePath: "/config.json", "..."} │
│      status: "completed",                              │
│      error: undefined,                                  │
│      turn: 3                                           │
│  }                                                     │
│  ...（最多 1000 条目）                                  │
└─────────────────────────────────────────────────────────┘
```

---

## 13. Token 计算与统计

### 13.1 Token 计算

**Tokenizer 使用：** `@anthropic-ai/tokenizer`

```typescript
export const calculateTokensSaved = (state, messages, pruneToolIds): number => {
    let totalTokens = 0

    for (const id of pruneToolIds) {
        // 1. 查找对应消息部分
        const part = findToolPart(state, messages, id)
        if (!part) continue

        // 2. 计算不同类型的 token 保存
        if (part.state.status === "error") {
            // 错误：为输入内容（被移除）
            const inputStr = stringify(part.state.input)
            totalTokens += countTokens(inputStr)
        } else if (part.tool === "question") {
            // Question：为输入内容（questions 数组）
            const inputStr = stringify(part.state.input?.questions)
            totalTokens += countTokens(inputStr)
        } else {
            // 一般：为输出内容（被移除）
            const outputStr = part.state.output
            totalTokens += countTokens(outputStr ?? "")
        }
    }

    return totalTokens
}

function countTokens(text: string): number {
    try {
        // 使用 Anthropic tokenizer
        return encode(text).length
    } catch {
        // 回退：估算（字符数 / 4）
        return Math.ceil(text.length / 4)
    }
}
```

### 13.2 统计数据

**会话级别（仅当前会话）：**

```typescript
state.stats.pruneTokenCounter
// - 每次 LLM 修剪（discard/extract）后累加
// - 自动策略不更新此计数器
// - 超过会话不持久化此值
```

**累记统计（跨会话）：**

```typescript
state.stats.totalPruneTokens
// - 每次 LLM 修剪：
//   - 加到 pruneTokenCounter
//   - 然后加到 totalPruneTokens
// - 持久化到磁盘
// - 跨进程存活
```

**统计显示：**

```typescript
/dcp stats 输出：

▣ DCP | ~12.5K tokens saved total

（跨所有会话的累计）

/dcp context 输出：

▣ DCP | ~1.2K tokens saved total

▣ Pruning (~2.5K)
→ read: /lib/auth.ts
→ grep: "export.*function"
→ bash: npm test

▣ Extracted
───
Auth flow defined in /lib/auth.ts with JWT token validation
API routes use middleware for rate limiting
```

---

## 14. 保护机制详解

### 14.1 工具保护

**默认受保护工具列表：**

```typescript
const DEFAULT_PROTECTED_TOOLS: string[] = [
    "task", // OpenCode 任务管理
    "todowrite", // Todo 操作
    "todoread", // Todo 操作
    "discard", // DCP 修剪工具
    "extract", // DCP 修剪工具
    "batch", // 批操作
    "write", // 文件写入
    "edit", // 文件编辑
    "plan_enter", // 计划进入
    "plan_exit", // 计划退出
]
```

**为什么保护这些：**

- **任务管理工具**（task、todowrite、todoread）：
    - 用于跟踪进度，非内容处理
    - 频繁引用，修剪将破坏上下文

- **DCP 工具**（discard、extract）：
    - 递归危险：修剪工具输出致工具中断
    - 保护自身不被修剪

- **文件操作工具**（write、edit、batch）：
    - 提供审计日志
    - 输入验证和预处理

**策略级别覆盖：**

```typescript
{
    strategies: {
        deduplication: {
            protectedTools: [...DEFAULT_PROTECTED_TOOLS, "read", "grep"]
        },
        supersedeWrites: {
            protectedTools: [...DEFAULT_PROTECTED_TOOLS]  // 无策略特定工具
        },
        purgeErrors: {
            protectedTools: [...DEFAULT_PROTECTED_TOOLS, "bash"]
        }
    }
}
```

### 14.2 文件保护

**模式匹配：**

```typescript
const isProtectedFilePath = (filePath: string | undefined, patterns: string[]): boolean => {
    if (!filePath) return false
    return patterns.some((pattern) => {
        return filePath.match(new minimatch.Minimatch(pattern))
    })
}
```

**配置示例：**

```jsonc
{
    "protectedFilePatterns": [
        "*.secret", // 所有 .secret 文件
        "config/*.json", // config 目录中的 JSON 文件
        ".env", // 环境变量文件
        "**/*.pem", // 所有 PEM 证书文件
        "workspace至关文件/*", // 特定目录
    ],
}
```

**应用于：**

- `read` 工具的 `filePath` 参数
- `write` 工具的 `filePath` 参数
- `edit` 工具的 `filePath` 参数
- 所有工具的 `filePath` 相关参数提取

**使用场景：**

- **敏感配置**：始终在上下文中可用
- **证书/密钥**：避免因修剪被迫重新输入
- **工作空间配置**：关键设置受保护

### 14.3 轮次保护

**目的：** 防止在工具调用后立即修剪，给 AI 时间引用最近的工具输出。

**逻辑：**

```typescript
const isProtectedByTurn =
    config.turnProtection.enabled && // 功能开关
    config.turnProtection.turns > 0 && // 有效阈值
    state.currentTurn - toolTurn < config.turnProtection.turns // 距离检查
```

**示例（`turnProtection.turns = 4`）：**

```
Turn 1: read(/lib/auth.ts) → [文件内容]
         ↓
Turn 2: grep("export.*function")  → [搜索结果]
         ↓
Turn 3: bash(npm test)         → [测试输出]
         ↓
Turn 4: write(/config.json, ...)  → [写入成功]
         ↓
Turn 5: AI 考虑修剪 → 可修剪 Turn 1 的 read ✓
         ← 工具在 4 轮外，修剪安全
```

**对策略的影响：**

```typescript
// syncToolCache() 中：
if (isProtectedByTurn) {
    continue // 不缓存此工具，因此不出现在 prunable-tools 列表
}

// deduplicate() 中：
for (const id of unprunedIds) {
    // 仅非轮次保护的工具参与去重
    // 轮次保护的工具从列表中排除
}
```

**行为：**

- ✅ 对 LLM 隐藏（不在 `<prunable-tools>` 列表）
- ⚠️ 无人为在列表中的工具调用 being protected 的影响
- 📝 自动策略会忽略它们（不在缓存）
- 🔓 `currentTurn - toolTurn < threshold` 后可用修剪

---

## 15. 消息压缩处理

### 15.1 压缩检测

OpenCode 周期性压缩对话历史（类似创建总结）。

```typescript
export const findLastCompactionTimestamp = (messages): number => {
    for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i]

        // 压缩消息标记
        if (msg.info.role === "assistant" && msg.info.summary === true) {
            // 系统创建的总结消息
            return msg.info.time.created
        }
    }
    return 0
}
```

### 15.2 压缩响应

**1. 清空工具缓存：**

```typescript
if (lastCompaction > state.lastCompaction) {
    state.toolParameters.clear() // 缓存失效
    state.prune.toolIds = [] // 清空修剪记录
    state.lastCompaction = lastCompaction
}
```

**为什么清空：**

- 压缩前消息可能已不相关
- 压缩后的消息可能重新编号
- 保留旧缓存元数据可能导致不一致

**2. 跳过压缩消息：**

```typescript
export const isMessageCompacted = (state, msg): boolean => {
    return msg.info.time.created < state.lastCompaction
}

// 用于所有过滤逻辑：
for (const msg of messages) {
    if (isMessageCompacted(state, msg)) {
        continue // 跳过旧消息
    }

    // 处理新消息...
}
```

---

## 16. 子 Agent 检测与处理

### 16.1 子 Agent 概念

OpenCode 可能生成子 Agents 执行特定任务（如代码审查、总结器）。

**为什么 DCP 对子 Agents 禁用：**

1. **干扰**：修剪可能破坏子 Agent 的总结逻辑
2. **精炼冲突**：子 Agents 自己产生精炼内容，DCP 修剪导致重复
3. **上下文需求**：子 Agents 需要完整上下文完成总结任务

### 16.2 检测机制

```typescript
export async function isSubAgentSession(client, sessionId): Promise<boolean> {
    try {
        // 调用 OpenCode API 获取会话元数据
        const session = await client.session.get({ path: { id: sessionId } })

        // 如果拥有 parentID，则是子 Agent 会话
        return session.data?.parentID !== undefined && session.data?.parentID !== null
    } catch {
        // API 调用失败：假设非子 Agent
        return false
    }
}
```

### 16.3 子 Agent 行为

**检查与跳过：**

```typescript
// system prompt hook
if (state.isSubAgent) {
    return // 不注入修剪指令
}

// messages transform hook
if (state.isSubAgent) {
    return // 不运行修剪流水线
}

// tool hook
// 不对子 Agent 会话注册 discard/extract 工具
```

**结果：**

- 子 Agents 完全按正常模式运行
- 无修剪干扰
- 无错误或警告

---

## 17. 日志系统

### 17.1 日志文件结构

```
~/.config/opencode/logs/dcp/
├── daily/                          # 每日日志文件
│   ├── 2026-01-20.log
│   ├── 2026-01-21.log
│   └── ...
└── context/                         # 消息上下文快照
    └── {sessionId}/
        ├── context_001.json
        ├── context_002.json
        └── ...
```

### 17.2 日志级别

| 级别    | 条件                  | 输出                           |
| ------- | --------------------- | ------------------------------ |
| `info`  | `config.debug = true` | 会话变更、修剪操作、缓存同步   |
| `debug` | `config.debug = true` | 详细的决策逻辑、数据结构       |
| `warn`  | 非阻塞问题            | 缓存未命中、API 失败、配置警告 |
| `error` | 严重失败              | 持久化失败、通知发送失败       |

**示例日志：**

```
[2026-01-20 14:23:45] [INFO] Session changed: null -> sess_abc123
[2026-01-20 14:23:45] [INFO] isSubAgent = false
[2026-01-20 14:23:45] [INFO] Initializing session state { sessionId: sess_abc123 }
[2026-01-20 14:23:46] [DEBUG] Syncing tool parameters from OpenCode messages
[2026-01-20 14:23:47] [DEBUG] Cached tool id: call_123 (created on turn 7)
[2026-01-20 14:23:47] [DEBUG] Cached tool id: call_124 (created on turn 7)
[2026-01-20 14:23:48] [DEBUG] Marked 2 duplicate tool calls for pruning
[2026-01-20 14:23:49] [DEBUG] Pruned outputs: 2 tool outputs replaced
[2026-01-20 14:23:50] [INFO] Pruning complete: ~2.5K tokens saved
```

### 17.3 上下文最小化

```typescript
const minimizeForDebug = (messages: WithParts[]): any[] => {
    return messages.map((msg) => ({
        // 仅保留以下字段
        info: {
            id: msg.info.id,
            role: msg.info.role,
            time: msg.info.time,
        },
        // 对于 tool parts，移除大输出
        parts: msg.parts.map((part) => {
            if (part.type === "tool") {
                return {
                    type: part.type,
                    callID: part.callID,
                    tool: part.tool,
                    state: {
                        status: part.state.status,
                        // output 被替换或移除以减少日志大小
                        output:
                            part.state.output?.length > 100
                                ? `[${part.state.output.slice(0, 100)}...]`
                                : part.state.output,
                    },
                }
            }
            return part
        }),
    }))
}
```

**目的：**

- 减少日志文件大小
- 加快日志写入和读取
- 保留调试所需的关键信息

---

## 18. 架构决策与权衡

### 18.1 为什么用 Placeholder 而非删除

**设计选择：** 保留消息结构，替换内容

**优点：**

- ✅ 保持对话结构（消息统计、轮次计数）
- ✅ 对 LLM 透明（显示被移除的内容）
- ✅ 维护消息引用（无断链接）
- ✅ 非破坏性（保留元数据）

**缺点：**

- ❌ 标记修剪的上下文仍在（与开源存储历史冲突）
- ❌ 稍微增加 token 消耗（placeholder 自身占 token）

**权衡：** 透明性和结构性 > 节省

### 18.2 为什么合成消息注入

**设计选择：** 创建假助手消息而非修改最后助手消息

**优点：**

- ✅ 不干扰用户消息流（未立即回复后注入）
- ✅ 使用熟悉工具输出格式（`context_info`）
- ✅ LLM 可过滤（如果需专注）
- ✅ 避免破坏消息链接（`parentID`）

**缺点：**

- ❌ 增加消息计数
- ❌ 合成消息影响轮次统计

**权衡：** 非侵入性注入清晰标记 > 修改现有消息

### 18.3 为什么分离策略和修剪

**关注点分离：**

```typescript
// 策略：标记什么
deduplicate() // 分析 → 添加到 state.prune.toolIds
supersedeWrites() // 分析 → 添加到 state.prune.toolIds
purgeErrors() // 分析 → 添加到 state.prune.toolIds

// 修剪：如何修剪
prune() // 应用 placeholder 替换
```

**收益：**

- ✅ 易于组合策略（可同时运行全部）
- ✅ 清晰权限（策略标记不可同步修改消息）
- ✅ 策略可独立测试

### 18.4 为什么重建缓存而非增量更新

**设计选择：** 每次请求重建 `toolParameters` Map

**优点：**

- ✅ 源语原则（消息即真理）
- ✅ 无缓存一致性问题（无 updates-in-place）
- ✅ 简单实现（无增量逻辑、无无效跟踪）

**缺点：**

- ❌ O(n) 重建成本（但消息已被压缩）
- ❌ 重复解析消息

**权衡：** 简单性 > 性能（合理，因压缩限制消息数量）

---

## 19. 扩展点与可定制化

### 19.1 添加新的自动策略

**模式：**

```typescript
export const yourStrategy = (
    state: SessionState,
    logger: Logger,
    config: PluginConfig,
    messages: WithParts[]
): void => {
    // 1. 检查是否启用
    if (!config.strategies.yourStrategy.enabled) return

    // 2. 分析消息或缓存
    const pruneCandidates = findCandidates(...)

    // 3. 添加到 prune.toolIds
    for (const id of pruneCandidates) {
        state.prune.toolIds.push(id)
    }

    // 4. 更新统计
    state.stats.totalPruneTokens += calculateTokensSaved(state, messages, pruneCandidates)
}

// 在 index.ts 中
import { yourStrategy } from "./strategies/your-strategy"
yourStrategy(state, logger, config, messages)
```

**示例策略点子：**

- 历史文件移除（删除后修剪 write）
- 相关性修剪（基于语义相似建模）
- 引用计数修剪（未引用的旧操作）

### 19.2 添加新的自定义工具

**自定义工具：**

```typescript
export const createCustomTool = (ctx: PruneToolContext) => {
    return tool({
        description: "自定义修剪工具",
        args: {
            custom_param: tool.schema.string().describe("..."),
        },
        async execute(args, toolCtx) {
            // 自定义逻辑
            const pruneIds = determinePruneIds(args)

            // 共享执行逻辑
            return await executePruneOperation(
                ctx, toolCtx, pruneIds, "customReason", "CustomTool"
            )
        }
    })
}

// 在 index.ts tool hook 中注册
"tool": {
    ...existingTools,
    customTool: createCustomTool(...)
}
```

### 19.3 添加新的 Slash 命令

```typescript
export const handleCustomCommand = async ({
    client, state, logger, sessionId, messages
}) => {
    // 自定义逻辑
    const result = calculateCustomMetrics(messages, state)

    // 发送结果为 ignored 消息
    await client.session.prompt({
        path: { id: sessionId },
        body: {
            noReply: true,
            parts: [{
                type: "text",
                text: result,
                ignored: true
            }]
        }
    })
}

// 在 hooks.ts 中
import { handleCustomCommand } from "./commands/custom"

if (subcommand === "custom") {
    await handleCustomCommand(...)
    throw new Error("__DCP_CUSTOM_HANDLED__")
}
```

### 19.4 配置扩展点

**添加新配置选项：**

```typescript
// 1. 在 dcp.schema.json 中定义
{
    "strategies": {
        "yourStrategy": {
            "enabled": { "type": "boolean", "default": false },
            "customParam": { "type": "number", "default": 10 }
        }
    }
}

// 2. 在 PluginConfig 接口中定义
interface PluginConfig {
    // ... 现有字段
    strategies: {
        // ... 现有字段
        yourStrategy?: {
            enabled: boolean
            customParam?: number
        }
    }
}

// 3. 在策略中使用
const customParam = config.strategies.yourStrategy?.customParam ?? 10
```

---

## 20. 性能特征与限制

### 20.1 性能指标

| 操作                     | 复杂度     | 运行时分析                 |
| ------------------------ | ---------- | -------------------------- |
| 缓存同步 (syncToolCache) | O(n)       | 扫描所有消息，但受压缩限制 |
| 去重 (deduplicate)       | O(m log m) | m = 非保护工具数           |
| 写覆盖 (supersedeWrites) | O(w + r)   | w = writes, r = reads      |
| 错误清理 (purgeErrors)   | O(e)       | e = 错误工具数             |
| 修剪 (prune)             | O(n × p)   | n = 消息数，p = parts/消息 |
| 缓存查找                 | O(1)       | Map.get() 恒定时间         |
| Token 计算               | O(k)       | k = 修剪 ID 数             |
| 状态持久化               | O(1)       | 磁盘写入                   |

### 20.2 内存使用

**每个会话内存占用估算：**

```typescript
// SessionState（约 1 KB）
{
    sessionId: string (50 bytes),
    isSubAgent: boolean (1 byte),
    prune.toolIds: string[] (~200 bytes),
    stats: { ... } (16 bytes),
    variant?: string (20 bytes)
} ≈ 300 bytes

// toolParameters Map（核心）
Map<callID, ToolParameterEntry>

每个 ToolParameterEntry（约 500 bytes）:
{
    tool: string ("read" - 20 bytes),
    parameters: any (~200 bytes),
    status: string ("completed" - 20 bytes),
    error?: string (0-100 bytes),
    turn: number (8 bytes)
}

最大 1000 条目 ≈ 500 KB
```

**总计每会话：** 约 501 KB

**对比 OpenCode 总体：** 微不足道（相比消息历史占数百 MB）

### 20.3 已知限制

1. **无跨会话学习**：每会话从头开始
    - 影响：重复相似会话中的修剪决策
    - 解决：使用不同 AI 策略或持久化学习模型

2. **无多轮规划**：策略无状态跨请求
    - 影响：无法协调修剪决策（如修剪要点后修剪子要点）
    - 解决：添加状态到每个策略跟踪尚未修剪的工具

3. **缓存重建开销**：每请求 O(n) 扫描
    - 影响：长会话延迟增加
    - 缓解：压缩限制消息数（OpenCode 默认行为）

4. **无回滚**：修剪不可逆
    - 影响：修剪后原始内容从该请求丢失
    - 解决：记录修剪前上下文（debug 模式已启用）

5. **静态受保护工具列表**：受保护工具不可配置
    - 影响：无法保护特定任务类型
    - 解决：策略级保护（已实现）

---

## 21. 关键优势与适用场景

### 21.1 DCP 的优势

| 优势                    | 描述                                            |
| ----------------------- | ----------------------------------------------- |
| **零 LLM 成本自动策略** | 去重、写覆盖、错误清理每次请求运行，无 API 调用 |
| **智能上下文管理**      | 通过 Nudge 和系统提示教导 LLM 主动修剪          |
| **透明性**              | Placeholder 清晰显示被移除内容                  |
| **可配置性**            | 4 级配置、策略开关、保护规则                    |
| **会话隔离**            | 状态每会话独立，无跨会话污染                    |
| **最小持久化**          | 仅关键状态保存，支持跨重启                      |
| **多层保护**            | 工具级、文件级、轮次级保护防过度修剪            |
| **调试友好**            | 详细日志、上下文快照、诊断命令                  |

### 21.2 最佳适用场景

✅ **高价值场景：**

- 长调试会话（50+ 轮）
- 多文件重构会话
- 重复文件读取/检查会话
- 纠缠解决循环（多次尝试）
- 文档生成任务（大量读取）

⚠️ **中等价值场景：**

- 中等会话（20-50 轮）
- 一次性任务（无长会话）
- 按轮次计费的模型（需权衡缓存命中率）

❌ **低价值场景：**

- 短会话（< 10 轮）
- 高度依赖缓存的模型
- 简单查询任务（单文件读取回答）
- 首次全新会话

---

## 22. 总结与技术栈

### 22.1 技术栈

| 层次           | 技术                     | 版本             |
| -------------- | ------------------------ | ---------------- |
| **运行时**     | Node.js / TypeScript     | ES2022+          |
| **插件 SDK**   | @opencode-ai/sdk         | v2.x             |
| **插件框架**   | @opencode-ai/plugin      | >= 0.13.7        |
| **Token 计数** | @anthropic-ai/tokenizer  | 最新版           |
| **配置解析**   | jsonc-parser             | 用于 .jsonc 文件 |
| **文件匹配**   | minimatch                | glob 模式匹配    |
| **日志**       | node:fs + winston/自定义 | 日志到文件       |

### 22.2 架构模式总结

```
┌─────────────────────────────────────────────────────────┐
│              设计模式应用                    │
├─────────────────────────────────────────────────────────┤
│                                                     │
│ 1. Strategy Pattern                                  │
│    - deduplicate, supersedeWrites, purgeErrors   │
│    - 统一接口，独立实现                   │
│                                                     │
│ 2. Middleware Pattern                               │
│    - 消息转换流水线                            │
│    - 顺序处理阶段                              │
│                                                     │
│ 3. Hook Pattern                                     │
│    - 6 个 OpenCode lifecycle hooks             │
│    - 插件扩展点                            │
│                                                     │
│ 4. Injection Pattern                                 │
│    - Synthetic assistant messages                     │
│    - ignored 消息注入到上下文                 │
│                                                     │
│ 5. Protection Pattern                               │
│    - 工具、文件、轮次保护                     │
│    - 防护栏防过度修剪                       │
│                                                     │
│ 6. Cache Pattern                                    │
│    - Map-based tool cache                         │
│    - FIFO 淘汰 (1000 entries)                 │
│                                                     │
│ 7. Persistence Pattern                              │
│    - 会话级 JSON 存储                            │
│    - 最小化持久化                                   │
│                                                     │
│ 8. Plugin Pattern                                  │
│    - 工厂函数返回能力对象               │
│    - 异步初始化                                   │
└─────────────────────────────────────────────────────────┘
```

### 22.3 核心设计原则

1. **分而治之**：策略标记内容、修剪应用内容、缓存提供元数据
2. **源语原则**：消息即真理，缓存从它重建
3. **最小持久化**：仅保存决策（prune IDs），不保存数据（缓存）
4. **保护至上**：多轮保护防过度修剪
5. **透明性**：Placeholder 清晰显示被移除内容
6. **无侵入**：使用合成消息而非修改现有消息
7. **端而治之**：不自动扩展现有代码，专注问题
8. **可组合性**：策略可混合、可重用共享逻辑

---

## 23. 与同类设计对比分析

### 23.1 对比其他上下文管理方案

| 维度         | DCP (本设计)           | 传统上下文窗口管理     | 基于向量的 RAG     |
| ------------ | ---------------------- | ---------------------- | ------------------ |
| **修剪时机** | 主动修剪（LLM 工具）   | 被动丢弃（滚动元数据） | 按相关查询检索     |
| **用户控制** | AI 决定 + 自动策略     | AI 输入提示选择        | 系统算法决定       |
| **透明性**   | 高（Placeholder 清晰） | 低（静默丢弃）         | 依赖检索质量       |
| **召回保证** | AI 决定召回自动策略    | 无（最旧消息丢弃）     | 取决于向量质量     |
| **成本**     | 仅修剪后 LLM 调用      | 无额外成本（滚动）     | 检索 Query 成本    |
| **维护性**   | 低（配置驱动）         | 高（硬编码窗口大小）   | 中（向量 DB 维护） |
| **适用模型** | 所有 LLM（通用工具）   | 原生支持 models        | 支持嵌入模型       |

### 23.2 DCP 的独特优势

1. **LLM 驱动 + 自动混合**：结合 AI 的语义理解与自动化的确定性规则
2. **零成本自动**：自动策略零 LLM 调用，AI 主动修剪时付费
3. **无基础设施**：无需向量数据库、无需外部存储、自包含插件
4. **可插拔策略**：易于添加新修剪逻辑（遵循策略模式）
5. **细粒度保护**：工具级、文件级、轮次级的多层保护

---

## 24. 实施建议

### 24.1 可参考的最佳实践

**从 DCP 可学到的：**

1. **清晰的抽象分离**：
    - 策略（标记）：实现复杂分析逻辑
    - 应用（修剪）：实现简单替换逻辑
    - 支持（缓存）：提供元数据给两者

2. **保护驱动设计**：
    - 默认保守（保护关键工具）
    - 可配置例外
    - 多层保护栈

3. **合成消息非侵入注入**：
    - 不修改用户消息属性
    - 创建新消息标记为 ignored
    - 保留消息链完整性

4. **来源真理原则**：
    - 缓存从主数据重建
    - 不持久化可重建状态
    - 压缩检测清除陈旧缓存

5. **适度的最小化持久化**：
    - 仅保存决策（如 prune.toolIds）
    - 不保存数据（如 toolParameters）
    - 快速初始化、无状态腐烂风险

### 24.2 用于新系统开发的模式

**上下文管理核心模式：**

```typescript
// 1. Hook-based 插件接口
const plugin = (ctx) => ({
    lifecycle_hook: handler(ctx),
    transform_hook: (input, output) => {
        /* transform */
    },
})

// 2. 策略实现
interface Strategy<T> {
    enabled(config: Config): boolean
    analyze(state: State, input: T): string[] // 返回要移除的 ID
    apply(state: State, ids: string[]): void // 应用移除
}

// 3. 保护层
const protections = [isProtectedTool(id), isProtectedFile(filePath), isProtectedByTurn(toolTurn)]

// 4. Placeholder 替换
const prune = (items, replacement) => {
    items.forEach((item) => (item.content = replacement))
}
```

---

## 附录 A：完整文件清单

```
opencode-dynamic-context-pruning/
├── index.ts                          # 插件入口点
├── package.json                       # NPM 包配置
├── tsconfig.json                      # TypeScript 配置
├── dcp.schema.json                    # IDE 自动补全的配置 schema
├── README.md                          # 项目文档
├── lib/                               # 源代码目录
│   ├── state/                          # 状态管理层
│   │   ├── types.ts                   # SessionState, ToolParameterEntry 接口
│   │   ├── state.ts                   # 会话生命周期函数
│   │   ├── tool-cache.ts              # 工具参数缓存同步
│   │   ├── persistence.ts            # 会话状态持久化
│   │   ├── utils.ts                  # 状态辅助函数
│   │   └── index.ts                  # 状态模块导出
│   ├── strategies/                      # 修剪策略实现
│   │   ├── deduplication.ts          # 重复工具移除
│   │   ├── purge-errors.ts           # 错误工具清理
│   │   ├── supersede-writes.ts       # 写覆盖处理
│   │   ├── tools.ts                 # LLM 驱动工具（discard/extract）
│   │   ├── utils.ts                 # Token 计算、统计格式化
│   │   └── index.ts                 # 策略模块导出
│   ├── messages/                        # 消息转换层
│   │   ├── prune.ts                  # Placeholder 替换逻辑
│   │   ├── inject.ts                 # <prunable-tools> 注入
│   │   ├── utils.ts                 # 合成消息创建、ID 列表构建
│   │   └── index.ts                 # 消息模块导出
│   ├── hooks/                           # Hook 处理器
│   │   └── hooks.ts                # 所有 OpenCode hooks 实现
│   ├── ui/                              # 用户界面组件
│   │   ├── notification.ts            # Toast 通知发送
│   │   ├── utils.ts                 # 统计格式化、路径缩短
│   │   └── index.ts                 # UI 模块导出
│   ├── config.ts                        # 配置管理（4 级合并）
│   ├── logger.ts                        # 日志系统（日/上下文）
│   ├── protected-file-patterns.ts      # 受保护文件检测逻辑
│   ├── shared-utils.ts                 # 跨模块共享的辅助函数
│   ├── commands/                        # Slash 命令实现
│   │   ├── context.ts               # /dcp context 命令
│   │   ├── stats.ts                 # /dcp stats 命令
│   │   └── help.ts                  # /dcp help 命令
│   └── prompts/                          # 提示模板
│       ├── discard-tool-spec         # discard 工具描述
│       ├── extract-tool-spec         # extract 工具描述
│       ├── nudge/                   # Nudge 消息模板
│       │   ├── nudge-both
│       │   ├── nudge-discard
│       │   └── nudge-extract
│       └── system/                  # 系统 Prompt 模板
│           ├── system-prompt-both      # discard + extract 都启用
│           ├── system-prompt-discard   # 仅 discard 启用
│           └── system-prompt-extract   # 仅 extract 启用
└── tests/                             # 测试目录
    └── run-tests.ts                 # 测试执行器
```

---

## 附录 B：配置参考

### B.1 默认配置

```jsonc
{
    // 插件开关
    "enabled": true,

    // 调试模式
    "debug": false,

    // 通知级别: "off" | "minimal" | "detailed"
    "pruneNotification": "minimal",

    // 启用命令: /dcp context, /dcp stats, /dcp help
    "commands": true,

    // 轮次保护
    "turnProtection": {
        "enabled": true,
        "turns": 4,
    },

    // 受保护文件 glob 模式
    "protectedFilePatterns": [],

    // LLM 工具设置
    "tools": {
        "settings": {
            // Nudge 机制：每 N 工具提示修剪
            "nudgeEnabled": true,
            "nudgeFrequency": 8,

            // 受保护工具（与策略合并）
            "protectedTools": [
                "task",
                "todowrite",
                "todoread",
                "discard",
                "extract",
                "batch",
                "write",
                "edit",
                "plan_enter",
                "plan_exit",
            ],
        },

        // discard 工具
        "discard": {
            "enabled": true,
        },

        // extract 工具
        "extract": {
            "enabled": true,
            // 显示提取内容到通知
            "showDistillation": false,
        },
    },

    // 自动策略
    "strategies": {
        "deduplication": {
            "enabled": true,
            // 策略额外受保护工具（与 baseline 合并）
            "protectedTools": [],
        },

        "supersedeWrites": {
            "enabled": true,
            // 此策略无额外受保护工具
            "protectedTools": [],
        },

        "purgeErrors": {
            "enabled": true,
            "turns": 4, // 多少轮后清理错误
            // 策略额外受保护工具
            "protectedTools": [],
        },
    },
}
```

### B.2 配置合并顺序

```
默认代码值
    ↓
~/.config/opencode/dcp.jsonc     （全局用户配置）
    ↓
$OPENCODE_CONFIG_DIR/dcp.jsonc    （环境特定配置）
    ↓
.opencode/dcp.jsonc              （项目配置）
    ↓
最终生效配置
```

**合并规则：**

- `protectedTools`：union（合并，不覆盖）
- 其他字段：override（后者覆盖前者）
- `enabled` 对象：合并 child objects

---

## 结论

Dynamic Context Pruning (DCP) 插件是一个**精心设计的上下文管理系统**，通过以下核心原则实现高效的对话上下文优化：

1. **混合自动化**：3 个零 LLM 成本的自动策略 + LLM 驱动的智能决策
2. **保护驱动**：多层次保护（工具、文件、轮次）防止过度修剪
3. **透明可观察**：Placeholder 清晰显示修剪，详细日志和诊断命令
4. **可扩展架构**：策略模式使添加新修剪逻辑简单，Hook 系统提供清晰扩展点
5. **最小复杂度**：分离关注点（策略标记 → 应用修剪 → 缓存供给）
6. **会话隔离**：每会话独立状态，无跨会话副作用

**关键创新：**

- 通过 **合成消息注入**实现非侵入式上下文引导
- **Placeholder 替换**保持对话结构完整性
- **来源真理原则**从消息重建缓存而非持久化
- **Nudge 机制**教导 LLM 而非强制行为

适用于 API 计费用的 LLM 服务的长会话场景。对请求计费模式的价值最大，需慎重权衡缓存命中率影响。

**实施新系统时可参考的设计模式：**

- Hook-based 插件架构
- 策略模式，实现可组合业务规则
- 保护模式，建立多层安全护栏
- 注入模式，提供上下文信息而不改变现有数据
- 缓存同步模式，每次请求重建支持源语原则
