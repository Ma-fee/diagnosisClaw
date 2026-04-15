# Oh-My-OpenCode: Prompt vs Hook 分工详解

本文档详细列出 Notepad 系统中**哪些行为由 Prompt（大模型）负责**，**哪些由 Hook（系统代码）强制执行**。

---

## 总览

| 行为 | 负责方 | 机制 | 强制性 |
|------|--------|------|--------|
| 定义 Notepad 文件结构 | Prompt | Atlas 系统 prompt 中定义 | 约定 |
| 委托前读取 Notepad | Prompt | Atlas prompt 要求 | Soft |
| 委托后检查 Notepad | Prompt | Atlas verification 要求 | Soft |
| 注入 Notepad 使用指令 | Hook | `sisyphus-junior-notepad` hook | Hard |
| 追加 Finding（不覆盖） | Prompt | Worker prompt 中的 MUST DO | Soft |
| 禁止修改 Plan 文件 | Hook | `NOTEPAD_DIRECTIVE` 中的规则 | Hard |

---

## Prompt 驱动的部分

### 1. Atlas System Prompt 中的 Notepad 约定

**位置：** `src/agents/atlas/default.ts` 和 `src/agents/atlas/gpt.ts`

```markdown
## 2. DIRECTORIES

### Working Memory (Notepad - VERY IMPORTANT)
Bash("mkdir -p .sisyphus/notepads/{plan-name}")
- Notepad: `.sisyphus/notepads/{name}/` (READ/APPEND)

Structure:
.sisyphus/notepads/{plan-name}/
  - learnings.md    # Conventions, patterns
  - decisions.md    # Architectural choices
  - issues.md       # Problems, gotchas
  - problems.md     # Unresolved issues
```

**作用：** 定义 Notepad 的文件结构和用途
**执行方：** Atlas（大模型）需要理解和遵循这些约定

---

### 2. 委托前读取 Notepad（Atlas 的职责）

**位置：** `src/agents/atlas/default.ts` Lines 161-165

````markdown
## 3.2 Before Each Delegation

**MANDATORY: Read notepad first**
```
glob(".sisyphus/notepads/{plan-name}/*.md")
Read(".sisyphus/notepads/{plan-name}/learnings.md")
Read(".sisyphus/notepads/{plan-name}/issues.md")
```

Extract wisdom and include in prompt:
```
[From notepad - conventions, gotchas, decisions]
- Convention: [pattern discovered]
- Warning: [issue to avoid]
- Decision: [architectural choice]
```
````

**作用：** 确保每个子 Agent 都获得历史上下文

**执行方：** Atlas（大模型）需要在委托前主动执行这些读取操作

---

### 3. 要求子 Agent 记录 Finding

**位置：** `src/agents/atlas/default.ts` Line 80

```markdown
## 4. MUST DO
- Follow pattern in [reference file:lines]
- Write tests for [specific cases]
- **Append findings to notepad (never overwrite)**
```

**作用：** 将记录 finding 作为任务完成的要求

**执行方：** Atlas 在构造 task prompt 时包含此要求

---

### 4. 要求阅读 Notepad 文件（Atlas 的验证步骤）

**位置：** `src/hooks/atlas/verification-reminders.ts` Lines 31-37

```markdown
The subagent was instructed to record findings in notepad files. Read them NOW:
1. Glob(".sisyphus/notepads/${planName}/*.md")
2. Read the notepad files:
   - **learnings.md**: Patterns, conventions, successful approaches discovered
   - **issues.md**: Problems, blockers, gotchas encountered during work
```

**作用：** 验证子 Agent 确实记录了 finding

**触发：** Hook 检测到子 Agent 完成时自动注入此提醒

---

### 5. Worker Agent 的 Finding 记录

**由谁来执行？** 子 Agent（大模型）

**期望行为（由 Prompt 指导，但模型自主决定如何描述）：**

```typescript
// 理想情况下，Worker Agent 应该这样写
Write(".sisyphus/notepads/auth-refactor/learnings.md", `
## [2025-02-15 10:30] Task: analyze-auth-flow

### Patterns Discovered
- Controllers use async/await pattern with try-catch
  (src/auth/controller.ts:42)
- Error handling uses next(new AppError(...))
  (src/middleware/error.ts:15)

### Conventions
- Middleware filenames use kebab-case (auth-middleware.ts)
- JWT secrets always from process.env (never hardcoded)

### Gotchas
- bcrypt.compare() is async - needs await!
- Session timeout defaults to 24 hours
`);
```

**自由度：** 大模型决定记录哪些内容、如何组织语言

---

## Hook 驱动的部分

### 1. 自动注入 Notepad 指令

