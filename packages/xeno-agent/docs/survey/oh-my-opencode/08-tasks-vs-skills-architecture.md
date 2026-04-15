# Tasks vs Skills Architecture

## Executive Summary

**Tasks** and **Skills** serve complementary purposes in oh-my-opencode:

| Aspect | **Task** | **Skill** |
|--------|----------|-----------|
| **Purpose** | Executable unit of work (background agent session) | Reusable instruction template/expertise module |
| **Nature** | Runtime entity with lifecycle | Static content loaded from files/config |
| **Storage** | In-memory Map (ephemeral) | File system (`.md` files) + config |
| **Lifecycle** | pending → running → completed/error/cancelled | Static (loaded on demand, cached) |
| **Relationship** | Tasks **consume** skills as system content | Skills **equip** tasks with expertise |

## 1. Task Architecture

### 1.1 Data Structures

**File**: `src/features/background-agent/types.ts`

```typescript
// Task states - runtime lifecycle management
export type BackgroundTaskStatus =
  | "pending"
  | "running"
  | "completed"
  | "error"
  | "cancelled"

// Task progress tracking
export interface TaskProgress {
  toolCalls: number
  lastTool?: string
  lastUpdate: Date
  lastMessage?: string
  lastMessageAt?: Date
}

// Core task entity - tracks an entire background agent session
export interface BackgroundTask {
  id: string                      // Unique task identifier
  sessionID?: string              // OpenCode session ID (set when running)
  parentSessionID: string         // Parent that spawned this task
  parentMessageID: string         // Parent message context
  description: string              // Short task description
  prompt: string                  // Full prompt sent to agent
  agent: string                   // Agent name executing this task
  status: BackgroundTaskStatus    // Current lifecycle state
  queuedAt?: Date                // When queued
  startedAt?: Date               // When execution began
  completedAt?: Date             // When finished
  result?: string                 // Output result
  error?: string                 // Error message if failed
  progress?: TaskProgress         // Execution progress tracking
  parentModel?: { providerID: string; modelID: string }
  model?: { providerID: string; modelID: string; variant?: string }
  concurrencyKey?: string        // For per-provider limiting
  concurrencyGroup?: string        // Persistent key for resume
  parentAgent?: string           // Parent session's agent
  lastMsgCount?: number          // For stability detection
  stablePolls?: number           // Consecutive polls with no change
}

// Input for launching a new task
export interface LaunchInput {
  description: string
  prompt: string
  agent: string
  parentSessionID: string
  parentMessageID: string
  parentModel?: { providerID: string; modelID: string }
  parentAgent?: string
  model?: { providerID: string; modelID: string; variant?: string }
  skills?: string[]              // ⭐ KEY: Skills are injected here
  skillContent?: string           // Pre-resolved skill content
}
```

### 1.2 Task Lifecycle

**File**: `src/features/background-agent/manager.ts` (1336 lines)

Tasks follow a **runtime lifecycle** with active polling and state management:

```
┌─────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
│ pending │ -> │ running │ -> │completed │    │  error   │
└─────────┘    └─────────┘    └──────────┘    └──────────┘
    ^              |                ^               |
    |              |                |               |
    |           polling             |            timeout
    |           (2s interval)      |          (30 min)
    |              v                |               v
    └─────────────┴────────────────┴───────────────┘
                notify parent,
                release slot,
                cleanup (5 min)
```

#### Phase 1: Launch

```typescript
async launch(input: LaunchInput): Promise<BackgroundTask> {
  const task: BackgroundTask = {
    id: `bg_${crypto.randomUUID().slice(0, 8)}`,
    status: "pending",              // Start as pending
    queuedAt: new Date(),
    description: input.description,
    prompt: input.prompt,
    agent: input.agent,
    parentSessionID: input.parentSessionID,
    parentMessageID: input.parentMessageID,
    model: input.model,
    // ⭐ Note: skillContent is injected into system prompt
  }
  this.tasks.set(task.id, task)

  // Add to concurrency queue
  const key = this.getConcurrencyKeyFromInput(input)
  const queue = this.queuesByKey.get(key) ?? []
  queue.push({ task, input })
  this.queuesByKey.set(key, queue)

  // Trigger processing (async, non-blocking)
  this.processKey(key)

  return task  // ⭐ Returns immediately with pending status
}
```

