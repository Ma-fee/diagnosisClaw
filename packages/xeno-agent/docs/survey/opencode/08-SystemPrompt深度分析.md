# System Prompt 深度分析

## 为什么 Prompt 这么长？(6k+ 字符)

OpenCode 的第一轮 System Prompt 确实比较庞大，这并非代码冗余，而是为了构建一个**全知全能的上下文环境**。通过分析源码，我们发现其由以下几个动态部分组成：

### 1. 基础人格设定 (Base Persona)

**占比**: ~15%
**来源**: `src/session/prompt/anthropic.txt` 或 `codex.txt`

定义了 Agent 的核心行为准则：

- **角色**: "You are OpenCode, a sophisticated AI coding assistant..."
- **风格**: 简洁、不使用 emoji、不闲聊
- **安全**: 禁止破坏性命令、保护隐私
- **Git 规范**: Commit message 风格指南

### 2. 动态环境上下文 (Environment Context)

**占比**: ~20%
**来源**: `SystemPrompt.environment()`

这是 Prompt 变长的主要原因之一。系统会自动注入：

- **当前时间**: `Wed Jan 21 2026`
- **操作系统**: `Darwin 23.0.0`
- **Shell 环境**: `/bin/zsh`
- **文件树 (File Tree)**: 系统会运行 `rg --files` 并生成一个精简的文件树（默认限制 200 个文件）。对于中大型项目，这部分内容非常长，但它让 Agent 拥有了"上帝视角"，知道项目结构。

### 3. 工具定义 (Tool Definitions)

**占比**: ~40% (隐形消耗)
**来源**: `ToolRegistry` -> `Vercel AI SDK`

虽然工具定义通常作为 `tools` 参数传递（在 OpenAI/Anthropic API 中），但在某些模型或调试视图中，它们会被渲染为 System Prompt 的一部分。
OpenCode 内置了 25+ 个工具，每个工具都有详细的 Zod Schema 和描述。
特别是 `bash` 和 `edit` 工具，其参数描述非常详尽，占据了大量 token。

### 4. 自定义指令 (Custom Instructions)

**占比**: ~15%
**来源**: `AGENTS.md`, `CLAUDE.md`, `.opencode/rules.md`

OpenCode 会自动查找并读取项目中的特定文档：

- **AGENTS.md**: 项目特定的 Agent 行为指南
- **CLAUDE.md**: 用户个人的偏好设置
- **README.md**: (部分 Agent 会读取)

如果这些文件存在且内容较多，Prompt 长度会显著增加。

### 5. 状态提醒 (System Reminders)

**占比**: ~10%
**来源**: `src/session/prompt/plan.txt` 等

根据当前模式（如 Plan Mode），系统会插入特定的状态提醒：

```text
<system-reminder>
You are currently in PLAN MODE.
RESTRICTION: You are STRICTLY FORBIDDEN from editing any files...
</system-reminder>
```

## 长度分析总结

| 组件           | 估算大小 (字符) | 目的                      |
| -------------- | --------------- | ------------------------- |
| Base Persona   | ~1000           | 确立行为边界和风格        |
| File Tree      | ~2000+          | 提供项目全貌，减少盲目 ls |
| Tool Schemas   | ~2500+          | 确保工具调用的准确性      |
| Custom Context | ~1000+          | 适应项目特定规范          |
| **总计**       | **~6500+**      | **全上下文感知的代价**    |

## 优化策略

尽管 Prompt 很长，但这种"重上下文"策略是 Agent 能够**开箱即用**的关键。

OpenCode 采用了一些优化手段：

1. **文件树截断**: 限制文件数量，忽略 `.git` 等目录
2. **动态加载**: 只有当 Agent 切换到特定模式时，才加载相应的 Prompt（如 Plan Mode）
3. **Token 压缩**: 对超出上下文限制的历史消息进行摘要压缩 (`compaction` agent)

## 结论

6k+ 字符的 System Prompt 是**Feature** 而非 **Bug**。它换取的是 Agent 对项目环境的深度理解和工具使用的准确性。如果不提供这些上下文，Agent 就需要多轮对话（"ls", "read README", "try tool"）才能获得相同的信息，这反而会消耗更多的 token 和时间。
