# Oh My OpenCode Survey: Executive Summary

## Survey Completion Report

This survey analyzes the **Oh My OpenCode** project to inform the design of the `xeno-agent` framework.

### Artifacts Generated
The following detailed reports have been created in `packages/xeno-agent/docs/survey/oh-my-opencode/`:

1.  **[01-overview.md](./01-overview.md)**
    -   **Scope**: High-level goal, architecture, and tech stack.
    -   **Key Finding**: The project is a "Plugin" that transforms a coding agent into a multi-agent orchestration system using a "Manager-Worker" model.

2.  **[02-core-abstractions.md](./02-core-abstractions.md)**
    -   **Scope**: Agents, Hooks, Tools, and Skills.
    -   **Key Finding**: Agents are defined via a **Factory Pattern** with metadata (`PROMPT_METADATA`) that drives dynamic prompt assembly. Hooks are the central middleware for all logic.

3.  **[03-orchestration.md](./03-orchestration.md)**
    -   **Scope**: Sisyphus (Manager), Atlas (Orchestrator), and Boulder State.
    -   **Key Finding**: **Atlas Hook** is the critical component. It intercepts Sisyphus's attempts to "do work" and forces delegation. It also manages long-term state (`.sisyphus/boulder.json`) to survive session context limits.

4.  **[04-advanced-features.md](./04-advanced-features.md)**
    -   **Scope**: Background Tasks, Context Management, MCP.
    -   **Key Finding**:
        -   **Context**: Aggressive pruning (`truncator`) + Smart injection (`context-injector`).
        -   **Background**: Async task manager allows parallel "Research" and "Exploration".
        -   **Resilience**: `Todo Continuation Enforcer` prevents early exits.

5.  **[05-deep-dive-agents-prompts-timeline.md](./05-deep-dive-agents-prompts-timeline.md)**
    -   **Scope**: Detailed analysis of Prompt Construction, Tool Definitions, and the T0-T5 Event Loop.
    -   **Key Finding**:
        -   **Prompts**: Not static strings. Built dynamically (`dynamic-agent-prompt-builder.ts`) based on available tools/agents/skills.
        -   **Timeline**: A strict event loop where hooks (`chat.message` -> `tool.execute.before` -> `tool.execute.after`) control the flow.
        -   **Tools**: 23+ tools, including "Delegation" tools that spawn sub-sessions.

## Recommendations for Xeno-Agent Framework

Based on this analysis, the following patterns are highly recommended for adoption:

1.  **Adopt the "Hook" Middleware Architecture**: It separates concerns (safety, context, logging) from core agent logic.
2.  **Use Dynamic Prompt Builders**: Static system prompts are insufficient for flexible agent configurations.
3.  **Implement "Orchestration Enforcement"**: Don't just ask the agent to delegate; *enforce* it via code (like the Atlas hook).
4.  **State Persistence is Critical**: Use external state (like the "Boulder" system) to manage tasks that exceed a single context window.
5.  **Parallelism via Background Agents**: Allow the main agent to "fire and forget" research tasks to increase throughput.
