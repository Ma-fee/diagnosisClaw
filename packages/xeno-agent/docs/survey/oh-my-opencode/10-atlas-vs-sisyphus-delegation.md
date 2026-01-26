# Atlas vs Sisyphus: Delegation Task Differences

## Executive Summary

**Atlas** and **Sisyphus** receive **different output formats** when calling `delegate_task` due to **intentional design** controlled by the Atlas hook. Atlas gets rich visibility into subtask execution details (file changes, progress tracking, verification reminders), while Sisyphus receives standard raw output.

This is controlled by:
1. **Atlas Hook**: `src/hooks/atlas/index.ts` - only applies when Atlas is the caller
2. **`isCallerOrchestrator()` check**: Filters to only transform output for Atlas
3. **No equivalent hook for Sisyphus**: Sisyphus gets standard output

## 1. The Mechanism: Atlas Hook

### 1.1 Location

**File**: `src/hooks/atlas/index.ts` (lines 683-771)

### 1.2 Key Function: `tool.execute.after` Handler

```typescript
"tool.execute.after": async (input: ToolExecuteAfterInput, output: ToolExecuteAfterOutput): Promise<void> => {
  // CRITICAL CHECK: Only transform if Atlas is calling
  if (!isCallerOrchestrator(input.sessionID)) {
    return  // ← Early return for ALL non-Atlas agents (including Sisyphus)
  }

  if (input.tool !== "delegate_task") {
    return
  }

  // Transform output with rich details
  const ctx = getHookContext()
  const gitStats = getGitDiffStats(ctx.directory)
  const fileChanges = formatFileChanges(gitStats)
  const originalResponse = output.output

  // Transform to rich format
  output.output = `
## SUBAGENT WORK COMPLETED

${fileChanges}

---

**Subagent Response:**

${originalResponse}

<system-reminder>
${buildOrchestratorReminder(...)}
</system-reminder>`
}
```

### 1.3 Caller Detection: `isCallerOrchestrator()`

**Lines 397-403**

```typescript
function isCallerOrchestrator(sessionID?: string): boolean {
  if (!sessionID) return false
  const messageDir = getMessageDir(sessionID)
  if (!messageDir) return false
  const nearest = findNearestMessageWithFields(messageDir)
  return nearest?.agent === "Atlas"  // ← ONLY Atlas gets transformed output
}
```

This function is the **key to the difference**:
- Returns `true` if Atlas is calling
- Returns `false` if Sisyphus (or any other agent) is calling
- Controls whether output transformation happens

### 1.4 `tool.execute.after` Flow

```
Any agent calls delegate_task()
         ↓
tool.execute.after hook fires
         ↓
isCallerOrchestrator(sessionID) called
         ↓
    ┌─────────────┴─────────────┐
    ↓                           ↓
True (Atlas)              False (Sisyphus, others)
    ↓                           ↓
Transform output        Return early (no transformation)
    ↓                           ↓
Rich details added    Standard raw output
    ↓                           ↓
Atlas sees file changes,  Sisyphus sees basic output
progress, reminders
```

## 2. Standard delegate_task Output

**File**: `src/tools/delegate-task/tools.ts` (lines 1022-1032)

When no transformation is applied (Sisyphus case), this is the standard output:

```typescript
const response = `
Task completed in ${duration}.

Agent: ${agentToUse}${args.category ? ` (category: ${args.category})` : ""}
Session ID: ${sessionID}

---

${textContent || "(No text output)"}

---
To resume this session: resume="${sessionID}"
`
```

### 2.1 Standard Output Format

```
Task completed in 2m 15s.

Agent: Sisyphus-Junior (category: quick)
Session ID: ses_abc123

---

Subagent completed the task successfully. Created 3 files.

---
To resume this session: resume="ses_abc123"
```

## 3. Atlas-Enhanced Output

### 3.1 Full Format with File Changes

```typescript
output.output = `
## SUBAGENT WORK COMPLETED

${fileChanges}

---

**Subagent Response:**

${originalResponse}

<system-reminder>
${buildOrchestratorReminder(...)}
</system-reminder>`
```

### 3.2 File Changes Component

