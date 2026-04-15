# Oh My OpenCode Survey: Core Abstractions

## 1. Agents (`src/agents/`)

The agent system is designed around **specialization** and **orchestration**.

### Core Concepts
-   **AgentFactory**: A function `(model: string) => AgentConfig` that creates an agent instance.
-   **AgentPromptMetadata**: Defines how an agent is presented to the orchestrator (Sisyphus).
    -   `category`: "exploration" | "specialist" | "advisor" | "utility"
    -   `cost`: "FREE" | "CHEAP" | "EXPENSIVE"
    -   `triggers`: Heuristics for when to use this agent.
-   **Modes**:
    -   `"primary"`: The main entry point (Sisyphus).
    -   `"subagent"`: Specialized agents called via `delegate_task`.

### Key Agents
1.  **Sisyphus (Orchestrator)**:
    -   **Model**: `anthropic/claude-opus-4-5`
    -   **Role**: Manages the high-level plan, delegates tasks, and verifies results.
    -   **Prompt**: Dynamically built (`dynamic-agent-prompt-builder.ts`) to include available tools, agents, and skills.
2.  **Oracle (Advisor)**:
    -   **Model**: `openai/gpt-5.2`
    -   **Role**: High-intelligence reasoning for architecture and complex debugging.
    -   **Constraints**: Read-only (cannot write/edit code).
3.  **Librarian (Researcher)**:
    -   **Model**: `opencode/glm-4.7-free`
    -   **Role**: External research (GitHub, Docs).
    -   **Features**: Date-aware, citation-mandatory.
4.  **Explore (Grep)**:
    -   **Model**: `opencode/grok-code`
    -   **Role**: Fast codebase exploration.

### Configuration
Agents are configured via `src/config/schema.ts` and can be overridden by user settings (`prompt_append`, `model`, etc.).

## 2. Hooks (`src/hooks/`)

Hooks are the "middleware" of the system, intercepting events to enforce logic, safety, and context.

### Lifecycle Events
-   `chat.message`: Intercept user input (e.g., `keyword-detector` for "ultrawork").
-   `tool.execute.before`: Block or modify tool calls (e.g., `permission-check`).
-   `tool.execute.after`: Transform output (e.g., `truncator`).
-   `event` (`session.idle`): Background tasks (e.g., `todo-continuation-enforcer`).

### Critical Hooks
-   **Atlas (`src/hooks/atlas/`)**: The "Brain" of the orchestration.
    -   Enforces delegation (blocks direct writes by Sisyphus in complex tasks).
    -   Manages the **Boulder State** (persistent plan tracking).
    -   Injects verification steps into `delegate_task` output.
-   **Context Injectors**:
    -   `directory-agents-injector`: Injects `AGENTS.md` from the current directory.
    -   `rules-injector`: Injects project-specific rules.

## 3. Tools (`src/tools/`)

Tools provide the actual capabilities.

### Categories
-   **Built-in Tools**: `bash`, `read`, `write`, `edit`.
-   **Delegation Tools**:
    -   `delegate_task`: Synchronous delegation (sub-session).
    -   `background_task`: Async delegation (fire-and-forget).
-   **MCP Tools**: Imported from Model Context Protocol servers.
-   **Skill Tools**: Dynamic tools exposed by enabled skills (e.g., `playwright`).

### Permission System
-   `src/shared/permission-compat.ts` defines `allow`, `ask`, `deny` logic.
-   Specialized agents have strict deny-lists (e.g., Oracle cannot `write`).

## 4. Skills (`src/features/builtin-skills/`)

Skills are reusable "capabilities" that can be mixed into agents.

-   **Definition**: TypeScript objects with `name`, `description`, `template`, and `mcpConfig`.
-   **Integration**:
    -   Prompts are injected into the agent's system prompt.
    -   MCP servers (if any) are started on demand.
-   **Examples**:
    -   `git-master`: Complex git workflows.
    -   `playwright`: Browser automation via MCP.
