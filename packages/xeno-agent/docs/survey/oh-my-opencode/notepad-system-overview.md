# Oh-My-OpenCode Notepad 系统深度调研

## 概述

Notepad 系统是 Oh-My-OpenCode 中解决 **子 Agent 无状态(Stateless)**问题的关键机制。由于每次 `task()` 调用都创建全新的、没有上下文的子 Agent，Notepad 提供了一个**文件系统级别的外部记忆(External Memory)** 来在多次委托之间传递知识和经验。

---

## 核心问题：子 Agent 的无状态性

### 问题描述

```typescript
// 每次 task() 调用都是全新的 Agent
const result1 = await task({ prompt: "分析代码" }); // Agent A
const result2 = await task({ prompt: "实现功能" }); // Agent B - 完全不知道 Agent A 的发现
```

**问题：**
- Agent B 不知道 Agent A 发现了什么模式
- Agent B 不知道之前的约定是什么
- 同样的坑会踩多次
- 项目特有的模式无法传承

### 解决方案：Notepad 外部记忆系统

```
.sisyphus/notepads/{plan-name}/
├── learnings.md    # 约定、模式、最佳实践
├── decisions.md    # 架构决策
├── issues.md       # 遇到的问题、坑
└── problems.md     # 未解决的技术债务
```

---

## 机制分工：Prompt vs Hook

### Prompt 驱动的部分（大模型负责）

#### 1. Atlas/Prometheus 在 Prompt 中的要求

**读取 Notepad（委托前）：**

````markdown
## 3.2 Before Each Delegation

**MANDATORY: Read notepad first**
```bash
glob(".sisyphus/notepads/{plan-name}/*.md")
Read(".sisyphus/notepads/{plan-name}/learnings.md")
Read(".sisyphus/notepads/{plan-name}/issues.md")
```

Extract wisdom and include in prompt:
```markdown
[From notepad - conventions, gotchas, decisions]
- Convention: [pattern discovered]
- Warning: [issue to avoid]
- Decision: [architectural choice]
```
````

**要求子 Agent 记录 Finding：**

```markdown
## 4. MUST DO
- Follow pattern in [reference file:lines]
- Write tests for [specific cases]
- **Append findings to notepad (never overwrite)**

## 5. MUST NOT DO
- Do NOT use Edit tool on notepad files (use Write with append mode)
- Do NOT overwrite notepad files
```

#### 2. Sisyphus-Junior 接收的 Prompt 指令

**通过 Hook 注入的系统提示：**

```typescript
// constants.ts - 注入给子 Agent 的指令
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
`
```

#### 3. 子 Agent 期望的 Finding 格式

```markdown
# Task: [task-id] - [brief description]

## Patterns Discovered
- [Pattern]: [description and file location]
- [Convention]: [how things are done in this codebase]

## Gotchas / Issues
- [Issue]: [what went wrong and how to avoid]
- [Warning]: [something to watch out for]

## Decisions Made
- [Decision]: [why this approach was chosen]

## References
- File: [path:lines] - [what it demonstrates]
```

### Hook 驱动的部分（系统强制执行）

#### 1. Sisyphus-Junior-Notepad Hook

```typescript
// hook.ts
export function createSisyphusJuniorNotepadHook(_ctx: PluginInput) {
  return {
    "tool.execute.before": async (input, output) => {
      // 1. 只有 task 工具才注入
      if (input.tool !== "task") return;
      
      // 2. 只有 Atlas 调用的 task 才注入
      if (!isCallerOrchestrator(input.sessionID)) return;
      
      // 3. 避免重复注入
      if (prompt.includes(SYSTEM_DIRECTIVE_PREFIX)) return;
      
      // 4. 在 prompt 前注入 Notepad 指令
      output.args.prompt = NOTEPAD_DIRECTIVE + prompt;
    }
  };
}
```

**关键逻辑：**
- 自动识别 Atlas 委托的子任务
- 在子 Agent 的 prompt 前注入 notepad 使用指令
- 确保每个子 Agent 都知道如何记录 finding

#### 2. Atlas Hook 的验证提醒

```typescript
// verification-reminders.ts
export const VERIFICATION_REMINDER = `
...
**STEP 2: MANUAL CODE REVIEW (NON-NEGOTIABLE)**

The subagent was instructed to record findings in notepad files. Read them NOW:
1. Glob(".sisyphus/notepads/${planName}/*.md")
2. Read the notepad files:
   - **learnings.md**: Patterns, conventions, successful approaches discovered
   - **issues.md**: Problems, blockers, gotchas encountered during work
...
`;
```

---

## Notepad 文件结构详解

### 1. learnings.md - 约定与模式

**用途：** 记录代码库中的约定、成功模式、最佳实践

**示例内容：**
```markdown
# Learnings: auth-refactor