**位置：** `src/hooks/sisyphus-junior-notepad/hook.ts`

```typescript
export function createSisyphusJuniorNotepadHook(_ctx: PluginInput) {
  return {
    "tool.execute.before": async (input, output) => {
      // 1. 检查如果不是 task 工具，不处理
      if (input.tool !== "task") {
        return;
      }

      // 2. 检查如果不是 Orchestrator 调用的，不处理
      if (!isCallerOrchestrator(input.sessionID)) {
        return;
      }

      // 3. 避免重复注入
      const prompt = output.args.prompt as string | undefined;
      if (prompt && prompt.includes(SYSTEM_DIRECTIVE_PREFIX)) {
        return;
      }

      // 4. 关键：自动注入 NOTEPAD_DIRECTIVE
      output.args.prompt = NOTEPAD_DIRECTIVE + prompt;
    },
  };
}
```

**作用：** 确保每个 Atlas 委托的子 Agent 都获得 Notepad 使用指令
**强制点：**
- 不需要 Atlas 手动在每个 task() 中添加 notepad 指令
- Hook 自动识别并增强 prompt

---

### 2. 注入的 NOTEPAD_DIRECTIVE 内容

**位置：** `src/hooks/sisyphus-junior-notepad/constants.ts`

```typescript
export const NOTEPAD_DIRECTIVE = `
<Work_Context>
## Notepad Location (for recording learnings)
NOTEPAD PATH: .sisyphus/notepads/{plan-name}/
- learnings.md: Record patterns, conventions, successful approaches
- issues.md: Record problems, blockers, gotchas encountered
- decisions.md: Record architectural choices and rationales
- problems.md: Record unresolved issues, technical debt

You SHOULD append findings to notepad files after completing work.
IMPORTANT: Always APPEND to notepad files - never overwrite or use Edit tool.

## Plan Location (READ ONLY)
PLAN PATH: .sisyphus/plans/{plan-name}.md

CRITICAL RULE: NEVER MODIFY THE PLAN FILE
...
</Work_Context>
`;
```

**关键指令：**
- "You SHOULD append findings to notepad files"
- "Always APPEND - never overwrite"
- "NEVER MODIFY THE PLAN FILE"（强制执行只读）

---

### 3. 工作流程中的 Hook 触发点

```
用户请求
    ↓
Atlas（Orchestrator）
    ↓ 调用 task()
Hook: sisyphus-junior-notepad
    ↓ 修改 args.prompt
Sisyphus-Junior（Worker）
    ↓ 读取增强后的 prompt
执行 + 记录 finding
    ↓
返回结果给 Atlas
    ↓
Hook: atlas（verification）
    ↓ 注入验证提醒
Atlas 读取 notepad 验证
    ↓
下一个任务
```

---

## 典型场景的分工示例

### 场景：Atlas 委托任务给子 Agent

#### Step 1: Atlas 构造 Prompt（Prompt 负责）

```typescript
// Atlas 主动在 prompt 中包含 notepad 信息
task(
  category="quick",
  prompt=`
## TASK
Implement login endpoint

## MUST DO
- Implement email/password validation
- Generate JWT token
- **Append findings to .sisyphus/notepads/auth-refactor/learnings.md**

## CONTEXT
### From Notepad (previous tasks)
- Convention: Controllers use async/await (src/auth/controller.ts:42)
- Warning: bcrypt.compare() needs await

Notepad: .sisyphus/notepads/auth-refactor/learnings.md
`
);
```

**Atlas 的责任：**
- ✅ 在委托前读取 notepad
- ✅ 在 prompt 中引用 notepad 内容
- ✅ 明确要求记录 finding

---

#### Step 2: Hook 自动增强 Prompt（Hook 负责）

```typescript
// Hook 自动在 prompt 前添加 NOTEPAD_DIRECTIVE
// 最终传给子 Agent 的 prompt：

`<Work_Context>
## Notepad Location
NOTEPAD PATH: .sisyphus/notepads/auth-refactor/
...
Always APPEND - never overwrite...
</Work_Context>

## TASK
Implement login endpoint

## MUST DO
...
`
```

**Hook 的责任：**
- ✅ 自动注入 notepad 使用规则
- ✅ 确保指令格式统一
- ✅ 无需 Atlas 重复书写

---

#### Step 3: 子 Agent 记录 Finding（Prompt + 模型自主）

```typescript
// Worker Agent 决定记录的内容和格式
// 这是模型自主行为，没有强制模式

Write(".sisyphus/notepads/auth-refactor/learnings.md", `
## [2025-02-15 14:30] Task: implement-login

### Implementation Pattern
- Used try-catch for error handling
- Token expires in 1 hour (configurable via env)