#### Phase 2: Process & Start

```typescript
private async processKey(key: string): Promise<void> {
  await this.concurrencyManager.acquire(key)
  await this.startTask(item)
}

private async startTask(item: QueueItem): Promise<void> {
  // Create OpenCode session
  const createResult = await this.client.session.create({
    body: {
      parentID: input.parentSessionID,
      title: `Background: ${input.description}`,
    },
    query: { directory: parentDirectory },
  })
  const sessionID = createResult.data.id

  // Update to running state
  task.status = "running"
  task.startedAt = new Date()
  task.sessionID = sessionID
  task.progress = { toolCalls: 0, lastUpdate: new Date() }

  // ⭐ KEY: Launch agent with skill content as system prompt
  this.client.session.prompt({
    path: { id: sessionID },
    body: {
      agent: input.agent,
      ...(input.model ? { model: input.model } : {}),
      system: input.skillContent,  // ← Skills injected here!
      tools: {
        ...getAgentToolRestrictions(input.agent),
        task: false,
        delegate_task: false,
        call_omo_agent: true,
      },
      parts: [{ type: "text", text: input.prompt }],
    },
  })

  this.startPolling()  // Begin 2-second polling interval
}
```

#### Phase 3: Poll

```typescript
private startPolling(): void {
  this.pollingInterval = setInterval(() => {
    this.pollRunningTasks()
  }, 2000)
}

private async pollRunningTasks(): Promise<void> {
  // Check session status, message count, tool calls
  // Detect stability: 3 consecutive polls with no message change = complete
  const sessionStatus = allStatuses[sessionID]
  if (sessionStatus?.type === "idle") {
    await this.tryCompleteTask(task, "polling (idle status)")
  }
}
```

#### Phase 4: Complete

```typescript
private async tryCompleteTask(task: BackgroundTask, source: string): Promise<boolean> {
  task.status = "completed"
  task.completedAt = new Date()

  if (task.concurrencyKey) {
    this.concurrencyManager.release(task.concurrencyKey)
    task.concurrencyKey = undefined
  }

  await this.notifyParentSession(task)

  // Cleanup after 5 minutes
  setTimeout(() => this.tasks.delete(task.id), 5 * 60 * 1000)

  return true
}
```

### 1.3 Storage & Cleanup

Tasks are **stored in-memory** (ephemeral):

```typescript
export class BackgroundManager {
  private tasks: Map<string, BackgroundTask>         // Active + recently completed
  private notifications: Map<string, BackgroundTask[]>  // Pending notifications
  private pendingByParent: Map<string, Set<string>>   // Parent-child tracking
  private queuesByKey: Map<string, QueueItem[]>        // Concurrency queues

  // Cleanup: Delete tasks after 5 minutes of completion
  private pruneStaleTasksAndNotifications(): void {
    const now = Date.now()
    const TASK_TTL_MS = 30 * 60 * 1000  // 30 minutes TTL

    for (const [taskId, task] of this.tasks.entries()) {
      const age = now - (task.startedAt?.getTime() ?? 0)
      if (age > TASK_TTL_MS) {
        task.status = "error"
        task.error = "Task timed out after 30 minutes"
        this.tasks.delete(taskId)
      }
    }
  }
}
```

**Key Points**:
- No persistent storage
- Tasks live only while the plugin is loaded
- 5-minute cleanup after completion
- 30-minute timeout for stale tasks

### 1.4 Concurrency Management

**File**: `src/features/background-agent/concurrency.ts`

Each provider/model has its own concurrency limit:

```typescript
interface ConcurrencyLimits {
  anthropic: number
  openai: number
  google: number
  xai: number
}

// Default limits
const DEFAULT_LIMITS: ConcurrencyLimits = {
  anthropic: 3,
  openai: 3,
  google: 5,
  xai: 5,
}
```

Tasks are queued per concurrency key (provider/model combination):
- Acquire slot before starting
- Release slot on completion/timeout
- Resume operations use persistent `concurrencyGroup`

## 2. Skill Architecture

### 2.1 Data Structures

**File**: `src/features/opencode-skill-loader/types.ts`

