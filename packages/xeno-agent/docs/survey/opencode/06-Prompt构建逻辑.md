# Prompt 构建逻辑

## 核心理念

OpenCode 的 Prompt 构建不是静态的字符串拼接，而是一个动态的、上下文感知的过程。它综合了环境变量、Agent 配置、工具定义、用户输入和系统状态。

**文件位置**: `src/session/prompt.ts`

## Prompt 层次结构

一个完整的 Prompt 由以下几层组成（按注入顺序）：

1. **Base System Prompt**: 基础系统设定
2. **Environment Context**: 环境信息（时间、平台、CWD）
3. **Agent Specific Prompt**: Agent 专属设定
4. **Tool Definitions**: 工具 Schema (由 AI SDK 自动处理)
5. **System Reminders**: 动态系统提醒
6. **Message History**: 历史对话

## 1. 基础系统 Prompt

系统首先加载基础 Prompt，定义了 AI 的角色和基本行为准则。

```typescript
// 伪代码
const basePrompt = `
You are OpenCode, a powerful AI coding assistant...
Current directory: ${cwd}
Operating System: ${os}
Date: ${date}
`;
```

## 2. 动态变量替换

OpenCode 支持在 Prompt 模板中使用变量：

- `{{cwd}}`: 当前工作目录
- `{{os}}`: 操作系统
- `{{date}}`: 当前日期
- `{{user}}`: 用户名

这些变量在 `SessionPrompt.resolvePromptParts` 中被解析和替换。

## 3. Agent 专属设定

每个 Agent 可以定义自己的 `prompt` 属性。这个 Prompt 会被追加到系统 Prompt 中。

```typescript
// explore agent
const PROMPT_EXPLORE = `
Your goal is to explore the codebase and provide insights.
- Do NOT modify any code.
- Use grep and glob to find patterns.
- Summarize your findings clearly.
`;
```

## 4. 工具注入 (Tool Injection)

OpenCode **不**手动将工具定义拼接进 Prompt 字符串。

相反，它利用 **Vercel AI SDK** 的 `tools` 参数。

- 将 `Tool.parameters` (Zod Schema) 转换为 JSON Schema
- 通过协议（OpenAI Function Calling 或 Anthropic Tools）传递给 LLM

这确保了工具调用的准确性和类型安全。

## 5. System Reminders (动态提醒)

这是 OpenCode 最独特的设计之一。系统会根据当前状态，在消息流中动态插入 `<system-reminder>` 标签。

**场景 1: Plan Mode 切换**
当用户要求进入 Plan 模式时：

```xml
<system-reminder>
You are now in PLAN MODE.
1. You have READ-ONLY access (except for .opencode/plans/).
2. Follow the 5-phase planning process.
3. Do not implement code yet.
</system-reminder>
```

**场景 2: 上下文溢出**
当上下文接近上限时：

```xml
<system-reminder>
Context limit reached. Please summarize your progress and compact the session.
</system-reminder>
```

**场景 3: 工具错误**
当工具连续失败时：

```xml
<system-reminder>
Tool execution failed 3 times. Please verify parameters or try a different approach.
</system-reminder>
```

这些提醒作为 `system` 角色的消息插入到对话历史的末尾，具有极高的权重。

## 6. Prompt Mixing (混合逻辑)

最终的 Prompt 组装逻辑：

```typescript
async function buildMessages(session, input) {
  const messages = [];

  // 1. System Message
  messages.push({
    role: "system",
    content: basePrompt + agentPrompt + envContext,
  });

  // 2. History
  messages.push(...session.messages);

  // 3. Dynamic Reminders
  const reminders = getReminders(session);
  if (reminders.length > 0) {
    messages.push({
      role: "system",
      content: reminders.join("\n"),
    });
  }

  return messages;
}
```

## 最佳实践总结

1. **分层构建**: 将通用逻辑和 Agent 专有逻辑分离
2. **动态注入**: 根据上下文（如 cwd, os）动态填充信息
3. **原生工具支持**: 利用 LLM 的原生 Tool Calling 能力，而不是 Prompt 工程
4. **即时反馈**: 使用 System Reminder 进行实时纠偏

这种构建逻辑使得 OpenCode 能够灵活适应不同的任务场景，同时保持高度的稳定性和可控性。
