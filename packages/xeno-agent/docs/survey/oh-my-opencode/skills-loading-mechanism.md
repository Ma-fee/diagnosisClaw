# Skills Loading Mechanism in oh-my-opencode

**Generated:** 2026-02-04
**Source:** oh-my-opencode codebase survey

## Table of Contents

1. [Overview](#overview)
2. [Skill Definition and Storage](#skill-definition-and-storage)
3. [Skill Type Definitions](#skill-type-definitions)
4. [Skill Loading Flow](#skill-loading-flow)
5. [Built-in Skills](#built-in-skills)
6. [External Skill Discovery](#external-skill-discovery)
7. [Skill Registration and Initialization](#skill-registration-and-initialization)
8. [Skill MCP Integration](#skill-mcp-integration)
9. [Runtime Execution](#runtime-execution)
10. [Configuration](#configuration)

---

## Overview

The skills system in oh-my-opencode is a modular, extensible framework for loading and executing domain-specific instructions for AI agents. Skills can be:

1. **Built-in**: Defined in TypeScript code within the plugin
2. **OpenCode-project**: Stored in `.opencode/skills/` directories
3. **OpenCode-global**: Stored in `~/.config/opencode/skills/`
4. **Claude Code project**: Stored in `.claude/skills/` (for compatibility)
5. **Claude Code global**: Stored in `~/.claude/skills/` (for compatibility)

The skill system supports:
- Frontmatter-based metadata (YAML)
- MCP server integration per-skill
- Lazy/eager content loading
- Scope-based priority resolution
- Dynamic discovery from multiple directories

---

## Skill Definition and Storage

### Directory Structure

```
src/features/builtin-skills/
├── index.ts           # Main entry point (23 lines)
├── types.ts           # BuiltinSkill interface
├── skills.ts          # Skill definitions exported
├── skills.test.ts
└── skills/
    ├── index.ts       # Barrel exports
    ├── playwright.ts  # Playwright browser automation (313 lines)
    ├── agent-browser.ts
    ├── frontend-ui-ux.ts
    ├── git-master.ts  # Git operations (1108 lines)
    └── dev-browser.ts
```

### File Paths

| Component | Path | Lines | Purpose |
|-----------|-------|-------|---------|
| Main entry | `/Users/yuchen.liu/src/oh-my-opencode/src/features/builtin-skills/index.ts` | 23 | Export builtin skills |
| Types | `/Users/yuchen.liu/src/oh-my-opencode/src/features/builtin-skills/types.ts` | 17 | `BuiltinSkill` interface |
| Skills loader | `/Users/yuchen.liu/src/oh-my-opencode/src/features/opencode-skill-loader/loader.ts` | 269 | External skill discovery |
| Async loader | `/Users/yuchen.liu/src/oh-my-opencode/src/features/opencode-skill-loader/async-loader.ts` | 188 | Concurrent skill loading |
| Merger | `/Users/yuchen.liu/src/oh-my-opencode/src/features/opencode-skill-loader/merger.ts` | 276 | Skill merging logic |
| Skill content | `/Users/yuchen.liu/src/oh-my-opencode/src/features/opencode-skill-loader/skill-content.ts` | 211 | Content resolution |
| Skill tool | `/Users/yuchen.liu/src/oh-my-opencode/src/tools/skill/tools.ts` | 212 | Runtime skill execution |
| Plugin entry | `/Users/yuchen.liu/src/oh-my-opencode/src/index.ts` | 871 | Main plugin initialization |

---

## Skill Type Definitions

### BuiltinSkill Interface

**File:** `src/features/builtin-skills/types.ts` (lines 3-16)

```typescript
export interface BuiltinSkill {
  name: string                    // Skill identifier
  description: string             // Human-readable description
  template: string                // Instruction template content
  license?: string               // License information
  compatibility?: string        // Compatibility notes
  metadata?: Record<string, unknown>
  allowedTools?: string[]       // Whitelisted tool names
  agent?: string                // Restricted agent (if any)
  model?: string               // Preferred model
  subtask?: boolean            // Is this a subtask skill?
  argumentHint?: string         // Usage hint for arguments
  mcpConfig?: SkillMcpConfig  // Embedded MCP servers
}
```

### LoadedSkill Interface

**File:** `src/features/opencode-skill-loader/types.ts` (lines 26-38)

```typescript
export interface LoadedSkill {
  name: string
  path?: string                  // Original file path
  resolvedPath?: string          // Resolved symlink path
  definition: CommandDefinition  // OpenCode-compatible definition
  scope: SkillScope            // Source scope (priority)
  license?: string
  compatibility?: string
  metadata?: Record<string, string>
  allowedTools?: string[]
  mcpConfig?: SkillMcpConfig
  lazyContent?: LazyContentLoader
}
```

### Skill Scope Types

**File:** `src/features/opencode-skill-loader/types.ts` (line 4)

```typescript
export type SkillScope = 
  | "builtin"          // Built-in skills (priority: 1)
  | "config"           // Config-defined skills (priority: 2)
  | "user"             // Claude Code user skills (priority: 3)
  | "opencode"         // OpenCode global skills (priority: 4)
  | "project"          // Claude Code project skills (priority: 5)
  | "opencode-project" // OpenCode project skills (priority: 6)
```

Higher priority numbers override lower priority skills with the same name.

---

## Skill Loading Flow

### Main Entry Point: Plugin Initialization

**File:** `src/index.ts` (lines 417-445)

```typescript
// Load configuration
const browserProvider = pluginConfig.browser_automation_engine?.provider ?? "playwright"
const disabledSkills = new Set(pluginConfig.disabled_skills ?? [])
const systemMcpNames = getSystemMcpServerNames()

// Step 1: Create built-in skills
const builtinSkills = createBuiltinSkills({ browserProvider })
  .filter((skill) => {
    // Filter disabled skills
    if (disabledSkills.has(skill.name as never)) return false
    // Filter skills with conflicting MCP servers
    if (skill.mcpConfig) {
      for (const mcpName of Object.keys(skill.mcpConfig)) {
        if (systemMcpNames.has(mcpName)) return false
      }
    }
    return true
  })

// Step 2: Discover external skills in parallel
const includeClaudeSkills = pluginConfig.claude_code?.skills !== false
const [userSkills, globalSkills, projectSkills, opencodeProjectSkills] =
  await Promise.all([
    includeClaudeSkills ? discoverUserClaudeSkills() : Promise.resolve([]),
    discoverOpencodeGlobalSkills(),
    includeClaudeSkills ? discoverProjectClaudeSkills() : Promise.resolve([]),
    discoverOpencodeProjectSkills(),
  ])

// Step 3: Merge all skill sources
const mergedSkills = mergeSkills(
  builtinSkills,
  pluginConfig.skills,
  userSkills,
  globalSkills,
  projectSkills,
  opencodeProjectSkills,
)
```

### Skill Discovery Functions

**File:** `src/features/opencode-skill-loader/loader.ts` (lines 249-268)

```typescript
// Discover from multiple sources in parallel
export async function discoverUserClaudeSkills(): Promise<LoadedSkill[]> {
  const userSkillsDir = join(getClaudeConfigDir(), "skills")
  return loadSkillsFromDir(userSkillsDir, "user")
}

export async function discoverProjectClaudeSkills(): Promise<LoadedSkill[]> {
  const projectSkillsDir = join(process.cwd(), ".claude", "skills")
  return loadSkillsFromDir(projectSkillsDir, "project")
}

export async function discoverOpencodeGlobalSkills(): Promise<LoadedSkill[]> {
  const configDir = getOpenCodeConfigDir({ binary: "opencode" })
  const opencodeSkillsDir = join(configDir, "skills")
  return loadSkillsFromDir(opencodeSkillsDir, "opencode")
}

export async function discoverOpencodeProjectSkills(): Promise<LoadedSkill[]> {
  const opencodeProjectDir = join(process.cwd(), ".opencode", "skills")
  return loadSkillsFromDir(opencodeProjectDir, "opencode-project")
}
```

### Directory Loading Logic

**File:** `src/features/opencode-skill-loader/loader.ts` (lines 131-173)

```typescript
async function loadSkillsFromDir(skillsDir: string, scope: SkillScope): Promise<LoadedSkill[]> {
  const entries = await fs.readdir(skillsDir, { withFileTypes: true }).catch(() => [])
  const skills: LoadedSkill[] = []

  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue

    const entryPath = join(skillsDir, entry.name)

    // Directory with SKILL.md
    if (entry.isDirectory() || entry.isSymbolicLink()) {
      const resolvedPath = await resolveSymlinkAsync(entryPath)
      const dirName = entry.name

      const skillMdPath = join(resolvedPath, "SKILL.md")
      try {
        await fs.access(skillMdPath)
        const skill = await loadSkillFromPath(skillMdPath, resolvedPath, dirName, scope)
        if (skill) skills.push(skill)
        continue
      } catch {}

      // Directory with {name}.md
      const namedSkillMdPath = join(resolvedPath, `${dirName}.md`)
      try {
        await fs.access(namedSkillMdPath)
        const skill = await loadSkillFromPath(namedSkillMdPath, resolvedPath, dirName, scope)
        if (skill) skills.push(skill)
        continue
      } catch {}
    }

    // Direct .md file
    if (isMarkdownFile(entry)) {
      const skillName = basename(entry.name, ".md")
      const skill = await loadSkillFromPath(entryPath, skillsDir, skillName, scope)
      if (skill) skills.push(skill)
    }
  }

  return skills
}
```

### Frontmatter Parsing

**File:** `src/features/opencode-skill-loader/loader.ts` (lines 65-129)

```typescript
async function loadSkillFromPath(
  skillPath: string,
  resolvedPath: string,
  defaultName: string,
  scope: SkillScope
): Promise<LoadedSkill | null> {
  try {
    const content = await fs.readFile(skillPath, "utf-8")
    const { data, body } = parseFrontmatter<SkillMetadata>(content)
    
    // Parse MCP config from frontmatter or mcp.json
    const frontmatterMcp = parseSkillMcpConfigFromFrontmatter(content)
    const mcpJsonMcp = await loadMcpJsonFromDir(resolvedPath)
    const mcpConfig = mcpJsonMcp || frontmatterMcp

    const skillName = data.name || defaultName
    const originalDescription = data.description || ""
    const isOpencodeSource = scope === "opencode" || scope === "opencode-project"
    const formattedDescription = `(${scope} - Skill) ${originalDescription}`

    // Wrap template with standardized structure
    const templateContent = `<skill-instruction>
Base directory for this skill: ${resolvedPath}/
File references (@path) in this skill are relative to this directory.

${body.trim()}
</skill-instruction>

<user-request>
$ARGUMENTS
</user-request>`

    // Create eager loader (actual content read upfront)
    const eagerLoader: LazyContentLoader = {
      loaded: true,
      content: templateContent,
      load: async () => templateContent,
    }

    const definition: CommandDefinition = {
      name: skillName,
      description: formattedDescription,
      template: templateContent,
      model: sanitizeModelField(data.model, isOpencodeSource ? "opencode" : "claude-code"),
      agent: data.agent,
      subtask: data.subtask,
      argumentHint: data["argument-hint"],
    }

    return {
      name: skillName,
      path: skillPath,
      resolvedPath,
      definition,
      scope,
      license: data.license,
      compatibility: data.compatibility,
      metadata: data.metadata,
      allowedTools: parseAllowedTools(data["allowed-tools"]),
      mcpConfig,
      lazyContent: eagerLoader,
    }
  } catch {
    return null
  }
}
```

---

## Built-in Skills

### Skill Factory Function

**File:** `src/features/builtin-skills/skills.ts` (lines 16-22)

```typescript
export interface CreateBuiltinSkillsOptions {
  browserProvider?: BrowserAutomationProvider
}

export function createBuiltinSkills(options: CreateBuiltinSkillsOptions = {}): BuiltinSkill[] {
  const { browserProvider = "playwright" } = options

  // Select browser skill based on configuration
  const browserSkill = browserProvider === "agent-browser" ? agentBrowserSkill : playwrightSkill

  return [browserSkill, frontendUiUxSkill, gitMasterSkill, devBrowserSkill]
}
```

### Available Built-in Skills

| Skill Name | File | Lines | Purpose |
|-------------|-------|--------|---------|
| `playwright` | `skills/playwright.ts` | 313 | Playwright MCP browser automation |
| `agent-browser` | `skills/playwright.ts` | 313 | Vercel agent-browser CLI automation |
| `frontend-ui-ux` | `skills/frontend-ui-ux.ts` | UI/UX design tasks |
| `git-master` | `skills/git-master.ts` | 1108 | Git operations (commit, rebase, history) |
| `dev-browser` | `skills/dev-browser.ts` | 222 | Persistent browser automation |

### Example: Playwright Skill

**File:** `src/features/builtin-skills/skills/playwright.ts` (lines 3-15)

```typescript
export const playwrightSkill: BuiltinSkill = {
  name: "playwright",
  description: "MUST USE for any browser-related tasks...",
  template: `# Playwright Browser Automation

This skill provides browser automation capabilities via the Playwright MCP server.`,
  mcpConfig: {
    playwright: {
      command: "npx",
      args: ["@playwright/mcp@latest"],
    },
  },
}
```

---

## External Skill Discovery

### Supported Skill File Locations

| Priority | Location | Type | Scope |
|----------|----------|------|-------|
| 1 | Built-in TypeScript | Code | `builtin` |
| 2 | Config `skills` object | Config | `config` |
| 3 | `~/.claude/skills/` | Directory | `user` |
| 4 | `~/.config/opencode/skills/` | Directory | `opencode` |
| 5 | `.claude/skills/` | Directory | `project` |
| 6 | `.opencode/skills/` | Directory | `opencode-project` |

### Supported File Structures

1. **Directory with SKILL.md:**
   ```
   my-skill/
   ├── SKILL.md          # Frontmatter + content
   ├── mcp.json         # Optional MCP config
   └── references/       # Optional references
       └── guide.md
   ```

2. **Directory with {name}.md:**
   ```
   my-skill/
   ├── my-skill.md
   └── mcp.json
   ```

3. **Direct .md file:**
   ```
   skills/
   ├── my-skill.md
   └── another-skill.md
   ```

### Skill Metadata (Frontmatter)

**File:** `src/features/opencode-skill-loader/types.ts` (lines 6-18)

```yaml
---
name: my-skill
description: Description of what this skill does
model: anthropic/claude-opus-4-5
agent: sisyphus
subtask: false
argument-hint: "usage hint for arguments"
license: MIT
compatibility: opencode >= 1.0.150
metadata:
  author: name
  version: 1.0.0
allowed-tools: ["Bash", "Read", "Write"]

# Optional embedded MCP config
mcp:
  my-server:
    command: npx
    args: ["@example/mcp-server"]
---

# Skill instruction content
This is the actual skill template...
```

### MCP Configuration

**From Frontmatter:**
```yaml
---
mcp:
  server-name:
    command: npx
    args: ["@example/mcp-server"]
    env:
      API_KEY: ${ENV_VAR}
---
```

**From mcp.json:**
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["@example/mcp-server"]
    }
  }
}
```

---

## Skill Registration and Initialization

### Skill Merging Algorithm

**File:** `src/features/opencode-skill-loader/merger.ts` (lines 195-275)

```typescript
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

  // Priority constants
  const SCOPE_PRIORITY: Record<SkillScope, number> = {
    builtin: 1,
    config: 2,
    user: 3,
    opencode: 4,
    project: 5,
    "opencode-project": 6,
  }

  // Phase 1: Add built-in skills
  for (const builtin of builtinSkills) {
    const loaded = builtinToLoaded(builtin)
    skillMap.set(loaded.name, loaded)
  }

  // Phase 2: Add config-defined skills
  const normalizedConfig = normalizeConfig(config)
  for (const [name, entry] of Object.entries(normalizedConfig.entries)) {
    if (entry === false) continue
    if (entry === true) continue
    if (entry.disable) continue

    const loaded = configEntryToLoaded(name, entry, options.configDir)
    if (loaded) {
      const existing = skillMap.get(name)
      if (existing && !entry.template && !entry.from) {
        // Merge with existing
        skillMap.set(name, mergeSkillDefinitions(existing, entry))
      } else {
        // Override
        skillMap.set(name, loaded)
      }
    }
  }

  // Phase 3: Add file system skills (scope-based priority)
  const fileSystemSkills = [
    ...userClaudeSkills,
    ...userOpencodeSkills,
    ...projectClaudeSkills,
    ...projectOpencodeSkills,
  ]

  for (const skill of fileSystemSkills) {
    const existing = skillMap.get(skill.name)
    // Higher priority scope overrides
    if (!existing || SCOPE_PRIORITY[skill.scope] > SCOPE_PRIORITY[existing.scope]) {
      skillMap.set(skill.name, skill)
    }
  }

  // Phase 4: Apply config modifications again
  for (const [name, entry] of Object.entries(normalizedConfig.entries)) {
    if (entry === true) continue
    if (entry === false) {
      skillMap.delete(name)  // Explicitly disabled
      continue
    }
    if (entry.disable) {
      skillMap.delete(name)
      continue
    }

    const existing = skillMap.get(name)
    if (existing && !entry.template && !entry.from) {
      skillMap.set(name, mergeSkillDefinitions(existing, entry))
    }
  }

  // Phase 5: Apply disable list
  for (const name of normalizedConfig.disable) {
    skillMap.delete(name)
  }

  // Phase 6: Apply enable list (whitelist mode)
  if (normalizedConfig.enable.length > 0) {
    const enableSet = new Set(normalizedConfig.enable)
    for (const name of skillMap.keys()) {
      if (!enableSet.has(name)) {
        skillMap.delete(name)
      }
    }
  }

  return Array.from(skillMap.values())
}
```

### Skill Tool Registration

**File:** `src/index.ts` (lines 448-458)

```typescript
// Create skill tool
const skillMcpManager = new SkillMcpManager()
const getSessionIDForMcp = () => getMainSessionID() || ""
const skillTool = createSkillTool({
  skills: mergedSkills,
  mcpManager: skillMcpManager,
  getSessionID: getSessionIDForMcp,
  gitMasterConfig: pluginConfig.git_master,
})

const skillMcpTool = createSkillMcpTool({
  manager: skillMcpManager,
  getLoadedSkills: () => mergedSkills,
  getSessionID: getSessionIDForMcp,
})

// Register in plugin tools
return {
  tool: {
    skill: skillTool,
    skill_mcp: skillMcpTool,
    // ... other tools
  },
  // ... plugin hooks
}
```

---

## Skill MCP Integration

### MCP Manager Lifecycle

**File:** `src/features/skill-mcp-manager/manager.ts` (lines 62-73)

```typescript
export class SkillMcpManager {
  private clients: Map<string, ManagedClient> = new Map()
  private pendingConnections: Map<string, Promise<Client>> = new Map()
  private authProviders: Map<string, McpOAuthProvider> = new Map()
  private readonly IDLE_TIMEOUT = 5 * 60 * 1000  // 5 minutes

  private getClientKey(info: SkillMcpClientInfo): string {
    return `${info.sessionID}:${info.skillName}:${info.serverName}`
  }
}
```

### Connection Types

**File:** `src/features/skill-mcp-manager/manager.ts` (lines 17-60)

```typescript
type ConnectionType = "stdio" | "http"

function getConnectionType(config: ClaudeCodeMcpServer): ConnectionType | null {
  // Explicit type takes priority
  if (config.type === "http" || config.type === "sse") {
    return "http"
  }
  if (config.type === "stdio") {
    return "stdio"
  }

  // Infer from available fields
  if (config.url) {
    return "http"
  }
  if (config.command) {
    return "stdio"
  }

  return null
}
```

### MCP Client Creation

**File:** `src/features/skill-mcp-manager/manager.ts` (lines 145-200)

```typescript
async getOrCreateClient(
  info: SkillMcpClientInfo,
  config: ClaudeCodeMcpServer
): Promise<Client> {
  const key = this.getClientKey(info)
  const existing = this.clients.get(key)

  if (existing) {
    existing.lastUsedAt = Date.now()
    return existing.client  // Reuse existing client
  }

  // Prevent race condition
  const pending = this.pendingConnections.get(key)
  if (pending) {
    return pending
  }

  const expandedConfig = expandEnvVarsInObject(config)
  const connectionPromise = this.createClient(info, expandedConfig)
  this.pendingConnections.set(key, connectionPromise)

  try {
    const client = await connectionPromise
    return client
  } finally {
    this.pendingConnections.delete(key)
  }
}
```

### Skill MCP Tool

**File:** `src/tools/skill-mcp/tools.ts` (lines 110-150)

```typescript
export function createSkillMcpTool(options: SkillMcpToolOptions): ToolDefinition {
  const { manager, getLoadedSkills, getSessionID } = options

  return tool({
    description: SKILL_MCP_DESCRIPTION,
    args: {
      mcp_name: tool.schema.string().describe("Name of MCP server from skill config"),
      tool_name: tool.schema.string().optional().describe("MCP tool to call"),
      resource_name: tool.schema.string().optional().describe("MCP resource URI to read"),
      prompt_name: tool.schema.string().optional().describe("MCP prompt to get"),
      arguments: tool.schema.union([...]).optional().describe("JSON arguments"),
      grep: tool.schema.string().optional().describe("Regex pattern to filter output"),
    },
    async execute(args: SkillMcpArgs) {
      const operation = validateOperationParams(args)
      const skills = getLoadedSkills()
      const found = findMcpServer(args.mcp_name, skills)

      if (!found) {
        throw new Error(`MCP server "${args.mcp_name}" not found.`)
      }

      const info: SkillMcpClientInfo = {
        serverName: args.mcp_name,
        skillName: found.skill.name,
        sessionID: getSessionID(),
      }

      // Execute MCP operation via manager
      const client = await manager.getOrCreateClient(info, found.config)
      // ... call tool/resource/prompt
    },
  })
}
```

---

## Runtime Execution

### Skill Tool Factory

**File:** `src/tools/skill/tools.ts` (lines 129-212)

```typescript
export function createSkillTool(options: SkillLoadOptions = {}): ToolDefinition {
  let cachedSkills: LoadedSkill[] | null = null
  let cachedDescription: string | null = null

  const getSkills = async (): Promise<LoadedSkill[]> => {
    if (options.skills) return options.skills
    if (cachedSkills) return cachedSkills
    cachedSkills = await getAllSkills()
    return cachedSkills
  }

  const getDescription = async (): Promise<string> => {
    if (cachedDescription) return cachedDescription
    const skills = await getSkills()
    const skillInfos = skills.map(loadedSkillToInfo)
    cachedDescription = skillInfos.length === 0
      ? TOOL_DESCRIPTION_NO_SKILLS
      : TOOL_DESCRIPTION_PREFIX + formatSkillsXml(skillInfos)
    return cachedDescription
  }

  return tool({
    get description() {
      return cachedDescription ?? TOOL_DESCRIPTION_PREFIX
    },
    args: {
      name: tool.schema.string().describe("The skill identifier"),
    },
    async execute(args: SkillArgs, ctx?: { agent?: string }) {
      const skills = await getSkills()
      const skill = skills.find(s => s.name === args.name)

      if (!skill) {
        const available = skills.map(s => s.name).join(", ")
        throw new Error(`Skill "${args.name}" not found. Available: ${available}`)
      }

      // Agent restriction check
      if (skill.definition.agent && (!ctx?.agent || skill.definition.agent !== ctx.agent)) {
        throw new Error(`Skill "${args.name}" is restricted to agent "${skill.definition.agent}"`)
      }

      let body = await extractSkillBody(skill)

      // Special handling for git-master config injection
      if (args.name === "git-master") {
        body = injectGitMasterConfig(body, options.gitMasterConfig)
      }

      const dir = skill.path ? dirname(skill.path) : skill.resolvedPath || process.cwd()

      const output = [
        `## Skill: ${skill.name}`,
        "",
        `**Base directory**: ${dir}`,
        "",
        body,
      ]

      // Append MCP capabilities if configured
      if (options.mcpManager && options.getSessionID && skill.mcpConfig) {
        const mcpInfo = await formatMcpCapabilities(
          skill,
          options.mcpManager,
          options.getSessionID()
        )
        if (mcpInfo) {
          output.push(mcpInfo)
        }
      }

      return output.join("\n")
    },
  })
}
```

### Skill Body Extraction

**File:** `src/tools/skill/tools.ts` (lines 43-56)

```typescript
async function extractSkillBody(skill: LoadedSkill): Promise<string> {
  if (skill.lazyContent) {
    const fullTemplate = await skill.lazyContent.load()
    const templateMatch = fullTemplate.match(/<skill-instruction>([\s\S]*?)<\/skill-instruction>/)
    return templateMatch ? templateMatch[1].trim() : fullTemplate
  }

  if (skill.path) {
    return extractSkillTemplate(skill)
  }

  const templateMatch = skill.definition.template?.match(/<skill-instruction>([\s\S]*?)<\/skill-instruction>/)
  return templateMatch ? templateMatch[1].trim() : skill.definition.template || ""
}
```

### MCP Capabilities Formatting

**File:** `src/tools/skill/tools.ts` (lines 58-127)

```typescript
async function formatMcpCapabilities(
  skill: LoadedSkill,
  manager: SkillMcpManager,
  sessionID: string
): Promise<string | null> {
  if (!skill.mcpConfig || Object.keys(skill.mcpConfig).length === 0) {
    return null
  }

  const sections: string[] = ["", "## Available MCP Servers", ""]

  for (const [serverName, config] of Object.entries(skill.mcpConfig)) {
    const info: SkillMcpClientInfo = {
      serverName,
      skillName: skill.name,
      sessionID,
    }
    const context: SkillMcpServerContext = {
      config,
      skillName: skill.name,
    }

    sections.push(`### ${serverName}`)
    sections.push("")

    try {
      const [tools, resources, prompts] = await Promise.all([
        manager.listTools(info, context).catch(() => []),
        manager.listResources(info, context).catch(() => []),
        manager.listPrompts(info, context).catch(() => []),
      ])

      if (tools.length > 0) {
        sections.push("**Tools:**")
        sections.push("")
        for (const t of tools as Tool[]) {
          sections.push(`#### \`${t.name}\``)
          if (t.description) {
            sections.push(t.description)
          }
          sections.push("")
          sections.push("**inputSchema:**")
          sections.push("```json")
          sections.push(JSON.stringify(t.inputSchema, null, 2))
          sections.push("```")
          sections.push("")
        }
      }
      if (resources.length > 0) {
        sections.push(`**Resources**: ${resources.map((r: Resource) => r.uri).join(", ")}`)
      }
      if (prompts.length > 0) {
        sections.push(`**Prompts**: ${prompts.map((p: Prompt) => p.name).join(", ")}`)
      }

      if (tools.length === 0 && resources.length === 0 && prompts.length === 0) {
        sections.push("*No capabilities discovered*")
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      sections.push(`*Failed to connect: ${errorMessage.split("\n")[0]}*`)
    }

    sections.push("")
    sections.push(`Use \`skill_mcp\` tool with \`mcp_name="${serverName}"\` to invoke.`)
    sections.push("")
  }

  return sections.join("\n")
}
```

---

## Configuration

### Configuration Schema

**File:** `src/config/schema.ts` (lines 260-296)

```typescript
export const SkillSourceSchema = z.union([
  z.string(),
  z.object({
    path: z.string(),
    recursive: z.boolean().optional(),
    glob: z.string().optional(),
  }),
])

export const SkillDefinitionSchema = z.object({
  description: z.string().optional(),
  template: z.string().optional(),
  from: z.string().optional(),  // Load from file
  model: z.string().optional(),
  agent: z.string().optional(),
  subtask: z.boolean().optional(),
  "argument-hint": z.string().optional(),
  license: z.string().optional(),
  compatibility: z.string().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  "allowed-tools": z.array(z.string()).optional(),
  disable: z.boolean().optional(),
})

export const SkillsConfigSchema = z.union([
  z.array(z.string()),  // Simple enable list
  z.record(z.string(), SkillEntrySchema).and(z.object({
    sources: z.array(SkillSourceSchema).optional(),
    enable: z.array(z.string()).optional(),
    disable: z.array(z.string()).optional(),
  }).partial()),
])
```

### Example Configuration

```json
{
  "skills": {
    "sources": [
      "./custom-skills",
      { "path": "./vendor-skills", "recursive": true }
    ],
    "enable": ["my-custom-skill", "git-master"],
    "disable": ["playwright"],
    "my-custom-skill": {
      "description": "My custom skill",
      "template": "...",
      "model": "anthropic/claude-opus-4-5"
    }
  },
  "disabled_skills": ["agent-browser"],
  "git_master": {
    "commit_footer": true,
    "include_co_authored_by": true
  },
  "browser_automation_engine": {
    "provider": "playwright"
  }
}
```

### Built-in Skill Names

**File:** `src/config/schema.ts` (lines 32-37)

```typescript
export const BuiltinSkillNameSchema = z.enum([
  "playwright",
  "agent-browser",
  "frontend-ui-ux",
  "git-master",
])
```

### Claude Code Compatibility Settings

**File:** `src/index.ts` (line 430)

```typescript
const includeClaudeSkills = pluginConfig.claude_code?.skills !== false
```

---

## Summary

### Key Components

| Component | File | Purpose |
|-----------|-------|---------|
| `createBuiltinSkills()` | `builtin-skills/skills.ts:16` | Create built-in skill instances |
| `discoverUserClaudeSkills()` | `opencode-skill-loader/loader.ts:249` | Load `~/.claude/skills/` |
| `discoverProjectClaudeSkills()` | `opencode-skill-loader/loader.ts:254` | Load `.claude/skills/` |
| `discoverOpencodeGlobalSkills()` | `opencode-skill-loader/loader.ts:259` | Load `~/.config/opencode/skills/` |
| `discoverOpencodeProjectSkills()` | `opencode-skill-loader/loader.ts:265` | Load `.opencode/skills/` |
| `mergeSkills()` | `opencode-skill-loader/merger.ts:195` | Merge all skill sources |
| `createSkillTool()` | `tools/skill/tools.ts:129` | Create skill execution tool |
| `createSkillMcpTool()` | `tools/skill-mcp/tools.ts:110` | Create MCP invocation tool |
| `SkillMcpManager` | `skill-mcp-manager/manager.ts:62` | Manage MCP client lifecycles |

### Loading Flow Diagram

```
Plugin Entry (index.ts:107)
    │
    ├─► Load plugin config
    │
    ├─► createBuiltinSkills()
    │   └─► Returns [playwright, git-master, ...]
    │
    ├─► discoverUserClaudeSkills()
    │   └─► scan ~/.claude/skills/
    │
    ├─► discoverOpencodeGlobalSkills()
    │   └─► scan ~/.config/opencode/skills/
    │
    ├─► discoverProjectClaudeSkills()
    │   └─► scan .claude/skills/
    │
    ├─► discoverOpencodeProjectSkills()
    │   └─► scan .opencode/skills/
    │
    └─► mergeSkills()
        │
        ├─► Filter disabled_skills
        │
        ├─► Apply scope priority
        │   builtin < config < user < opencode < project < opencode-project
        │
        └─► Return LoadedSkill[]

mergedSkills → createSkillTool() → Register in plugin
```

### MCP Integration Flow

```
Skill Execution
    │
    ├─► skill.name matches loaded skill
    │
    ├─► Check skill.mcpConfig
    │   │
    │   └─► For each MCP server:
    │       │
    │       ├─► SkillMcpManager.getOrCreateClient()
    │       │   │
    │       │   ├─► Check cache by sessionID:skillName:serverName
    │       │   │
    │       │   └─► Create client if needed
    │       │       ├─► Expand ${VAR} in config
    │       │       ├─► stdio: start process
    │       │       └─► http: connect to URL
    │       │
    │       ├─► List tools/resources/prompts
    │       │
    │       └─► Format as markdown
    │
    └─► Append to skill output
```

---

## Prompt Injection (Template Substitution)

### Overview

Skills use a **layered template assembly** approach where the final prompt is built through multiple stages of content injection and placeholder substitution.

### 1. Template Wrapping (Load Time)

**File:** `src/features/opencode-skill-loader/loader.ts` (lines 83-92)

When a skill is loaded from disk, its raw content is wrapped in a standardized XML structure:

```typescript
const templateContent = `<skill-instruction>
Base directory for this skill: ${resolvedPath}/
File references (@path) in this skill are relative to this directory.

${body.trim()}
</skill-instruction>

<user-request>
$ARGUMENTS
</user-request>`
```

| Component | Purpose |
|-----------|---------|
| `<skill-instruction>` | Contains the skill's core instructions and context |
| Base directory info | Tells the agent where the skill files are located |
| `${body.trim()}` | The actual skill content from SKILL.md (after frontmatter) |
| `<user-request>` | Wrapper for user arguments |
| `$ARGUMENTS` | **Placeholder** for user input (replaced by OpenCode runtime) |

### 2. Runtime Execution Flow

**File:** `src/tools/skill/tools.ts` (lines 166-207)

```typescript
async execute(args: SkillArgs, ctx?: { agent?: string }) {
  // Step 1: Find the skill
  const skills = await getSkills()
  const skill = skills.find(s => s.name === args.name)

  // Step 2: Extract skill body (strips XML tags)
  let body = await extractSkillBody(skill)

  // Step 3: Special config injection for git-master
  if (args.name === "git-master") {
    body = injectGitMasterConfig(body, options.gitMasterConfig)
  }

  // Step 4: Assemble output with metadata
  const output = [
    `## Skill: ${skill.name}`,
    "",
    `**Base directory**: ${dir}`,
    "",
    body,  // Contains $ARGUMENTS placeholder
  ]

  // Step 5: Append MCP capabilities if configured
  if (options.mcpManager && options.getSessionID && skill.mcpConfig) {
    const mcpInfo = await formatMcpCapabilities(...)
    output.push(mcpInfo)
  }

  return output.join("\n")
}
```

### 3. Body Extraction Logic

**File:** `src/tools/skill/tools.ts` (lines 43-56)

```typescript
async function extractSkillBody(skill: LoadedSkill): Promise<string> {
  if (skill.lazyContent) {
    const fullTemplate = await skill.lazyContent.load()
    // Extract content between <skill-instruction> tags
    const templateMatch = fullTemplate.match(/<skill-instruction>([\s\S]*?)<\/skill-instruction>/)
    return templateMatch ? templateMatch[1].trim() : fullTemplate
  }

  if (skill.path) {
    return extractSkillTemplate(skill)
  }

  const templateMatch = skill.definition.template?.match(/<skill-instruction>([\s\S]*?)<\/skill-instruction>/)
  return templateMatch ? templateMatch[1].trim() : skill.definition.template || ""
}
```

### 4. Special Injection: git-master Config

**File:** `src/features/opencode-skill-loader/skill-content.ts`

For the `git-master` skill, additional configuration is injected dynamically:

```typescript
export function injectGitMasterConfig(
  body: string,
  config: GitMasterConfig | undefined
): string {
  if (!config) return body

  const configSection = `
<git-master-config>
${JSON.stringify(config, null, 2)}
</git-master-config>`

  // Insert before closing </skill-instruction> tag
  return body.replace(/<\/skill-instruction>/, `${configSection}\n</skill-instruction>`)
}
```

Example output:
```xml
<skill-instruction>
  ... skill content ...

  <git-master-config>
  {
    "commit_footer": true,
    "include_co_authored_by": true
  }
  </git-master-config>
</skill-instruction>
```

### 5. Built-in Skills: No Placeholders

Built-in skills defined in TypeScript don't use `$ARGUMENTS` because they're code-defined:

```typescript
export const playwrightSkill: BuiltinSkill = {
  name: "playwright",
  description: "MUST USE for any browser-related tasks...",
  template: `# Playwright Browser Automation

This skill provides browser automation...`,  // Complete content
  mcpConfig: {
    playwright: {
      command: "npx",
      args: ["@playwright/mcp@latest"],
    },
  },
}
```

### 6. $ARGUMENTS Replacement

**Critical:** The `$ARGUMENTS` placeholder is **NOT replaced by oh-my-opencode**. It is preserved in the returned template and replaced by **OpenCode itself** when the skill is invoked.

Flow:
```
User: "skill name=git-master arguments=commit"
    ↓
oh-my-opencode skill tool returns:
    "## Skill: git-master\n\n**Base directory**: ...\n\n<skill-instruction>...$ARGUMENTS...</skill-instruction>"
    ↓
OpenCode replaces $ARGUMENTS with "commit"
    ↓
Final prompt sent to LLM
```

### 7. MCP Capabilities Injection

**File:** `src/tools/skill/tools.ts` (lines 58-127)

If a skill has MCP servers configured, their capabilities are dynamically discovered and appended:

```typescript
async function formatMcpCapabilities(skill, manager, sessionID): Promise<string | null> {
  if (!skill.mcpConfig) return null

  const sections: string[] = ["", "## Available MCP Servers", ""]

  for (const [serverName, config] of Object.entries(skill.mcpConfig)) {
    // Connect to MCP server
    const [tools, resources, prompts] = await Promise.all([
      manager.listTools(info, context),
      manager.listResources(info, context),
      manager.listPrompts(info, context),
    ])

    // Format as markdown
    sections.push(`### ${serverName}`)
    if (tools.length > 0) {
      sections.push("**Tools:**")
      tools.forEach(t => sections.push(`- \`${t.name}\`: ${t.description}`))
    }
    // ... resources, prompts
  }

  return sections.join("\n")
}
```

### Summary: Injection Layers

| Stage | Location | Action |
|-------|----------|--------|
| **Load** | `loader.ts:83-92` | Wrap raw skill content with XML tags, add `$ARGUMENTS` placeholder |
| **Extract** | `tools.ts:43-56` | Extract `<skill-instruction>` content at runtime |
| **Config** | `skill-content.ts` | Inject git-master JSON config (if applicable) |
| **MCP** | `tools.ts:58-127` | Dynamically append MCP server capabilities |
| **Replace** | OpenCode (external) | Replace `$ARGUMENTS` with actual user input |

---

## References

### Key Files

| File | Lines | Primary Function |
|------|-------|-----------------|
| `src/index.ts` | 871 | Main plugin entry |
| `src/features/builtin-skills/index.ts` | 23 | Built-in skills export |
| `src/features/builtin-skills/skills.ts` | 23 | Built-in skill factory |
| `src/features/opencode-skill-loader/loader.ts` | 269 | Skill discovery |
| `src/features/opencode-skill-loader/merger.ts` | 276 | Skill merging |
| `src/features/opencode-skill-loader/types.ts` | 39 | Type definitions |
| `src/features/opencode-skill-loader/skill-content.ts` | 211 | Content resolution |
| `src/tools/skill/tools.ts` | 212 | Skill execution tool |
| `src/tools/skill-mcp/tools.ts` | 195 | Skill MCP tool |
| `src/features/skill-mcp-manager/manager.ts` | 617 | MCP client management |
| `src/config/schema.ts` | 429 | Configuration schema |

### Skill Metadata Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Skill name (defaults to filename/dirname) |
| `description` | string | No | Human-readable description |
| `model` | string | No | Preferred AI model |
| `agent` | string | No | Restricted agent name |
| `subtask` | boolean | No | Mark as subtask skill |
| `argument-hint` | string | No | Usage hint |
| `license` | string | No | License information |
| `compatibility` | string | No | Compatibility notes |
| `metadata` | object | No | Custom metadata |
| `allowed-tools` | string[] | No | Whitelisted tools |
| `mcp` | object | No | Embedded MCP configuration |

---

**End of Document**
