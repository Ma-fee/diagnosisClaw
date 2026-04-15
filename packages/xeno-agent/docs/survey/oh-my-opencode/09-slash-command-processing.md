# Slash Command Processing

## Executive Summary

**All skills** (both built-in and custom) are automatically exposed as slash commands in oh-my-opencode. Users can invoke any skill by typing `/skill-name` in the chat interface, which triggers a sophisticated parsing and template replacement pipeline.

## 1. Architecture Overview

### 1.1 Component Relationship

```
User Input: "/playwright test login form"
         ↓
┌─────────────────────────────────────────┐
│  auto-slash-command Hook               │  ← Intercepts chat.message
│  (chat.message event)                  │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Detector                              │  ← Parses slash syntax
│  /playwright test login form            │     Extracts: command="playwright"
│     ↓                                  │                args="test login form"
│  command + args                         │
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Executor                              │  ← Finds command/skill
│  findCommand("playwright")              │     Formats template
│  formatCommandTemplate()                │     Resolves refs
└─────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│  Message Replacement                   │  ← Replaces user input
│  <auto-slash-command>                 │     with formatted template
│    ...template content...               │
│  </auto-slash-command>                │
└─────────────────────────────────────────┘
         ↓
Agent receives skill template as context
```

### 1.2 File Structure

| File | Lines | Purpose |
|------|-------|---------|
| `src/tools/slashcommand/tools.ts` | 167 | Slash command tool implementation, skill mapping |
| `src/hooks/auto-slash-command/index.ts` | 150 | Hook that intercepts chat messages |
| `src/hooks/auto-slash-command/executor.ts` | 200+ | Executes slash commands, formats templates |
| `src/hooks/auto-slash-command/detector.ts` | 50+ | Parses slash command syntax |
| `src/index.ts` | 294 | Registers slashcommand tool and hook |

## 2. Slash Command Tool

**File**: `src/tools/slashcommand/tools.ts` (line 167)

### 2.1 Tool Definition

```typescript
export function createSlashcommandTool(options: SlashcommandToolOptions = {}): ToolDefinition {
  return tool({
    name: "slashcommand",
    description: "Load a slash command to get detailed instructions for a specific task.",
    args: {
      command: tool.schema.string()
    },
    async execute(args: SlashCommandArgs, context) {
      const { resolved, notFound } = await resolveCommandsAsync([args.command])

      if (notFound.length > 0) {
        return `Slash command not found: ${args.command}`
      }

      const command = resolved.get(args.command)
      return formatCommand(command)
    },
  })
}
```

### 2.2 Skill-to-Command Mapping

**Key Function**: `skillToCommandInfo` (lines 69-85)

```typescript
function skillToCommandInfo(skill: LoadedSkill): CommandInfo {
  return {
    name: skill.name,
    path: skill.path,
    metadata: {
      name: skill.name,
      description: skill.definition.description || "",
      argumentHint: skill.definition.argumentHint,
      model: skill.definition.model,
      agent: skill.definition.agent,
      subtask: skill.definition.subtask,
    },
    content: skill.definition.template,
    scope: skill.scope,
    lazyContentLoader: skill.lazyContent,
  }
}
```

### 2.3 Command Discovery

```typescript
const getAllItems = async (): Promise<CommandInfo[]> => {
  const commands = getCommands()              // Built-in commands
  const skills = await getSkills()           // From file system
  return [...commands, ...skills.map(skillToCommandInfo)]  // ⭐ Skills mapped here
}
```

## 3. Auto-Slash-Command Hook

**File**: `src/hooks/auto-slash-command/index.ts`

### 3.1 Hook Registration

```typescript
// src/index.ts (line 333)
plugin.registerHook("chat.message", async (ctx) => {
  const result = await processMessage(ctx)
  if (result.modified) {
    // Replace message with formatted template
    ctx.output.parts[idx].text = result.replacementText
  }
  return ctx
})
```

### 3.2 Processing Flow

```typescript
async function processMessage(ctx: HookContext): Promise<ProcessResult> {
  for (let i = 0; i < ctx.output.parts.length; i++) {
    const part = ctx.output.parts[i]
    if (part.type !== "text") continue

    const text = part.text

    // 1. Detect slash command
    const detection = detectSlashCommand(text)
    if (!detection) continue

    const { command, args, fullMatch } = detection

    // 2. Execute slash command
    const execution = await executeSlashCommand(command, args, ctx)
    if (!execution) continue

    const { replacementText } = execution

    // 3. Replace user message
    return {
      modified: true,
      replacementText,
    }
  }

  return { modified: false }
}
```