## [2025-02-15 10:30] Task 1: analyze-auth-flow

### Codebase Conventions
- All middleware files use kebab-case: `auth-middleware.ts`
- JWT secrets stored in `process.env.JWT_SECRET`, never hardcoded
- Controllers follow pattern: `export async function handlerName(req, res)`

### Gotchas
- `bcrypt.compare()` is async, always use `await`
- Default session timeout is 24 hours in this project
- Error handling uses `next(new AppError(...))` consistently

## [2025-02-15 11:15] Task 2: implement-login

### Pattern Match
- Auth middleware should be placed BEFORE route handlers in Express
- Use httpOnly cookies for refresh tokens
```

### 2. decisions.md - 架构决策

**用途：** 记录重要的架构选择及其理由

**示例内容：**
```markdown
# Decisions: auth-refactor

## [2025-02-15 10:45] Authentication Strategy

**Decision:** Use JWT access tokens + httpOnly refresh tokens

**Rationale:**
- Stateless authentication for scalability
- XSS protection via httpOnly cookies
- No server-side session storage needed

**Alternatives Considered:**
- Session-based: Rejected due to scalability concerns
- Pure JWT: Rejected due to no revocation capability

## [2025-02-15 11:30] Password Hashing

**Decision:** Use bcrypt with cost factor 12

**Rationale:**
- Industry standard
- Sufficient security/performance balance
```

### 3. issues.md - 遇到的问题

**用途：** 记录遇到的坑、 blocker、警告

**示例内容：**
```markdown
# Issues: auth-refactor

## [2025-02-15 10:35] Database Connection

**Issue:** Connection pool exhaustion during tests

**Symptom:** Tests hang after ~50 test cases

**Root Cause:** Connections not released in `afterAll` hook

**Solution:** Always call `await db.destroy()` in test teardown

## [2025-02-15 11:20] TypeScript Types

**Warning:** `@types/bcrypt` version mismatch

**Issue:** Type errors with latest bcrypt

**Workaround:** Use `// @ts-ignore` or downgrade to known working version
```

### 4. problems.md - 未解决问题

**用途：** 记录技术债务、待决策问题

**示例内容：**
```markdown
# Problems: auth-refactor

## [2025-02-15 11:45] Rate Limiting

**Status:** Not implemented

**Why:** Out of current scope

**Impact:** Potential brute force vulnerability

**Next Steps:** Create follow-up task for rate limiting middleware
```

---

## 完整工作流程示例

### 场景：实现用户认证系统

**Step 1: Atlas 初始化 Notepad**

```typescript
// Atlas 执行
Bash("mkdir -p .sisyphus/notepads/auth-refactor")
```

**Step 2: Atlas 委托第一个任务**

```typescript
// 读取现有 notepad（空）
Read(".sisyphus/notepads/auth-refactor/learnings.md")

// 委托任务
task(
  category="deep",
  load_skills=[],
  prompt=`
## 1. TASK
Analyze current auth implementation in src/auth/

## 4. MUST DO
- Read all auth-related files
- Identify patterns and conventions
- **APPEND findings to .sisyphus/notepads/auth-refactor/learnings.md**

## 6. CONTEXT
Notepad: .sisyphus/notepads/auth-refactor/learnings.md
`
)
```

**Step 3: 子 Agent 记录 Finding**

```typescript
// 子 Agent 分析完成后的动作
Write(".sisyphus/notepads/auth-refactor/learnings.md", `
## [2025-02-15 10:30] Task: analyze-auth-implementation

### Conventions Found
- Auth middleware files use kebab-case naming
- JWT secret from process.env.JWT_SECRET
- Error handling uses next(new AppError(...))

### Gotchas
- bcrypt.compare() is async, needs await
- Session timeout is 24 hours by default
`)
```

**Step 4: Atlas 读取 Finding 并传递给下一个子 Agent**

```typescript
// Atlas 读取更新后的 notepad
const learnings = Read(".sisyphus/notepads/auth-refactor/learnings.md")

// 委托第二个任务，传入之前的发现
task(
  category="quick",
  load_skills=[],
  prompt=`
## 1. TASK
Implement login endpoint

## 6. CONTEXT
### Inherited Wisdom (from notepad)
${learnings}

Based on previous analysis:
- Use kebab-case for middleware filenames  
- JWT secret from process.env.JWT_SECRET
- Error handling uses next(new AppError(...))
- Remember: bcrypt.compare() needs await!
`
)
```

---

## 关键设计原则

### 1. 永远追加，从不覆盖

```markdown
❌ 错误：使用 Edit 或 Write 覆盖
Write(".sisyphus/notepads/x/learnings.md", "new content")  // 旧内容丢失！

