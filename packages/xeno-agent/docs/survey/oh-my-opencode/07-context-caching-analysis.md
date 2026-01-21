# Oh My OpenCode Survey: Context Caching & Injection

## 1. System Prompt Optimization for Caching

Oh My OpenCode is explicitly architected to be **Prefix-Caching Friendly**.

### The Prompt Structure
The Agent System Prompt is constructed in a specific order to maximize cache hit rates (`src/agents/utils.ts` and `src/agents/dynamic-agent-prompt-builder.ts`).

1.  **Skills Content (Static-ish)**: Prepended at the very start. Stable unless config changes.
2.  **Base System Prompt (Static)**: The massive block of instructions, behavior rules, and constraints. This never changes during a session.
3.  **Dynamic Sections (Semi-Static)**:
    -   Available Tools list.
    -   Available Agents list.
    -   These change only if plugins/tools are added/removed (rare).
4.  **Environment Context (Volatile) - THE SUFFIX**:
    -   `Current Time`, `Timezone`, `Locale`.
    -   This is **appended at the very end** (`createEnvContext` in `src/agents/utils.ts`).
    -   This ensures the first 95% of the prompt remains identical byte-for-byte across requests, allowing KV-cache reuse.

**Optimization Note**: The `envContext` includes seconds-precision time (`new Date()`). While this breaks the cache for the *suffix*, it preserves the massive *prefix*.

## 2. Context Injection Strategies

The system uses a "Just-in-Time" injection strategy via **Hooks**, rather than stuffing everything into the System Prompt.

### Mechanism: `tool.execute.after`
Instead of pre-loading files, the system watches what the agent does and injects context *after* relevant actions.

1.  **Directory Agents (`src/hooks/directory-agents-injector/`)**:
    -   **Trigger**: Agent reads ANY file in a directory.
    -   **Action**: Scans up the directory tree for `AGENTS.md`.
    -   **Injection**: Appends `[Directory Context: .../AGENTS.md]` to the `read` tool output.
    -   **Caching**: Uses `sessionCaches` (Set<string>) to ensure each `AGENTS.md` is injected **only once per session**.

2.  **Rules Injection (`src/hooks/rules-injector/`)**:
    -   **Trigger**: Agent reads/writes a file.
    -   **Action**: Finds `.cursorrules` or `.windsurfrules` relevant to that file.
    -   **Injection**: Appends rule content to the tool output.
    -   **Caching**: Checks content hash to prevent duplicate injection.

### Mechanism: `session.compacted` (Recovery)
When context limits are hit and the history is summarized (compacted):
-   **Hook**: `src/hooks/compaction-context-injector/`.
-   **Action**: Re-injects a structured summary prompt (`SUMMARIZE_CONTEXT_PROMPT`).
-   **Goal**: Forces the model to explicitly list "User Requests", "Work Completed", and "MUST NOT DO" constraints in the summary, ensuring critical constraints survive the context wipe.

## 3. Caching Control

-   **Explicit Caching**: No explicit HTTP headers (e.g., `Anthropic-Beta: prompt-caching`) were found in the analyzed code. The system relies on the **natural structure** of the prompt (Static Prefix + Volatile Suffix) to leverage implicit provider caching.
-   **Deduplication**: The `ContextInjector` hooks implement aggressive deduplication (`sessionCaches`, `contentHashes`) to prevent polluting the context window with redundant information.

## 4. Design Recommendations for Xeno-Agent

1.  **Adopt the "Volatile Suffix" Pattern**: Put all time-dependent or rapidly changing instructions at the *end* of your system prompt.
2.  **Event-Driven Context**: Don't dump all context at start. Inject `README.md`, `CONTRIBUTING.md`, or `Rules` only when the agent *touches* relevant files.
3.  **Deduplicate Aggressively**: Track what you've injected. Never inject the same static context twice in a session.
4.  **Compaction Survival**: When summarizing history, explicitly prompt the model to preserve *constraints* and *goals*, not just narrative.