```typescript
// Where skills can be loaded from (priority order)
export type SkillScope =
  | "builtin"      // Hardcoded in plugin (playwright, git-master)
  | "config"       // From oh-my-opencode.json config
  | "user"         // ~/.claude/skills/
  | "project"      // .claude/skills/
  | "opencode"     // ~/.config/opencode/skills/
  | "opencode-project" // .opencode/skills/

// Metadata from skill file frontmatter (YAML)
export interface SkillMetadata {
  name?: string
  description?: string
  model?: string
  "argument-hint"?: string
  agent?: string
  subtask?: boolean
  license?: string
  compatibility?: string
  metadata?: Record<string, string>
  "allowed-tools"?: string
  mcp?: SkillMcpConfig            // MCP servers this skill requires
}

// Lazy-loaded content (defer file reading until needed)
export interface LazyContentLoader {
  loaded: boolean
  content?: string
  load: () => Promise<string>
}

// Fully loaded skill ready for use
export interface LoadedSkill {
  name: string
  path?: string                    // Original file path
  resolvedPath?: string            // Resolved actual path
  definition: CommandDefinition     // OpenCode-compatible definition
  scope: SkillScope                // Where this came from
  license?: string
  compatibility?: string
  metadata?: Record<string, string>
  allowedTools?: string[]          // Tools this agent can use
  mcpConfig?: SkillMcpConfig       // MCP servers to launch
  lazyContent?: LazyContentLoader   // Skill content template
}
```

**Built-in Skill Interface** (`src/features/builtin-skills/types.ts`):

```typescript
export interface BuiltinSkill {
  name: string
  description: string
  template: string                  // ⭐ KEY: The instruction content
  license?: string
  compatibility?: string
  metadata?: Record<string, unknown>
  allowedTools?: string[]
  agent?: string
  model?: string
  subtask?: boolean
  argumentHint?: string
  mcpConfig?: SkillMcpConfig
}
```

### 2.2 Skill Discovery

**File**: `src/features/opencode-skill-loader/loader.ts`

Skills are discovered from **6 sources** (priority order):

```
1. builtin (lowest priority)
   ↓
2. config (oh-my-opencode.json)
   ↓
3. user (~/.claude/skills/)
   ↓
4. opencode (~/.config/opencode/skills/)
   ↓
5. project (.claude/skills/)
   ↓
6. opencode-project (.opencode/skills/) [highest priority]
```

```typescript
// Discovery: Load skills from directories
async function loadSkillsFromDir(
  skillsDir: string,
  scope: SkillScope
): Promise<LoadedSkill[]> {
  const entries = await fs.readdir(skillsDir, { withFileTypes: true })
  const skills: LoadedSkill[] = []

  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue

    const entryPath = join(skillsDir, entry.name)

    // Load from directory with SKILL.md
    if (entry.isDirectory() || entry.isSymbolicLink()) {
      const resolvedPath = await resolveSymlinkAsync(entryPath)
      const skillMdPath = join(resolvedPath, "SKILL.md")
      const skill = await loadSkillFromPath(skillMdPath, resolvedPath, dirName, scope)
      if (skill) skills.push(skill)
    }
    // Load from single .md file
    if (isMarkdownFile(entry)) {
      const skillName = basename(entry.name, ".md")
      const skill = await loadSkillFromPath(entryPath, skillsDir, skillName, scope)
      if (skill) skills.push(skill)
    }
  }

  return skills
}
```

### 2.3 Skill Parsing

```typescript
// Parse skill from markdown file with YAML frontmatter
async function loadSkillFromPath(
  skillPath: string,
  resolvedPath: string,
  defaultName: string,
  scope: SkillScope
): Promise<LoadedSkill | null> {
  const content = await fs.readFile(skillPath, "utf-8")
  const { data, body } = parseFrontmatter<SkillMetadata>(content)
  const mcpJsonMcp = await loadMcpJsonFromDir(resolvedPath)

  // ⭐ KEY: Wrap skill body in template format
  const templateContent = `<skill-instruction>
Base directory for this skill: ${resolvedPath}/
File references (@path) in this skill are relative to this directory.

${body.trim()}
</skill-instruction>