```typescript
function formatFileChanges(gitStats: GitDiffStats | null): string {
  if (!gitStats) return "[No file changes detected]"

  const lines = []

  // Modified files
  if (gitStats.modified.length > 0) {
    lines.push("Modified files:")
    for (const f of gitStats.modified) {
      lines.push(`  ${f.path}  (+${f.additions}, -${f.deletions})`)
    }
  }

  // Created files
  if (gitStats.created.length > 0) {
    lines.push("Created files:")
    for (const f of gitStats.created) {
      lines.push(`  ${f.path}  (+${f.additions})`)
    }
  }

  // Deleted files
  if (gitStats.deleted.length > 0) {
    lines.push("Deleted files:")
    for (const f of gitStats.deleted) {
      lines.push(`  ${f.path}`)
    }
  }

  return lines.length > 0 ? lines.join("\n") : "[No file changes detected]"
}
```

### 3.3 Full Atlas Output Example

```
## SUBAGENT WORK COMPLETED

Modified files:
  src/example.ts  (+12, -3)
  src/utils.ts  (+8, -15)

Created files:
  src/new-feature.ts  (+45)
  tests/new-feature.test.ts  (+32)

Deleted files:
  src/old-utils.ts

---

**Subagent Response:**

Task completed in 2m 15s.
Agent: Sisyphus-Junior (category: quick)
Session ID: ses_abc123

---

Subagent completed the task successfully. Created 3 files and modified 2 files.

---

<system-reminder>
**BOULDER STATE:** Plan: `my-feature` | 3/5 done | 2 remaining

Completed items:
- ✅ Set up project structure
- ✅ Implement core feature
- ✅ Add unit tests

Remaining items:
- ⏳ Add integration tests
- ⏳ Write documentation

---

**MANDATORY: WHAT YOU MUST DO RIGHT NOW**

**1. VERIFY - Subagent claims:** "Created 3 files and modified 2 files"

The git diff shows actual changes. Trust the diff, not the claim.

**2. Cross-check file contents:**
- src/new-feature.ts (45 lines added)
- tests/new-feature.test.ts (32 lines added)
- src/example.ts (+12, -3)
- src/utils.ts (+8, -15)
- src/old-utils.ts (deleted)

**3. LIE WARNING:** Subagents frequently claim to have done things they haven't actually done. Use the git diff output above to verify.

**4. Check for errors:**
- Run `bun test` to verify tests pass
- Run `bun run typecheck` to verify no type errors

**5. Update Boulder State if task completed a planned item**

**6. Update Todo List if applicable**

**To resume this subagent session:**
delegate_task(resume="ses_abc123", prompt="...")
</system-reminder>
```

## 4. Sisyphus Output Example

Sisyphus receives the **standard raw output** without transformation:

```
Task completed in 2m 15s.

Agent: Sisyphus-Junior (category: quick)
Session ID: ses_abc123

---

Subagent completed the task successfully. Created 3 files and modified 2 files.

---
To resume this session: resume="ses_abc123"
```

Note:
- No file changes summary
- No boulder state tracking
- No verification reminders
- No LIE warnings
- Just the basic completion message

## 5. Detailed Comparison

### 5.1 Feature Comparison Table

| Feature | Atlas Mode | Sisyphus Mode |
|---------|------------|---------------|
| **File Changes Summary** | ✅ Full diff (added/modified/deleted with line counts) | ❌ None |
| **Header** | ✅ "## SUBAGENT WORK COMPLETED" | ❌ None |
| **Subagent Response Section** | ✅ Preserved under "**Subagent Response:**" | ✅ Shown directly |
| **Verification Reminders** | ✅ Detailed QA checklist | ❌ None |
| **LIE Warnings** | ✅ "Subagents frequently lie" warnings | ❌ None |
| **Boulder Progress** | ✅ Shows "X/Y done | Z remaining" | ❌ None |
| **Todo List Updates** | ✅ Reminder to update todos | ❌ None |
| **Type Check/Test Commands** | ✅ Reminders to run | ❌ None |
| **Resume Reminder** | ✅ `delegate_task(resume="...")` | ✅ `resume="..."` |
| **Session Info** | ✅ Agent, Session ID, Duration, Category | ✅ Agent, Session ID, Duration, Category |
| **System Reminder Wrapper** | ✅ `<system-reminder>` tag | ❌ None |

### 5.2 Output Flow Comparison

#### Atlas Flow

```
Atlas calls delegate_task()
         ↓
tool.execute.after hook fires
         ↓
isCallerOrchestrator(sessionID) → true (Atlas)
         ↓
Get git diff stats
         ↓
Format file changes summary
         ↓
Build orchestrator reminder (boulder state, verification, LIE warnings)
         ↓
Wrap in "## SUBAGENT WORK COMPLETED"
         ↓
Atlas receives:
  - File changes
  - Progress tracking
  - Verification reminders
  - LIE warnings
  - Resume info
```

