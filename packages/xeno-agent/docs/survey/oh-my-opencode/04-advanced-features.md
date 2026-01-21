# Oh My OpenCode Survey: Advanced Features

## 1. Background Task System (`src/features/background-agent/`)

Allows the agent to run tasks asynchronously, enabling parallelism.

### Architecture
-   **Manager**: A singleton `BackgroundAgentManager` handling the lifecycle.
-   **Concurrency**:
    -   Per-model/provider limits (e.g., max 2 concurrent GPT-5 calls).
    -   Queue system (`concurrency.ts`) manages wait-lists.
-   **Lifecycle**:
    -   `launch()` -> Returns `task_id`.
    -   `poll()` -> Checks status.
    -   `notify()` -> Toasts the user when done.

### Use Cases
-   **Research**: Launch 3 `librarian` agents to search different docs simultaneously.
-   **Exploration**: Launch 3 `explore` agents to grep different parts of the codebase.

## 2. Context Management (`src/features/context-injector/`)

A sophisticated system to manage the limited context window.

### Mechanisms
1.  **Injection**:
    -   `ContextCollector` gathers relevant files (`AGENTS.md`, `rules.md`).
    -   Injects them into the chat stream via `messages.transform` hook.
2.  **Pruning**:
    -   `tool-output-truncator`: Truncates massive tool outputs (e.g., 5000-line reads) to save space.
    -   `pruning-deduplication`: Removes duplicate tool calls from the history.
3.  **Compaction Recovery**:
    -   When context is full, the system "compacts" (summarizes) history.
    -   `compaction-context-injector` ensures critical context (current plan, rules) is *re-injected* after compaction.

## 3. MCP (Model Context Protocol) Integration (`src/mcp/`)

First-class support for the MCP standard.

### Three-Tier Architecture
1.  **Built-in MCPs**:
    -   `websearch`: Exa-based search.
    -   `context7`: Documentation resolver.
    -   `grep_app`: GitHub code search.
2.  **Claude Code Compat**:
    -   Loads `.mcp.json` configuration compatible with Claude Code.
    -   Supports environment variable expansion.
3.  **Skill-Embedded MCPs**:
    -   Skills can define their own MCP requirements (e.g., `playwright` skill loads `@playwright/mcp`).
    -   **Lazy Loading**: MCP servers are only started when the skill is actually used.

## 4. Resilience Features

-   **Todo Continuation Enforcer**:
    -   If the agent stops while Todos are marked `pending`, this hook injects a system prompt: "You have pending tasks. Please continue."
-   **Ralph Loop**:
    -   A specialized loop for "Iterative improvement".
-   **Session Recovery**:
    -   Handles API 500/503 errors by retrying with exponential backoff.
-   **Edit Error Recovery**:
    -   If `edit` fails (e.g., "text not found"), this hook analyzes the failure and suggests a fix (e.g., "Try using a larger context").