## 4. Detector

**File**: `src/hooks/auto-slash-command/detector.ts`

### 4.1 Pattern Matching

```typescript
const SLASH_COMMAND_PATTERN = /^\/([a-zA-Z][\w-]*)\s*(.*)/

export function detectSlashCommand(
  text: string
): { command: string; args: string; fullMatch: string } | null {
  const match = text.match(SLASH_COMMAND_PATTERN)
  if (!match) return null

  return {
    command: match[1],      // "playwright"
    args: match[2],        // "test login form"
    fullMatch: match[0],    // "/playwright test login form"
  }
}
```

### 4.2 Examples

| Input | Command | Args |
|-------|---------|------|
| `/playwright test login` | `playwright` | `test login` |
| `/git-master commit --fixup` | `git-master` | `commit --fixup` |
| `/build` | `build` | `""` (empty) |
| `/api-designer design user endpoint` | `api-designer` | `design user endpoint` |

## 5. Executor

**File**: `src/hooks/auto-slash-command/executor.ts`

### 5.1 Command Lookup

```typescript
async function findCommand(commandName: string, options?: ExecutorOptions): Promise<CommandInfo | null> {
  const allCommands = await discoverAllCommands(options)

  // Case-insensitive search
  return allCommands.find(
    (cmd) => cmd.name.toLowerCase() === commandName.toLowerCase()
  ) ?? null
}

async function discoverAllCommands(options?: ExecutorOptions): Promise<CommandInfo[]> {
  const commands = getCommands()
  const skills = await getSkills()
  return [...commands, ...skills.map(skillToCommandInfo)]
}
```

### 5.2 Template Formatting

```typescript
export async function executeSlashCommand(
  commandName: string,
  args: string,
  context: HookContext
): Promise<ExecutionResult | null> {
  const command = await findCommand(commandName)

  if (!command) {
    return null
  }

  // 1. Load content
  const content = command.lazyContentLoader
    ? await command.lazyContentLoader.load()
    : command.content

  // 2. Replace $ARGUMENTS with user input
  const formattedContent = replaceArguments(content, args)

  // 3. Format with metadata
  const formatted = `
<auto-slash-command>
## Slash Command: /${command.name}
## Description: ${command.metadata.description}
${command.metadata.model ? `## Model: ${command.metadata.model}` : ""}
${command.metadata.agent ? `## Agent: ${command.metadata.agent}` : ""}

${formattedContent}
</auto-slash-command>
`

  return {
    replacementText: formatted.trim(),
    command,
  }
}

function replaceArguments(template: string, args: string): string {
  return template.replace(/\$ARGUMENTS/g, args)
}
```

### 5.3 Output Format

```markdown
<auto-slash-command>
## Slash Command: /playwright
## Description: MUST USE for any browser-related tasks
## Model: anthropic/claude-opus-4-5

# Playwright Browser Automation

This skill provides browser automation capabilities...

## When to Use
- Web scraping
- Visual verification
- Screenshot capture

<user-request>
test login form
</user-request>
</auto-slash-command>
```

## 6. Skill Discovery for Slash Commands

**File**: `src/features/opencode-skill-loader/loader.ts`

### 6.1 Discovery Sources

Skills are discovered from **6 directories** (priority order):

| Directory | Scope | Example Path |
|-----------|-------|--------------|
| `.opencode/skills/` | opencode-project | `/project/.opencode/skills/my-skill/` |
| `.claude/skills/` | project | `/project/.claude/skills/api-designer.md` |
| `~/.config/opencode/skills/` | opencode | `~/.config/opencode/skills/` |
| `~/.claude/skills/` | user | `~/.claude/skills/` |

Plus **built-in skills** from `src/features/builtin-skills/skills.ts`.

### 6.2 Discovery Function

```typescript
export async function discoverAllSkills(): Promise<LoadedSkill[]> {
  const [opencodeProjectSkills, projectSkills, opencodeGlobalSkills, userSkills] = await Promise.all([
    discoverOpencodeProjectSkills(),
    discoverProjectClaudeSkills(),
    discoverOpencodeGlobalSkills(),
    discoverUserClaudeSkills(),
  ])
  return [...opencodeProjectSkills, ...projectSkills, ...opencodeGlobalSkills, ...userSkills]
}
```

