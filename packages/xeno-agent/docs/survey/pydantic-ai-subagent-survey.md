# Pydantic AI Subagent & Delegation Survey

## Executive Summary

Pydantic AI handles subagents and delegation primarily through **tool usage**. There is no special "subagent" primitive; instead, an agent delegates to another by calling the second agent's `run` method within a tool definition. This design keeps agents stateless and composable but implies that subagent execution is typically blocking from the parent's perspective.

## 1. Invocation Mechanism

Subagents are invoked as **tools**. The parent agent registers a tool function (sync or async) that instantiates or references another agent and calls its `run` method.

### Pattern: Tool-based Delegation

```python
from pydantic_ai import Agent, RunContext

# The "child" agent
sub_agent = Agent('openai:gpt-4o')

# The "parent" agent
parent_agent = Agent('openai:gpt-4o')

@parent_agent.tool
async def call_expert(ctx: RunContext[None], query: str) -> str:
    # 1. Parent invokes sub-agent inside a tool
    # 2. explicit passing of usage/deps if needed
    result = await sub_agent.run(query, usage=ctx.usage) 
    
    # 3. Return final result to parent
    return result.output
```

## 2. Event Streaming

**Finding**: There is **no built-in mechanism** to stream intermediate events (like token deltas or internal tool calls) from a subagent back to the parent agent's stream *during* execution.

- The `call_expert` tool above is a standard async function. The parent awaits its completion.
- The parent agent emits a `ToolCall` event when it starts the tool, and a `ToolReturn` event when the subagent finishes.
- All internal steps of the subagent (thoughts, retries, its own tool calls) are **hidden** from the parent's event stream unless manually captured and returned as part of the tool output (which would be a monolithic return value, not a stream).

### Implication for AgentPool
If AgentPool requires real-time streaming of subagent activities (e.g., seeing the subagent "think" in the UI), Pydantic AI's default pattern is insufficient. A custom solution would be needed, such as passing a callback to the subagent or using a shared event bus.

## 3. Session & Context Management

Pydantic AI agents are designed to be **stateless**.

- **Session State**: Managed explicitly by passing `message_history` to `agent.run()`.
- **Delegation Context**: When delegating, the parent must explicitly pass context to the child if shared state is desired.
    - **Usage Tracking**: `ctx.usage` from the parent `RunContext` can be passed to `sub_agent.run(..., usage=ctx.usage)` to aggregate token counts.
    - **Dependencies**: `deps` can be passed explicitly. The parent and child can share the same dependency object or use different ones.

```python
@parent_agent.tool
async def delegate(ctx: RunContext[MyDeps], query: str) -> str:
    # Explicitly sharing dependencies and usage
    result = await sub_agent.run(
        query, 
        deps=ctx.deps,      # Share deps
        usage=ctx.usage     # Share usage accounting
    )
    return result.output
```

## 4. Built-in Delegation Patterns

Pydantic AI documents three main patterns:

1.  **Agent Delegation (Tool-based)**:
    - Described above.
    - Best for: "I need an expert to answer this specific sub-question."
    - Control flow: Parent -> Child -> Parent.

2.  **Programmatic Hand-off**:
    - Linear execution in python code.
    - `result1 = await agent1.run(...)` -> logic -> `result2 = await agent2.run(..., message_history=result1.messages)`.
    - Best for: Phased workflows (e.g., Triage -> Research -> Answer).

3.  **Graph-based Control Flow (`pydantic-graph`)**:
    - For complex, non-linear flows (state machines).
    - Agents are nodes in a graph.
    - Transitions are defined by return types.
    - Allows for loops and conditional branching beyond simple tool calls.

## Comparison with AgentPool

| Feature | Pydantic AI | AgentPool (Goal) |
| :--- | :--- | :--- |
| **Invocation** | Implicit via Tools | Explicit `SubAgent` capability |
| **Streaming** | Blocking (Parent waits for Child) | Real-time event bubbling (Child events visible to Parent) |
| **State** | Explicit pass-through | Managed/Implicit (via Session) |
| **Visibility** | Opaque execution | Transparent/Observable |

## Recommendations for AgentPool

To build a robust subagent system inspired by (but improving on) Pydantic AI:

1.  **Formalize Subagent Tools**: Instead of ad-hoc functions, create a specialized `SubAgentTool` that knows how to hook into the subagent's event stream.
2.  **Event Bubbling**: Implement a mechanism to subscribe to the subagent's stream and re-emit relevant events (e.g., "Subagent thinking", "Subagent tool use") to the parent's stream, wrapping them so the UI knows they are nested.
3.  **Shared Context Object**: Similar to `RunContext`, but ensuring it carries the "Session ID" and "Parent Task ID" automatically to maintain traceability (tracing is supported in Pydantic AI via Logfire/OpenTelemetry, which is a good model to follow).