### Issues Encountered
- Need to handle "email not found" vs "wrong password" differently
- Rate limiting should be added (#security)

### Decisions
- Chose to return 401 for both auth failures (security through obscurity)
`);
```

**模型的自由度：**
- ✅ 决定记录什么内容
- ✅ 决定如何组织
- ✅ 决定详细程度
- ❌ 但受约束：必须追加，不能覆盖

---

#### Step 4: Atlas 验证（Prompt 负责）

```typescript
// Hook 在子 Agent 完成后注入提醒

`**MANDATORY: WHAT YOU MUST DO RIGHT NOW**

The subagent was instructed to record findings in notepad files. Read them NOW:
1. Glob(".sisyphus/notepads/auth-refactor/*.md")
2. Read the notepad files:
   - learnings.md: Patterns, conventions...
   - issues.md: Problems, blockers...

// Atlas 然后执行读取
Read(".sisyphus/notepads/auth-refactor/learnings.md");
// 验证内容是否符合预期
```

**Atlas 的责任：**
- ✅ 检查 finding 是否已记录
- ✅ 使用 finding 指导后续任务

---

## 边界情况处理

### 情况 1: 子 Agent 没有记录 Finding

**检测方式：** Hook 注入的 verification reminder

**Atlas 的应对：**
```typescript
// 在 prompt 中发现没有 finding
if (!learningsContent.includes(" patterns discovered")) {
  // 可以要求子 Agent 补充
  task(prompt=`Please document the patterns you discovered in the notepad`);
}
```

**责任方：** Prompt（Atlas 指导模型自我修正）

---

### 情况 2: 子 Agent 覆盖了 Notepad

**检测难度：** 高（需要比较前后内容）

**防范措施：**
- Prompt 中强调 "never overwrite or use Edit tool"
- 期望模型理解并遵循

**如果真的发生：** Prompt 只能教育，Hook 无法拦截

**改进想法：** 可以添加一个 Hook 拦截 write/edit 操作，检查目标是否是 notepad 文件，如果是则要求追加而非覆盖。

---

### 情况 3: 子 Agent 修改了 Plan 文件

**检测：** Hook 的 `NOTEPAD_DIRECTIVE` 明确禁止

```markdown
CRITICAL RULE: NEVER MODIFY THE PLAN FILE

The plan file (.sisyphus/plans/*.md) is SACRED and READ-ONLY.
- You may READ the plan to understand tasks
- You MUST NOT edit, modify, or update the plan file
- Only the Orchestrator manages the plan file

VIOLATION = IMMEDIATE FAILURE.
```

**后果：** 如果违反，Atlas 可能检测到计划文件被修改（unexpected changes）

---

## 实施建议

### 如果你想在自己的项目中实现类似系统：

#### 1. 必须实现 Hook（Hard Constraint）

```typescript
// 创建 task-injector hook
export function createTaskInjectorHook() {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "task") return;
      
      const enhancedPrompt = `
<External_Memory>
Use .notepads/{task-id}/ to record findings.
Always APPEND, never overwrite.
</External_Memory>

${output.args.prompt}`;
      
      output.args.prompt = enhancedPrompt;
    }
  };
}
```

#### 2. 必须在 Orchestrator Prompt 中约定（Soft Constraint）

```markdown
## Notepad Protocol

Before task:
1. Read .notepads/{plan}/*.md
2. Include findings in context

After task:
1. Read updated notepads
2. Verify findings recorded
3. Use for next task planning
```

#### 3. 权衡：需要更强的强制执行吗？

**当前局限：**
- 模型可能忘记记录 finding → Prompt 提醒
- 模型可能覆盖 notepad → 难以检测

**可能的增强：**
- Hook 拦截所有文件操作
- 检测到 notepad 路径时强制转换为追加模式
- 但这会增加复杂性

---

## 总结：分工矩阵

| 行为 | 机制 | 可靠性 | 建议 |
|------|------|--------|------|
| 定义 notepad 结构 | Prompt | ★★☆☆☆ | 使用示例+文档描述 |
| 委托前读取 | Prompt | ★★★☆☆ | MUST DO 明确指示 |
| 注入使用指令 | Hook | ★★★★☆ | 自动确保一致性 |
| APPEND 不覆盖 | Prompt | ★★★☆☆ | 强调重要性 |
| 禁止修改 Plan | Hook+Prompt | ★★★★☆ | Directive 中明确指出 |

**核心洞见：** Oh-My-OpenCode 使用 **Prompt 负责高级认知工作（决定记录什么）**，**Hook 负责机械性增强（注入使用规则）**，两者协同但保持关注点分离。