### 6.3 File Loading

```typescript
// From directory: ~/.claude/skills/my-skill/
my-skill/
├── SKILL.md              # Skill definition
├── mcp.json              # Optional MCP config
└── examples/             # Optional examples

// From single file: ~/.claude/skills/quick-fix.md
quick-fix.md              # Skill definition in single file
```

## 7. Built-in Commands

除了 skills，还有一些内置的 slash commands：

**File**: `src/features/builtin-commands/commands.ts`

| Command | Description |
|---------|-------------|
| `/publish` | Publish oh-my-opencode to npm via GitHub Actions |
| `/commit` | Create git commit (requires git-master skill) |
| `/omomomo` | Easter egg - about oh-my-opencode |
| `/get-unpublished-changes` | Compare HEAD with latest npm version |

这些是 **内置命令**（built-in commands），不是 skills。它们与 skills 一样被映射到 slash command 系统。

## 8. Complete Flow Example

### 8.1 User Input

```
User types in chat: "/playwright test the login form on localhost:3000"
```

### 8.2 Step-by-Step Processing

#### Step 1: Hook Interception

```typescript
// auto-slash-command/index.ts
plugin.registerHook("chat.message", async (ctx) => {
  const text = ctx.output.parts[0].text  // "/playwright test the login form on localhost:3000"

  const result = await processMessage(ctx)
  // result = { modified: true, replacementText: "<auto-slash-command>..." }
})
```

#### Step 2: Detection

```typescript
// detector.ts
const detection = detectSlashCommand(text)

// Returns:
{
  command: "playwright",
  args: "test the login form on localhost:3000",
  fullMatch: "/playwright test the login form on localhost:3000"
}
```

#### Step 3: Command Lookup

```typescript
// executor.ts
const command = await findCommand("playwright")

// Finds in commands + skills map:
const allCommands = [
  // Built-in commands: /publish, /commit, ...
  ...getCommands(),

  // Skills mapped to commands
  ...skills.map(skillToCommandInfo)  // ← playwright is here
]
```

#### Step 4: Template Loading

```typescript
// From playwright skill
const content = `
# Playwright Browser Automation

This skill provides browser automation capabilities via the Playwright MCP server.

## When to Use
- Web scraping and data extraction
- Visual verification and screenshot capture
- Automated testing and form filling
- Browser interaction monitoring

## MCP Tools Available
- playwright_navigate: Navigate to a URL
- playwright_screenshot: Capture page screenshots
- playwright_click: Click elements on page
- playwright_fill: Fill form fields

<user-request>
$ARGUMENTS
</user-request>
`
```

#### Step 5: Argument Replacement

```typescript
const formattedContent = replaceArguments(content, args)

// Result:
# Playwright Browser Automation

This skill provides browser automation capabilities via the Playwright MCP server.

## When to Use
- Web scraping and data extraction
- Visual verification and screenshot capture
- Automated testing and form filling
- Browser interaction monitoring

## MCP Tools Available
- playwright_navigate: Navigate to a URL
- playwright_screenshot: Capture page screenshots
- playwright_click: Click elements on page
- playwright_fill: Fill form fields

<user-request>
test the login form on localhost:3000
</user-request>
```

#### Step 6: Final Formatting

```typescript
const formatted = `
<auto-slash-command>
## Slash Command: /playwright
## Description: MUST USE for any browser-related tasks. Browser automation via Playwright MCP - verification, browsing, information gathering, web scraping, testing, screenshots, and all browser interactions.

# Playwright Browser Automation

This skill provides browser automation capabilities via the Playwright MCP server.

## When to Use
- Web scraping and data extraction
- Visual verification and screenshot capture
- Automated testing and form filling
- Browser interaction monitoring

## MCP Tools Available
- playwright_navigate: Navigate to a URL
- playwright_screenshot: Capture page screenshots
- playwright_click: Click elements on page
- playwright_fill: Fill form fields

<user-request>
test the login form on localhost:3000
</user-request>
</auto-slash-command>
`
```

#### Step 7: Message Replacement

```typescript
// Original user message replaced
ctx.output.parts[0].text = formatted

// Agent receives this as the "user message"
```

