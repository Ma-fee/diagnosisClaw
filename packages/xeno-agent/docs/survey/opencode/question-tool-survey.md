# OpenCode Question Tool Survey

调研日期: 2026-03-11

## 1. 概述

`question` 是 OpenCode 内置的用户交互工具，允许 LLM 在执行任务过程中向用户提出结构化问题，获取用户偏好、澄清需求或请求决策。

---

## 2. 代码位置

### 2.1 核心定义文件

| 编号  | 文件路径                                   | 说明                            |
| ----- | ------------------------------------------ | ------------------------------- |
| 2.1.1 | `/packages/opencode/src/tool/question.ts`  | 工具主定义与执行逻辑            |
| 2.1.2 | `/packages/opencode/src/tool/question.txt` | 工具描述（LLM Prompt）          |
| 2.1.3 | `/packages/opencode/src/question/index.ts` | Question 命名空间与 Schema 定义 |
| 2.1.4 | `/packages/opencode/src/tool/tool.ts`      | 基础工具框架定义                |

### 2.2 注册与配置

| 编号  | 文件路径                                  | 说明                                                |
| ----- | ----------------------------------------- | --------------------------------------------------- |
| 2.2.1 | `/packages/opencode/src/tool/registry.ts` | 工具注册表，条件启用 question 工具                  |
| 2.2.2 | `/packages/opencode/src/agent/agent.ts`   | Agent 权限配置（默认 deny，build/plan agent allow） |

### 2.3 Agent Prompt 引用

| 编号  | 文件路径                                            | 说明                              |
| ----- | --------------------------------------------------- | --------------------------------- |
| 2.3.1 | `/packages/opencode/src/session/prompt/trinity.txt` | trinity agent prompt 中的使用说明 |
| 2.3.2 | `/packages/opencode/src/session/prompt.ts`          | 系统 prompt 中的 phase 指令       |

### 2.4 API 与文档

| 编号  | 文件路径                                   | 说明                        |
| ----- | ------------------------------------------ | --------------------------- |
| 2.4.1 | `/packages/sdk/openapi.json`               | OpenAPI ToolListItem schema |
| 2.4.2 | `/packages/web/src/content/docs/tools.mdx` | 工具文档                    |

---

## 3. Schema 定义

### 3.1 Zod Schema（内部定义）

位置: `/packages/opencode/src/question/index.ts` (第 11-32 行)

```typescript
// 3.1.1 Option Schema - 单个选项
export const Option = z.object({
  label: z.string().describe("Display text (1-5 words, concise)"),
  description: z.string().describe("Explanation of choice"),
});

// 3.1.2 Info Schema - 单个问题
export const Info = z.object({
  question: z.string().describe("Complete question"),
  header: z.string().describe("Very short label (max 30 chars)"),
  options: z.array(Option).describe("Available choices"),
  multiple: z.boolean().optional().describe("Allow selecting multiple choices"),
  custom: z
    .boolean()
    .optional()
    .describe("Allow typing a custom answer (default: true)"),
});

// 3.1.3 Answer Schema - 答案格式
export const Answer = z.array(z.string());

// 3.1.4 Reply Schema - 多个问题的答案
export const Reply = z.object({
  answers: z
    .array(Answer)
    .describe(
      "User answers in order of questions (each answer is an array of selected labels)",
    ),
});
```

### 3.2 工具参数 Schema

位置: `/packages/opencode/src/tool/question.ts` (第 8-10 行)

```typescript
parameters: z.object({
  questions: z
    .array(Question.Info.omit({ custom: true }))
    .describe("Questions to ask"),
});
```

注意: `custom` 字段被移除，不会暴露给 LLM。

### 3.3 JSON Schema（LLM 看到的格式）

通过 `zod-to-json-schema` 转换后，LLM 看到的格式：

```json
{
  "id": "question",
  "description": "Use this tool when you need to ask the user questions...",
  "parameters": {
    "type": "object",
    "properties": {
      "questions": {
        "type": "array",
        "description": "Questions to ask",
        "items": {
          "type": "object",
          "properties": {
            "question": {
              "type": "string",
              "description": "Complete question"
            },
            "header": {
              "type": "string",
              "description": "Very short label (max 30 chars)"
            },
            "options": {
              "type": "array",
              "description": "Available choices",
              "items": {
                "type": "object",
                "properties": {
                  "label": {
                    "type": "string",
                    "description": "Display text (1-5 words, concise)"
                  },
                  "description": {
                    "type": "string",
                    "description": "Explanation of choice"
                  }
                },
                "required": ["label", "description"]
              }
            },
            "multiple": {
              "type": "boolean",
              "description": "Allow selecting multiple choices"
            }
          },
          "required": ["question", "header", "options"]
        }
      }
    },
    "required": ["questions"]
  }
}
```

---

## 4. 工具描述（LLM Prompt）

位置: `/packages/opencode/src/tool/question.txt`

```
Use this tool when you need to ask the user questions during execution. This allows you to:
1. Gather user preferences or requirements
2. Clarify ambiguous instructions
3. Get decisions on implementation choices as you work
4. Offer choices to the user about what direction to take.

Usage notes:
- When `custom` is enabled (default), a "Type your own answer" option is added automatically; don't include "Other" or catch-all options
- Answers are returned as arrays of labels; set `multiple: true` to allow selecting more than one
- If you recommend a specific option, make that the first option in the list and add "(Recommended)" at the end of the label
```

---

## 5. Agent Prompt 中的使用说明

### 5.1 trinity.txt 中的说明

位置: `/packages/opencode/src/session/prompt/trinity.txt` (第 85 行)

```
- When the user's request is vague, use the question tool to clarify before reading files or making changes.
```

### 5.2 prompt.ts 中的 Phase 指令