#### Sisyphus Flow

```
Sisyphus calls delegate_task()
         ↓
tool.execute.after hook fires
         ↓
isCallerOrchestrator(sessionID) → false (not Atlas)
         ↓
Early return (no transformation)
         ↓
Sisyphus receives:
  - Basic completion message
  - Session info
  - Resume info
```

## 6. Why This Design?

### 6.1 Atlas: Master Orchestrator

**File**: `src/agents/atlas.ts` (573 lines)

Atlas's purpose:
- **Coordinates work via formal plans** (boulder state)
- **Tracks progress across multiple subtasks**
- **Needs verification** because subagents can "frequently lie"
- **Manages complex multi-step workflows**

Therefore, Atlas needs:
- **File changes**: To track what subagents actually did vs what they claimed
- **Progress tracking**: Boulder state shows completion status
- **Verification reminders**: Because subagents may misrepresent their work
- **LIE warnings**: Explicit warnings that subagents can be deceptive
- **QA checklist**: Systematic verification steps

### 6.2 Sisyphus: Primary Orchestrator

**File**: `src/agents/sisyphus.ts` (451 lines)

Sisyphus's purpose:
- **Can work directly or delegate**
- **More self-sufficient**
- **Less formal orchestration**
- **Designed for autonomous work**

Therefore, Sisyphus gets:
- **Standard output**: Cleaner interface
- **Less noise**: Can verify on its own if needed
- **Simpler format**: No need for formal plan tracking

### 6.3 Architectural Principle

```
Atlas = Orchestration Engine
├─ Needs visibility into subtasks
├─ Tracks progress formally
├─ Requires verification checks
└─ Gets rich output details

Sisyphus = Primary Worker/Orchestrator
├─ More autonomous
├─ Self-sufficient
├─ Simpler workflows
└─ Gets standard output
```

## 7. Code: IsCallerOrchestrator Implementation

### 7.1 Complete Function

**File**: `src/hooks/atlas/index.ts` (lines 397-403)

```typescript
function isCallerOrchestrator(sessionID?: string): boolean {
  if (!sessionID) return false
  const messageDir = getMessageDir(sessionID)
  if (!messageDir) return false
  const nearest = findNearestMessageWithFields(messageDir)
  return nearest?.agent === "Atlas"
}
```

### 7.2 Helper Functions

```typescript
// Get message directory path from session ID
function getMessageDir(sessionID: string): string | null {
  const sessionsDir = path.join(getSessionsDir(), sessionID)
  const messagesDir = path.join(sessionsDir, "messages")
  if (!fs.existsSync(messagesDir)) return null
  return messagesDir
}

// Find nearest message with agent field
function findNearestMessageWithFields(messageDir: string): MessageFields | null {
  const messages = readMessagesFromDir(messageDir)
  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i]
    if (msg.role === "assistant" && msg.agent) {
      return {
        agent: msg.agent,
        messageID: msg.id,
      }
    }
  }
  return null
}

interface MessageFields {
  agent: string
  messageID: string
}
```

## 8. Universal Hooks (Apply to Both)

Both Atlas and Sisyphus receive output from these universal hooks:

### 8.1 task-resume-info Hook

**File**: `src/hooks/task-resume-info/index.ts`

Adds resume info to **all** delegate_task outputs:

```typescript
"tool.execute.after": async (input: ToolExecuteAfterInput, output: ToolExecuteAfterOutput): Promise<void> => {
  if (input.tool !== "delegate_task") {
    return
  }

  // Extract session ID from response
  const sessionIDMatch = output.output.match(/Session ID: ([a-zA-Z0-9_-]+)/)
  const sessionID = sessionIDMatch?.[1]

  if (!sessionID) {
    return
  }

  // Append resume info
  output.output += "\n\n---\n\nTo resume this session: resume=\"" + sessionID + "\""
}
```

This hook applies to **both** Atlas and Sisyphus.

### 8.2 delegate-task-retry Hook

**File**: `src/hooks/delegate-task-retry/index.ts`

Adds error guidance on failed delegate_task calls:

```typescript
"tool.execute.after": async (input: ToolExecuteAfterInput, output: ToolExecuteAfterOutput): Promise<void> => {
  if (input.tool !== "delegate_task") {
    return
  }

  // Check if task failed
  if (output.error) {
    output.output += "\n\n**Task failed.** Consider using:\n"
    output.output += "- `delegate_task(resume=\"${sessionID}\", prompt=\"fix the error\")` to retry\n"
    output.output += "- Increase timeout or change category if applicable"
  }
}
```

## 9. Configuration

### 9.1 Disabling Atlas Hook

The Atlas hook can be disabled via configuration:

```typescript
// src/index.ts (line 286)
const atlasHook = isHookEnabled("atlas")
  ? createAtlasHook(ctx, { directory: ctx.directory, backgroundManager })
  : null;

if (atlasHook) {
  plugin.registerHook(...atlasHook)
}
```

**Configuration file**: `oh-my-opencode.json`

```json
{
  "hooks": {
    "atlas": false
  }
}
```

If disabled, Atlas would receive the **same output format as Sisyphus**.

### 9.2 Hook Configuration

```json
{
  "hooks": {
    "atlas": true,
    "auto-slash-command": true,
    "task-resume-info": true
  }
}
```

## 10. Making Sisyphus See Subtask Details

If you want Sisyphus to have similar output visibility as Atlas, you have two options:

### Option 1: Modify `isCallerOrchestrator()` to Include Sisyphus

```typescript
function isCallerOrchestrator(sessionID?: string): boolean {
  if (!sessionID) return false
  const messageDir = getMessageDir(sessionID)
  if (!messageDir) return false
  const nearest = findNearestMessageWithFields(messageDir)
  // Atlas OR Sisyphus get transformed output
  return nearest?.agent === "Atlas" || nearest?.agent === "Sisyphus"
}
```

### Option 2: Create a Separate Hook for Sisyphus

```typescript
// src/hooks/sisyphus-output/index.ts

export function createSisyphusOutputHook(): Hook {
  return {
    "tool.execute.after": async (input: ToolExecuteAfterInput, output: ToolExecuteAfterOutput): Promise<void> => {
      // Only transform if Sisyphus is calling
      if (!isCallerSisyphus(input.sessionID)) {
        return
      }

      if (input.tool !== "delegate_task") {
        return
      }

      // Similar transformation as Atlas, but potentially different
      const gitStats = getGitDiffStats(ctx.directory)
      const fileChanges = formatFileChanges(gitStats)
      const originalResponse = output.output

      output.output = `
## SUBAGENT WORK COMPLETED

${fileChanges}

---

**Subagent Response:**

${originalResponse}
`
    },
  }
}

function isCallerSisyphus(sessionID?: string): boolean {
  if (!sessionID) return false
  const messageDir = getMessageDir(sessionID)
  if (!messageDir) return false
  const nearest = findNearestMessageWithFields(messageDir)
  return nearest?.agent === "Sisyphus"
}
```

Then register it in `src/index.ts`:

```typescript
const sisyphusOutputHook = createSisyphusOutputHook()
plugin.registerHook(...sisyphusOutputHook)
```

## 11. Summary

### 11.1 Key Points

1. **Intentional Design**: Atlas and Sisyphus receiving different outputs is by design, not a bug

2. **Controlled by Atlas Hook**: The `tool.execute.after` handler in `src/hooks/atlas/index.ts` controls output transformation

3. **Caller Detection**: `isCallerOrchestrator()` filters to only transform output for Atlas

4. **Atlas Gets Rich Output**: File changes, progress tracking, verification reminders, LIE warnings

5. **Sisyphus Gets Standard Output**: Basic completion message, session info, resume info

6. **Why This Design**: Atlas is a master orchestrator that needs visibility; Sisyphus is more autonomous

7. **Universal Hooks**: Both agents receive output from `task-resume-info` and `delegate-task-retry` hooks

8. **Configuration**: Atlas hook can be disabled; if disabled, both get standard output

### 11.2 Output Difference Summary

| Aspect | Atlas | Sisyphus |
|---------|--------|-----------|
| **Visibility** | High (rich details) | Low (standard) |
| **File Changes** | Shown | Not shown |
| **Progress** | Tracked (boulder) | Not tracked |
| **Verification** | Required | Optional |
| **Complexity** | High (orchestration) | Low (autonomous) |
| **Output Format** | Rich, multi-section | Simple, single-section |

### 11.3 Decision Matrix

Use Atlas when you need:
- Formal plan tracking
- Progress visualization
- Verification of subagent work
- Multi-step workflow coordination

Use Sisyphus when you need:
- Autonomous work
- Simpler interface
- Less orchestration overhead
- Direct task execution

The different output formats reflect their different roles in the system.
