# Oh My OpenCode Survey: Overview

## 1. Project Goal
**Oh My OpenCode** acts as a "batteries-included" plugin for [Claude Code](https://code.claude.com) (and compatible runners like OpenCode). Its primary goal is to transform a standard LLM coding agent into a **multi-agent orchestration system**.

Key objectives:
- **Orchestration**: Shift from a single agent to a team of specialized agents (Sisyphus, Oracle, Librarian, Explore).
- **Automation**: Automate context management, background tasks, and tool execution.
- **Reliability**: enforce task completion via "Todo Continuation Enforcer" and "Ralph Loop".
- **Integration**: Provide a unified layer for MCPs (Model Context Protocol), LSP (Language Server Protocol), and AST-Grep.

## 2. High-Level Architecture

The project is structured as a **Plugin** for the OpenCode SDK.

### Core Components
1.  **Plugin Entry (`src/index.ts`)**: Initializes the system, registers 30+ hooks, and sets up tool chains.
2.  **Hooks System (`src/hooks/`)**: A massive event-intercepting layer. Hooks can:
    -   Block/Modify tool execution (`PreToolUse`).
    -   Analyze/Truncate output (`PostToolUse`).
    -   Inject context (`UserPromptSubmit`).
    -   Manage lifecycle (Session start/stop).
3.  **Agent System (`src/agents/`)**: Defines specialized personas.
    -   **Sisyphus**: The main orchestrator (Claude Opus 4.5).
    -   **Oracle**: High-intelligence advisor (GPT-5.2).
    -   **Librarian**: Research and documentation expert (GLM-4.7).
    -   **Explore**: Fast codebase analysis (Grok Code).
4.  **Tooling Layer (`src/tools/`)**:
    -   **Local Tools**: Built-in tools like `bash`, `read`, `write`.
    -   **Delegation**: `delegate_task` to spawn background agents.
    -   **Skills**: Reusable workflows (e.g., `playwright`, `git-master`).
5.  **Background Manager (`src/features/background-agent/`)**: Handles async task execution, concurrency, and result collection.

## 3. Key Features
-   **Multi-Model Orchestration**: Different models for different tasks (Coding, Reasoning, Research).
-   **Context Management**: Aggressive context pruning (`tool-output-truncator`), auto-summarization (`compaction-context-injector`), and file injection.
-   **Resilience**:
    -   `todo-continuation-enforcer`: Prevents the agent from stopping before the task is done.
    -   `session-recovery`: Recovers from API errors.
    -   `edit-error-recovery`: Auto-fixes tool usage errors.
-   **Compatibility**: Emulates Claude Code's native features (MCP loading, configuration) while extending them.

## 4. Tech Stack
-   **Runtime**: Bun (exclusively).
-   **Language**: TypeScript.
-   **SDKs**: `@opencode-ai/sdk`, `@opencode-ai/plugin`, `@modelcontextprotocol/sdk`.
-   **Analysis Tools**: `ast-grep` (via napi), `typescript` (LSP).

## 5. Execution Flow
1.  **Initialization**: `OhMyOpenCodePlugin` loads config, enables hooks.
2.  **Event Loop**:
    -   User sends message -> `chat.message` hooks (e.g., `keyword-detector`).
    -   Agent calls tool -> `tool.execute.before` hooks (e.g., `permission-check`).
    -   Tool executes.
    -   Tool finishes -> `tool.execute.after` hooks (e.g., `truncator`).
3.  **Delegation**: If a task is complex, Sisyphus calls `delegate_task` or `background_task`, spawning a new session with a specialized agent.