✅ 正确：追加模式
Write(".sisyphus/notepads/x/learnings.md", "\\n## New Task\\n...")  // 保留历史
```

### 2. 结构化记录

每个 Finding 应该包含：
- **时间戳**：方便追溯
- **任务来源**：哪个任务产生的
- **分类**：约定、问题、决策
- **上下文**：相关文件路径

### 3. Atlas 负责读取，子 Agent 负责写入

| 角色 | 职责 | 文件操作 |
|------|------|----------|
| Atlas (Orchestrator) | 委托前读取 notepad，整合到 prompt | Read |
| Sisyphus-Junior (Worker) | 执行任务，记录 finding | Append |

### 4. Hook 自动注入指令

不需要手动在每个 task() 中添加 notepad 指令，Hook 会自动注入：

```typescript
// 不需要这样写
task(prompt=`Notepad: .sisyphus/notepads/x/\n${taskPrompt}`)

// 直接写任务
// Hook 会自动注入 notepad 指令
task(prompt=taskPrompt)  // 自动获得 NOTEPAD_DIRECTIVE 前缀
```

---

## 实现你自己的 Notepad 系统

### 核心代码模板

#### 1. Hook 注入系统

```typescript
// notepad-injector.ts
const NOTEPAD_DIRECTIVE = `
<Work_Context>
## Notepad System
Location: .notepads/{task-id}/
Files:
- learnings.md: Record patterns and conventions
- issues.md: Record problems encountered

You SHOULD append findings after completing work.
Always APPEND - never overwrite.
</Work_Context>
`;

export function createNotepadInjectorHook() {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "task") return;
      
      // 识别 orchestrator 发起的任务
      if (!isFromOrchestrator(input.sessionID)) return;
      
      // 注入指令
      output.args.prompt = NOTEPAD_DIRECTIVE + output.args.prompt;
    }
  };
}
```

#### 2. Atlas Prompt 模板

````markdown
## Notepad Protocol

Before delegation:
1. Read .notepads/{plan-name}/*.md
2. Extract key findings
3. Include in subagent prompt

After subagent completes:
1. Read updated notepad files
2. Verify findings were recorded
3. Use findings to inform next delegation

## Subagent Prompt Template

When delegating:
```
## 1. TASK
[specific task]

## 4. MUST DO
- [implementation requirements]
- **APPEND findings to .notepads/{plan-name}/learnings.md**

## 6. CONTEXT  
### Previous Findings
[from notepad]
- Convention: [pattern]
- Warning: [issue]
```
````

#### 3. Finding 记录格式

```typescript
// finding-format.ts
export function formatFinding(
  taskId: string,
  category: "pattern" | "issue" | "decision",
  content: string,
  context?: { file?: string; line?: number }
): string {
  const timestamp = new Date().toISOString();
  return `

## [${timestamp}] Task: ${taskId}

### ${category.toUpperCase()}
${content}

${context ? `**Context**: ${context.file}:${context.line}` : ''}
`;
}

// 使用示例
const finding = formatFinding(
  "auth-impl",
  "pattern",
  "Controllers use async/await pattern with try-catch",
  { file: "src/auth/controller.ts", line: 42 }
);

// finding 内容
// ## [2025-02-15T10:30:00Z] Task: auth-impl
// 
// ### PATTERN
// Controllers use async/await pattern with try-catch
//
// **Context**: src/auth/controller.ts:42
```

---

## 对比：传统的 Context Passing

| 方式 | 优点 | 缺点 |
|------|------|------|
| **Prompt Context Passing** | 直接、即时 | 上下文窗口限制，信息丢失 |
| **File-Based Notepad** | 持久化、结构化、可复查 | 需要读写文件 |
| **Vector DB** | 语义检索、支持大量知识 | 复杂度高、延迟 |

**Notepad 的优势：**
- **人类可读**：工程师可以直接查看 `.sisyphus/notepads/`
- **版本控制**：可以被 git 追踪
- **调试友好**：排查问题时可以看到 Agent 的"思考过程"
- **增量积累**：每个任务贡献一点，逐步构建知识体系

---

## 总结

Oh-My-OpenCode 的 Notepad 系统是一个优雅的**外部记忆**解决方案：

1. **Hook 负责注入**：`sisyphus-junior-notepad` hook 自动在子 Agent 的 prompt 前注入 notepad 使用指令

2. **Prompt 负责指导**：Atlas/Prometheus 的 system prompt 要求委托前读取 notepad，委托后写入 finding

3. **大模型负责执行**：子 Agent 根据 prompt 指令读取历史 finding、记录新的 finding

4. **文件系统负责持久化**：`.sisyphus/notepads/{plan-name}/*.md` 作为知识载体

这个机制的核心洞见：**利用文件系统作为 Agent 间的共享内存(Shared Memory)，通过 Prompt 约定读写协议，Hook 确保协议被遵循。**

---

*调研时间：2025年2月*
*来源：Oh-My-OpenCode v3.x 源码分析*