### 8.3 Agent's Perspective

The agent sees the formatted template as the **user's message** and immediately receives the skill's expertise as context. The agent can now:

1. Use Playwright MCP tools (automatically enabled)
2. Follow the skill's best practices
3. Execute the specific task: "test the login form on localhost:3000"

## 9. Creating Custom Slash Commands

### 9.1 File-Based Skill

```markdown
<!-- ~/.config/opencode/skills/api-designer.md -->

---
name: api-designer
description: REST API design expert
agent: oracle
model: openai/gpt-5.2
allowed-tools: lsp_goto_definition lsp_references
---

# API Designer

You are an API design specialist with expertise in REST principles and HTTP semantics.

## Design Principles

### 1. Resource-Centric URLs
- Use nouns, not verbs: `/users`, `/posts`
- Use plural for collections: `/users` not `/user`
- Hierarchy via nesting: `/users/{id}/posts`

### 2. HTTP Method Semantics
- GET: Retrieve (safe, idempotent)
- POST: Create (non-idempotent)
- PUT: Full replace (idempotent)
- PATCH: Partial update (idempotent)
- DELETE: Remove (idempotent)

### 3. Status Codes
- 2xx: Success (200, 201, 204)
- 4xx: Client error (400, 404, 409, 422)
- 5xx: Server error (500, 502, 503)

<user-request>
$ARGUMENTS
</user-request>
```

**Usage**:
```
/api-designer design a user management API with authentication
```

### 9.2 Directory-Based Skill

```
~/.claude/skills/my-skill/
├── SKILL.md
├── mcp.json          # Optional MCP server config
└── examples/
    ├── basic-example.md
    └── advanced-example.md
```

**SKILL.md**:
```markdown
---
name: my-skill
description: Custom skill with examples
---

# My Skill

<user-request>
$ARGUMENTS
</user-request>
```

**Usage**:
```
/my-scaffold do something
```

### 9.3 Config-Based Skill

```json
// oh-my-opencode.json
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

## 10. Usage Patterns

### 10.1 Direct Slash Command

```
/playwright test login form
```

**Best for**: Quick tasks, exploratory work

### 10.2 Using `skill` Tool

```typescript
skill(name="playwright")
```

**Best for**: Reading skill instructions without immediate execution

### 10.3 Using `delegate_task`

```typescript
delegate_task({
  load_skills: ["playwright"],
  prompt: "test login form",
  category: "quick",
  run_in_background: false
})
```

**Best for**: Background tasks, complex workflows, multiple skills

## 11. Key Features

### 11.1 Auto-Discovery

- New `.md` files are immediately available as slash commands
- No registration required
- Scanned from multiple directories

### 11.2 Prioritization

```
opencode-project (highest) > project > opencode > user > builtin (lowest)
```

Higher-priority skills override lower-priority ones with the same name.

### 11.3 Argument Passing

```typescript
"/skill arg1 arg2"  →  args = "arg1 arg2"
```

User input is automatically injected into `$ARGUMENTS` placeholder.

### 11.4 Model/Agent Specification

Skills can specify `model` and `agent` in metadata:

```yaml
---
agent: oracle
model: openai/gpt-5.2
---
```

These are automatically applied when the slash command is executed.

### 11.5 MCP Integration

Skills can define required MCP servers:

```markdown
---
mcp:
  playwright:
    command: npx
    args: ["@playwright/mcp@latest"]
---
```

MCP servers are automatically launched when the skill is used.

### 11.6 Tagged Output

Replaced messages are wrapped in `<auto-slash-command>` tags for identification:

```markdown
<auto-slash-command>
...
</auto-slash-command>
```

This allows the system to distinguish slash command outputs from regular messages.

## 12. Summary

1. **Automatic Exposure**: All skills (built-in + custom) are automatically available as slash commands

2. **No Configuration**: No registration needed - just create `.md` files

3. **Priority System**: Multiple sources with clear override rules

4. **Variable Support**: `$ARGUMENTS` placeholder for user input

5. **Metadata Application**: Model, agent, and MCP config automatically applied

6. **Three Usage Modes**:
   - `/skill-name` (direct slash command)
   - `skill(name="skill-name")` (read instructions)
   - `delegate_task(load_skills=["skill-name"], ...)` (background task)

The slash command system provides a seamless way to access skill-based workflows without complex configuration or manual registration.
