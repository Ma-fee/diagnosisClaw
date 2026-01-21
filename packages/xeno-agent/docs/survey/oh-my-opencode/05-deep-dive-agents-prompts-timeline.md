# Oh My OpenCode Survey: Deep Dive

## 1. Turn Lifecycle & Event Loop

Oh My OpenCode implements a strict event-driven lifecycle for every conversation turn.

### The Timeline (T0 - T5)

**T0: User Message** (`chat.message`)
1.  **Keyword Detection**: `keyword-detector` checks for triggers like "ultrawork" or "loop".
2.  **Context Injection**: `directory-agents-injector`, `rules-injector` inject context into the message.
3.  **Variant Selection**: `first-message-variant-gate` determines if a special persona variant is needed (e.g., "Sisyphus-Junior" for subagents).

**T1: Agent Thinking (The LLM)**
-   The Agent receives the processed message + system prompt.
-   It generates a "Think" block (if enabled) and decides on a tool call.

**T2: Pre-Tool Execution** (`tool.execute.before`)
1.  **Safety Checks**: `comment-checker`, `non-interactive-env` validation.
2.  **Atlas Interception**:
    -   **Delegation Check**: If Sisyphus calls `write/edit` on a complex task, Atlas BLOCKS it and suggests `delegate_task`.
    -   **Context Injection**: Injects specific file context if missing.
3.  **Task Analysis**: `delegate-task-retry` prepares for potential failures.

**T3: Tool Execution**
-   The tool runs (local bash, API call, or sub-agent delegation).
-   If `delegate_task` is called, a **Sub-Session** is spawned (recursion).

**T4: Post-Tool Execution** (`tool.execute.after`)
1.  **Output Truncation**: `tool-output-truncator` drastically cuts output (e.g., "Read 5000 lines... [Truncated to 500]").
2.  **Context Compaction**: `context-window-monitor` checks token usage. If critical, triggers summarization.
3.  **Error Recovery**: `edit-error-recovery` analyzes failure (e.g., "String not found") and injects a "Try this fix" message.
4.  **Atlas Verification**:
    -   If a `task` completed, Atlas injects the **Verification Checklist** ("Run lsp_diagnostics", "Run tests").
    -   Atlas updates the **Boulder State** if a plan item is checked.

**T5: Response Generation**
-   The result is fed back to the Agent.
-   Cycle repeats until the Agent yields a text response to the user.

## 2. Agent Prompt Architecture

The system uses a **Dynamic Prompt Builder** (`dynamic-agent-prompt-builder.ts`) rather than static strings.

### Sisyphus (The Orchestrator)
Sisyphus's prompt is assembled at runtime from 5 layers:
1.  **Core Persona**: `<Role>` definition ("You are Sisyphus...").
2.  **Behavioral Rules**: `<Behavior_Instructions>` (Phase 0-3 workflow).
3.  **Dynamic Context**:
    -   **Tools**: Table of available tools (sorted by cost).
    -   **Agents**: List of available specialists (`AvailableAgent[]`).
    -   **Skills**: Active skills (e.g., `playwright` instructions).
4.  **Orchestration Logic**: `<Oracle_Usage>` and `<Delegation_Table>`.
5.  **Environment**: `<omo-env>` (Current time, locale).

**Key Innovation**:
-   **Metadata-Driven**: Agents export `PROMPT_METADATA`. Sisyphus reads this to know *when* to delegate to them.
-   **Cost-Aware**: Prompts explicitly mention "EXPENSIVE" vs "CHEAP" agents to guide Sisyphus's choices.

### Oracle (The Advisor)
-   **Static Prompt**: `ORACLE_SYSTEM_PROMPT`.
-   **Role**: Pure reasoning. "You cannot write code. You are a brain in a jar."
-   **Constraint**: Tool access is strictly limited (no `write`, `edit`).

## 3. Tooling Ecosystem

### Built-in vs. External
-   **Built-in**: `bash`, `read`, `write` (Standard).
-   **External**: `delegate_task` (The Power Tool).
    -   **Category-Based**: `delegate_task(category="frontend")` spawns a "Sisyphus-Junior" with frontend-specific prompting.
    -   **Direct**: `delegate_task(subagent_type="oracle")` calls a specific agent.

### The "Subagent" Concept
When `delegate_task` is called:
1.  A **New Session** is created (isolated context).
2.  The **Subagent** is initialized with a specific prompt.
3.  The **Parent Session** waits (synchronously) or continues (background).
4.  **Result**: The subagent's final message is returned as the tool output to the parent.

## 4. Key Design Patterns

### The "Boulder" (State Persistence)
-   **Problem**: LLM context is transient. Long tasks get forgotten.
-   **Solution**: `.sisyphus/boulder.json` + `plans/*.md`.
-   **Mechanism**: Atlas hook *forces* Sisyphus to read/update the plan file after every task. The plan file *is* the long-term memory.

### The "Ralph Loop" (Iterative Work)
-   **Concept**: "Do X until condition Y is met".
-   **Implementation**: A dedicated hook that re-injects the prompt "Is the task done? If not, continue" until the agent signals completion or max iterations reached.
