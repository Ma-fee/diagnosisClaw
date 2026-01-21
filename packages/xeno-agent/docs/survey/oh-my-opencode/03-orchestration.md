# Oh My OpenCode Survey: Orchestration & Execution

## 1. The Orchestration Philosophy (Sisyphus & Atlas)

The system is built on the premise that **a single agent cannot do everything**. Instead, it uses a "Manager-Worker" model.

-   **Manager (Sisyphus)**: Responsible for understanding the user's intent, creating a plan, and delegating tasks.
-   **Orchestrator (Atlas)**: A system-level hook that enforces this behavior.

## 2. The Atlas Hook (`src/hooks/atlas/`)

Atlas is not just a passive observer; it is an active enforcer.

### Responsibilities
1.  **Delegation Enforcement**:
    -   If Sisyphus tries to `write` or `edit` files directly in a complex task, Atlas intercepts the call and warns: "You should delegate this to a specialized agent."
    -   This forces Sisyphus to use `delegate_task`.
2.  **Verification Injection**:
    -   When a subagent completes a task, Atlas intercepts the result.
    -   It appends a mandatory **Verification Checklist**:
        -   "Run lsp_diagnostics"
        -   "Run tests"
        -   "Check for regressions"
    -   Sisyphus *must* check these boxes before marking the task as done.
3.  **Plan Tracking (The "Boulder")**:
    -   Atlas maintains a persistent "Boulder State" (`.sisyphus/boulder.json`).
    -   It links the active plan (e.g., `plans/feat-auth.md`) to the current session.
    -   If the session goes idle, Atlas nudges Sisyphus: "The plan is not complete. Continue working."

## 3. The "Boulder" State System

This system ensures long-running tasks survive session context limits and interruptions.

-   **Plan Files**: Markdown files with `- [ ]` checkboxes.
-   **State**:
    ```json
    {
      "active_plan": "/abs/path/to/plan.md",
      "session_ids": ["ses_123"],
      "started_at": "2024-01-01T00:00:00Z"
    }
    ```
-   **Logic**:
    -   **Start**: User says "Refactor X". Sisyphus creates a plan. Atlas registers it as the "Boulder".
    -   **Loop**: Sisyphus picks a task -> Delegates -> Verifies -> Updates Plan.
    -   **End**: All checkboxes checked. Atlas releases the Boulder.

## 4. Execution Flow

1.  **Intent Analysis (Phase 0)**:
    -   Sisyphus analyzes the request.
    -   Is it a simple question? -> Answer directly.
    -   Is it a complex task? -> **Create a Todo List**.

2.  **Delegation (Phase 2)**:
    -   Sisyphus calls `delegate_task(agent="frontend", prompt="Implement button")`.
    -   System spawns a isolated sub-session with the `frontend` agent.
    -   Subagent works (Read -> Edit -> Verify).
    -   Subagent returns result.

3.  **Verification (Phase 3)**:
    -   Atlas intercepts the return.
    -   Sisyphus reads the verification checklist.
    -   Sisyphus runs `lsp_diagnostics` to confirm no new errors.

4.  **Completion**:
    -   Sisyphus marks the Todo as completed.
    -   Atlas updates the Boulder state.