<user-request>
$ARGUMENTS
</user-request>`

  const definition: CommandDefinition = {
    name: data.name || defaultName,
    description: `(${scope} - Skill) ${data.description || ""}`,
    template: templateContent,
    model: sanitizeModelField(data.model, isOpencodeSource ? "opencode" : "claude-code"),
    agent: data.agent,
    subtask: data.subtask,
  }

  return {
    name: definition.name,
    path: skillPath,
    resolvedPath,
    definition,
    scope,
    allowedTools: parseAllowedTools(data["allowed-tools"]),
    mcpConfig: mcpJsonMcp,
    lazyContent: { loaded: true, content: templateContent, load: async () => templateContent }
  }
}
```

### 2.4 Skill Merging

**File**: `src/features/opencode-skill-loader/merger.ts`

```typescript
// Priority: builtin(1) < config(2) < user(3) < opencode(4) < project(5) < opencode-project(6)
const SCOPE_PRIORITY: Record<SkillScope, number> = {
  builtin: 1,
  config: 2,
  user: 3,
  opencode: 4,
  project: 5,
  "opencode-project": 6,
}

export function mergeSkills(
  builtinSkills: BuiltinSkill[],
  config: SkillsConfig | undefined,
  userClaudeSkills: LoadedSkill[],
  userOpencodeSkills: LoadedSkill[],
  projectClaudeSkills: LoadedSkill[],
  projectOpencodeSkills: LoadedSkill[],
  options: MergeSkillsOptions = {}
): LoadedSkill[] {
  const skillMap = new Map<string, LoadedSkill>()

  // 1. Load all builtins first
  for (const builtin of builtinSkills) {
    const loaded = builtinToLoaded(builtin)
    skillMap.set(loaded.name, loaded)
  }

  // 2. Override with config entries
  for (const [name, entry] of Object.entries(normalizedConfig.entries)) {
    const loaded = configEntryToLoaded(name, entry, options.configDir)
    if (loaded) {
      const existing = skillMap.get(name)
      if (existing && !entry.template && !entry.from) {
        skillMap.set(name, mergeSkillDefinitions(existing, entry))
      } else {
        skillMap.set(name, loaded)  // Higher priority
      }
    }
  }

  // 3. Override with filesystem skills (user > project)
  const fileSystemSkills = [
    ...userClaudeSkills,
    ...userOpencodeSkills,
    ...projectClaudeSkills,
    ...projectOpencodeSkills,
  ]

  for (const skill of fileSystemSkills) {
    const existing = skillMap.get(skill.name)
    if (!existing || SCOPE_PRIORITY[skill.scope] > SCOPE_PRIORITY[existing.scope]) {
      skillMap.set(name, skill)  // Higher priority wins
    }
  }

  return Array.from(skillMap.values())
}
```

### 2.5 Skill File Format

```markdown
<!-- File: ~/.config/opencode/skills/my-skill.md -->

---
name: my-skill
description: Does something specific
agent: oracle
model: openai/gpt-5.2
allowed-tools: lsp_goto_definition lsp_references
mcp:
  playwright:
    command: npx
    args: ["@playwright/mcp@latest"]
---

# My Custom Skill

Detailed instructions here.

File references use @path relative to skill directory.

<user-request>
$ARGUMENTS
</user-request>
```

### 2.6 Skill Storage

Skills are **stored in files** (persistent):

```
~/.claude/skills/                    # User skills (Claude Code compat)
├── my-custom-skill/
│   └── SKILL.md                    # Skill directory format
├── another-skill.md                 # Single file format

~/.config/opencode/skills/            # OpenCode user skills
.opencode/skills/                    # Project-specific skills
.claude/skills/                      # Claude Code project skills

# Built-in skills (hardcoded in code)
src/features/builtin-skills/skills.ts
  ├── playwrightSkill
  ├── frontendUiUxSkill
  └── gitMasterSkill
```

### 2.7 Config-based Skills

`oh-my-opencode.json`:

```json
{
  "skills": {
    "my-skill": {
      "description": "Config-defined skill",
      "template": "Inline template here",
      "from": "./path/to/skill.md",
      "agent": "oracle"
    }
  }
}
```

## 3. Task-Skill Integration

### 3.1 How Tasks Use Skills

The key relationship: **Tasks consume skills as system content**

**File**: `src/tools/delegate-task/tools.ts`