位置: `/packages/opencode/src/session/prompt.ts`

#### 5.2.1 Phase 1 指令（第 1403 行）

```typescript
"3. After exploring the code, use the question tool to clarify ambiguities in the user request up front.";
```

#### 5.2.2 Phase 3 指令（第 1436, 1449 行）

```typescript
"3. Use question tool to clarify any remaining questions with the user";

"**Important:** Use question tool to clarify requirements/approach, use plan_exit to request plan approval. Do NOT use question tool to ask \"Is this plan okay?\" - that's what plan_exit does.";
```

---

## 6. 执行逻辑

位置: `/packages/opencode/src/tool/question.ts`

### 6.1 执行流程

```typescript
async execute(params, ctx) {
  // 6.1.1 向用户展示问题并等待回答
  const answers = await Question.ask({
    sessionID: ctx.sessionID,
    questions: params.questions,
    tool: ctx.callID ? { messageID: ctx.messageID, callID: ctx.callID } : undefined,
  })

  // 6.1.2 格式化单个答案
  function format(answer: Question.Answer | undefined) {
    if (!answer?.length) return "Unanswered"
    return answer.join(", ")
  }

  // 6.1.3 格式化所有问题和答案
  const formatted = params.questions
    .map((q, i) => `"${q.question}"="${format(answers[i])}"`)
    .join(", ")

  // 6.1.4 返回结果
  return {
    title: `Asked ${params.questions.length} question${params.questions.length > 1 ? "s" : ""}`,
    output: `User has answered your questions: ${formatted}. You can now continue with the user's answers in mind.`,
    metadata: { answers },
  }
}
```

### 6.2 多个问题的处理

- **顺序对应**: `answers[i]` 对应 `params.questions[i]`
- **多选支持**: 每个答案是一个字符串数组，用 `", "` 连接
- **空答案**: 显示为 `"Unanswered"`

---

## 7. 工具注册与权限

### 7.1 注册逻辑

位置: `/packages/opencode/src/tool/registry.ts`

```typescript
const question =
  ["app", "cli", "desktop"].includes(Flag.OPENCODE_CLIENT) ||
  Flag.OPENCODE_ENABLE_QUESTION_TOOL;

return [
  InvalidTool,
  ...(question ? [QuestionTool] : []),
  BashTool,
  // ...
];
```

默认对 `app`, `cli`, `desktop` 客户端启用，其他客户端可通过 `OPENCODE_ENABLE_QUESTION_TOOL` 标志启用。

### 7.2 Agent 权限配置

位置: `/packages/opencode/src/agent/agent.ts`

| Agent 类型     | question 权限 | 行号 |
| -------------- | ------------- | ---- |
| 默认 (default) | deny          | 63   |
| build          | allow         | 84   |
| plan           | allow         | 99   |

---

## 8. 核心数据结构

### 8.1 Question.Info（问题信息）

| 字段     | 类型     | 必需 | 说明                            |
| -------- | -------- | ---- | ------------------------------- |
| question | string   | 是   | 完整的问题文本                  |
| header   | string   | 是   | 简短标签（最多30字符）          |
| options  | Option[] | 是   | 可选答案列表                    |
| multiple | boolean  | 否   | 是否允许多选                    |
| custom   | boolean  | 否   | 是否允许自定义答案（默认 true） |

### 8.2 Question.Option（选项）

| 字段        | 类型   | 必需 | 说明                |
| ----------- | ------ | ---- | ------------------- |
| label       | string | 是   | 显示文本（1-5个词） |
| description | string | 是   | 选项说明            |

### 8.3 Question.Answer（答案）

```typescript
z.array(z.string()); // 选中的选项 label 数组
```

---

## 9. 使用示例

### 9.1 TypeScript 调用示例

```typescript
import { question } from "@/tool/question";

// 9.1.1 单问题示例
await question({
  questions: [
    {
      question: "What language do you prefer?",
      header: "Language",
      options: [
        { label: "TypeScript", description: "JavaScript with types" },
        { label: "Python", description: "Easy to learn" },
      ],
    },
  ],
});

// 9.1.2 多问题 + 多选示例
await question({
  questions: [
    {
      question: "Which features do you need?",
      header: "Features",
      multiple: true,
      options: [
        { label: "Auth", description: "User authentication" },
        { label: "Database", description: "Data persistence" },
        { label: "Cache", description: "Performance optimization" },
      ],
    },
  ],
});
```

### 9.2 LLM 输出示例

当用户选择后，LLM 收到的输出：

```
User has answered your questions: "What language do you prefer?"="TypeScript", "Which features do you need?"="Auth, Database". You can now continue with the user's answers in mind.
```

---

## 10. 关键说明

### 10.1 自动添加 "Type your own answer"

- `custom` 默认为 `true`
- 当 `custom` 启用时，前端会自动添加 "Type your own answer" 选项
- 不需要在 `options` 中包含 "Other" 或兜底选项

### 10.2 推荐选项标记

- 如果要推荐某个选项，将其放在第一位
- 在 label 末尾添加 `"(Recommended)"` 标记

### 10.3 与 plan_exit 的区别

- **question**: 用于澄清需求、获取偏好、请求决策
- **plan_exit**: 用于请求计划批准
- **不要**用 question 问 "Is this plan okay?"

---

## 11. 参考链接

- 调研来源: OpenCode 仓库 `/Users/yuchen.liu/src/opencode`
- 主要代码文件:
  - `/packages/opencode/src/tool/question.ts`
  - `/packages/opencode/src/question/index.ts`
  - `/packages/opencode/src/tool/tool.ts`
  - `/packages/opencode/src/tool/registry.ts`
  - `/packages/opencode/src/agent/agent.ts`