```typescript
export function createDelegateTask(options: DelegateTaskToolOptions): ToolDefinition {
  return tool({
    description: `Spawn agent task with category-based or direct agent selection.

    - load_skills: ALWAYS REQUIRED. Pass skill names to inject as system prompt.
    Available skills: playwright, frontend-ui-ux, git-master, ...

    Example:
      delegate_task(
        category="visual-engineering",
        load_skills=["frontend-ui-ux", "playwright"],
        prompt="Build a beautiful landing page",
        run_in_background=false
      )`,

    args: {
      load_skills: tool.schema.array(tool.schema.string())
        .describe("Skill names to inject. REQUIRED"),
      description: tool.schema.string(),
      prompt: tool.schema.string(),
      category: tool.schema.string().optional(),
      subagent_type: tool.schema.string().optional(),
      run_in_background: tool.schema.boolean(),
    },

    async execute(args: DelegateTaskArgs, toolContext) {
      // ⭐ STEP 1: Resolve skills to content
      let skillContent: string | undefined
      if (args.load_skills.length > 0) {
        const { resolved, notFound } = await resolveMultipleSkillsAsync(
          args.load_skills,
          { gitMasterConfig }
        )
        if (notFound.length > 0) {
          return `Skills not found: ${notFound.join(", ")}`
        }
        // Combine multiple skills with double newline separator
        skillContent = Array.from(resolved.values()).join("\n\n")
      }

      // ⭐ STEP 2: Launch task with skill content
      const task = await manager.launch({
        description: args.description,
        prompt: args.prompt,
        agent: "Sisyphus-Junior",  // or from category config
        parentSessionID: ctx.sessionID,
        parentMessageID: ctx.messageID,
        model: modelInfo,
        skillContent,  // ← Injected as system prompt!
        skills: args.load_skills,  // For tracking/toast display
      })

      return `Task launched.
ID: ${task.id}
Session: ${task.sessionID}
Status: ${task.status}`
    },
  })
}
```

### 3.2 Flow Diagram

```
Agent calls:
delegate_task(load_skills=["git-master", "frontend-ui-ux"], ...)
         ↓
    Resolve skill names → content
         ↓
  manager.launch(skillContent: "...")
         ↓
  session.prompt(system: skillContent)
         ↓
Agent executes the prompt with skill instructions as context
```

### 3.3 Example: Multiple Skills in Task

```typescript
// Agent calls:
delegate_task({
  load_skills: ["git-master", "frontend-ui-ux"],
  category: "visual-engineering",
  prompt: "Refactor the landing page component",
  run_in_background: false
})

// Internally:
const { resolved, notFound } = await resolveMultipleSkillsAsync(
  ["git-master", "frontend-ui-ux"],
  { gitMasterConfig }
)

const skillContent = Array.from(resolved.values()).join("\n\n")
// skillContent now contains:
// "## Skill: git-master\n\n[GIT MASTER INSTRUCTIONS...]\n\n## Skill: frontend-ui-ux\n\n[UI/UX INSTRUCTIONS...]"

const task = await manager.launch({
  description: "Refactor landing page",
  prompt: "Refactor the landing page component",
  agent: "Sisyphus-Junior",
  parentSessionID: "session-123",
  parentMessageID: "msg-456",
  skillContent,  // Injected as system prompt!
  skills: ["git-master", "frontend-ui-ux"]
})

// In startTask():
await client.session.prompt({
  path: { id: sessionID },
  body: {
    agent: "Sisyphus-Junior",
    system: skillContent,  // ← Agent receives both skill instructions as system prompt
    parts: [{ type: "text", text: "Refactor the landing page component" }],
  },
})
```

## 4. Variables in Skills

### 4.1 Standard Variable: `$ARGUMENTS`

This is the most commonly used variable placeholder in skill templates.

```typescript
// In loader.ts, all skill templates are wrapped in:
const templateContent = `<skill-instruction>
Base directory for this skill: ${resolvedPath}/
File references (@path) in this skill are relative to this directory.

${body.trim()}      // ← Skill's specific instructions
</skill-instruction>

<user-request>
$ARGUMENTS          // ← Variable placeholder
</user-request>`
```

### 4.2 Variable Replacement

```typescript
// Skill file content:
# My Skill
Do X with @config/file.ts

<user-request>
$ARGUMENTS
</user-request>

// When called:
delegate_task({
  load_skills: ["my-skill"],
  prompt: "Build a login form with email validation",  // ← Replaces $ARGUMENTS
  ...
})

// Agent actually receives:
<skill-instruction>
Base directory for this skill: /path/to/skill/
File references (@path) in this skill are relative to this directory.

# My Skill
Do X with @config/file.ts
</skill-instruction>

<user-request>
Build a login form with email validation    // ← Variable replaced with prompt
</user-request>
```

### 4.3 Supported Variables

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | User-provided prompt/arguments (standard variable) |
| `@path` | File path relative to skill directory (auto-resolved) |
| `${resolvedPath}` | Skill root directory path (resolved at load time) |

### 4.4 Built-in Skill Example

**File**: `src/features/builtin-skills/skills.ts`

```typescript
const playwrightSkill: BuiltinSkill = {
  name: "playwright",
  description: "MUST USE for any browser-related tasks. Browser automation via Playwright MCP",
  template: `# Playwright Browser Automation

This skill provides browser automation capabilities via the Playwright MCP server.

## When to Use
- Web scraping
- Visual verification
- Screenshot capture
- Form automation

## Usage
Use MCP tool: playwright_navigate, playwright_screenshot, etc.`,
  mcpConfig: {
    playwright: {
      command: "npx",
      args: ["@playwright/mcp@latest"],
    },
  },
}

const gitMasterSkill: BuiltinSkill = {
  name: "git-master",
  description: "MUST USE for ANY git operations. Atomic commits, rebase/squash, history search",
  template: `# Git Master Agent

You are a Git expert combining three specializations:
1. **Commit Architect**: Atomic commits, dependency ordering
2. **Rebase Surgeon**: History rewriting, conflict resolution
3. **History Archaeologist**: Finding when/where changes were introduced

## MODE DETECTION
- "commit" → COMMIT MODE
- "rebase" → REBASE MODE
- "find when" → HISTORY_SEARCH MODE

[... extensive git instructions ...]`,
}
```

## 5. Architectural Comparison

### 5.1 Summary Table

| Dimension | **Task** | **Skill** |
|-----------|----------|-----------|
| **Abstraction Level** | High: Represents a unit of work | Medium: Represents expertise/domain knowledge |
| **Primary Interface** | `BackgroundTask` | `LoadedSkill` |
| **Creation** | Runtime (`launch()`, `resume()`) | Build-time (file parsing, merging) |
| **State** | Mutable (status, progress, timestamps) | Immutable (loaded content) |
| **Persistence** | In-memory only | File system (`.md` files) |
| **Discovery** | N/A (created on demand) | Scanned from 6 directories |
| **Caching** | None (active in memory while running) | Cached after first load |
| **Relationship** | Tasks **use** skills (skills → system prompt) | Skills **equip** tasks (content → task) |
| **Concurrency** | Limited per provider/model | N/A (passive content) |
| **Lifecycle** | pending → running → completed | Load → Use → (no lifecycle) |
| **Key Files** | `manager.ts` (1336 lines) | `loader.ts`, `merger.ts`, `skills.ts` |
| **Tool Exposure** | `delegate_task`, `background_output`, `background_cancel` | `skill`, `skill_mcp`, `slashcommand` |

### 5.2 Key Design Principles

1. **Separation of Concerns**:
   - Skills = **Knowledge** (how to do something)
   - Tasks = **Execution** (when to do it)

2. **Composability**: Multiple skills can be combined in a single task

3. **Prioritization**: Higher-priority sources override lower-priority ones

4. **Lazy Loading**: Skills are loaded on-demand to reduce memory footprint

## 6. Conclusion

**Tasks** and **Skills** serve complementary purposes in the oh-my-opencode architecture:

1. **Tasks** are the **execution layer** - they represent units of work that run in background agent sessions. They have lifecycle state, are tracked in-memory, and execute prompts.

2. **Skills** are the **knowledge layer** - they are reusable instruction templates that encapsulate domain expertise. They're loaded from files, merged across sources, and injected into tasks as system prompts.

3. **The Bridge**: The `load_skills` parameter in `delegate_task` connects them - skills are resolved to content, passed to `manager.launch()`, and injected as the `system` prompt when the agent session is created.

This architecture enables:
- **Reusability**: Skills can be shared across tasks
- **Composition**: Multiple skills can be combined in a single task
- **Prioritization**: Higher-priority sources override lower-priority ones
- **Separation of Concerns**: Expertise (skills) is separate from execution (tasks)
