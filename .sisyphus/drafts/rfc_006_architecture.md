# RFC 006: Interface-Based PydanticAI Multi-Agent SDK

## 1. Summary

This RFC defines the architecture for the **PydanticAI-based Agent Framework SDK**. The goal is to provide a production-grade SDK that replicates the functionality of the RFC 001 system using a simplified, **delegation-based architecture**.

**Key Architectural Decisions:**
1.  **Pure Delegation Model**: Replaces GOTO/Stack-Machine with explicit **Task Delegation**.
2.  **Safety Guardrails**: Implements `max_recursion_depth` and **Cycle Detection** to prevent infinite loops.
3.  **Main vs Sub Agents**: User-facing vs Internal workers.
4.  **Interface-Driven Design**: Protocol-based architecture.
5.  **Static Agent Creation**: MVP focuses solely on **YAML-defined agents** (Dynamic LLM creation postponed).

---

## 2. Core Architecture

### 2.1 The Delegation Pattern (Simplified)

We rely on PydanticAI's native tool calling with strict safety controls.

```python
# Universal Delegation Tool
async def delegate_task(ctx: RunContext, target_agent: str, task: str) -> str:
    """Delegate a task to a sub-agent and await the result."""
    
    # 1. Cycle Detection & Depth Check
    current_trace = ctx.deps.trace_id
    current_depth = len(current_trace.path)
    if current_depth > MAX_DELEGATION_DEPTH:
        raise RecursionError("Max delegation depth exceeded")
    if target_agent in current_trace.path:
        raise RecursionError(f"Cycle detected: {target_agent} already in call stack")

    # 2. Check permissions
    if target_agent not in ctx.deps.config.allow_delegation_to:
        raise PermissionError(f"Delegation to {target_agent} not allowed")
    
    # 3. Load Target Agent
    agent = agent_factory.load(target_agent)
    
    # 4. Execute (Recursive Call)
    # Pass trace_id to maintain call stack history
    new_deps = ctx.deps.child(target=target_agent)
    result = await agent.run(task, deps=new_deps)
    return result.data
```

### 2.2 Interface Layer

| Interface | Description | Local Implementation | ACP Implementation |
|-----------|-------------|----------------------|-------------------|
| `AgentRuntime` | Executes agent logic | `LocalAgentRuntime` | `ACPAgentRuntime` |
| `StatePersistence` | Saves/Loads session state | `SQLitePersistence` | *(Stub)* |
| `ConfigLoader` | Loads agent definitions | `YAMLConfigLoader` | *(Stub)* |
| `SkillLoader` | Loads Anthropic-format skills | `AnthropicSkillLoader` | *(Stub)* |
| `ToolRegistry` | Manages tool allow/blocklists | `LocalToolRegistry` | *(Stub)* |

---

## 3. Agent System Design

### 3.1 Agent Definition Schema

Agents are defined in `config/agents/*.yaml`.

```yaml
# qa_assistant.yaml
identifier: "qa_assistant"
type: "main"  # or "sub"
role: "QA Assistant"
backstory: "You are the first point of contact..."
when_to_use: "General inquiries"

# Delegation Permissions
allow_delegation_to: 
  - "fault_expert"

# Tool Configuration
tools:
  mode: "allowlist"  # or "blocklist"
  builtins: 
    - "search"
  external: 
    - "github_api"

# Skill Configuration
skills:
  - "dialogue_management"  # Static
```

### 3.2 Skill System (Anthropic Format)

Skills strictly follow the **Anthropic Tool/Skill Definition** format.

**Component**: `SkillRegistry`
- **Responsibility**: Maps XML skill definitions to executable Python callables.
- **Validation**: Ensures XML parameters match Python function signatures at startup.

```xml
<tool_definition>
    <name>dialogue_management</name>
    <description>Manage conversation flow...</description>
    <parameters>...</parameters>
</tool_definition>
```

---

## 4. Implementation Roadmap (MVP)

### Phase 1: Core Interfaces & Runtime
- Implement `AgentRuntime` with `delegate_task` logic (incl. Guardrails).
- Implement `AgentFactory` (Static YAML only).
- Implement `TraceID` logic for cycle detection.

### Phase 2: Skills & Config
- Implement `AnthropicSkillLoader` and `SkillRegistry`.
- Implement `YAMLConfigLoader`.
- **Scope Cut**: Dynamic LLM Agent creation is moved to Phase 2+.

### Phase 3: Reproduction Demo
- Replicate RFC 001 scenario using Delegation Model.
- **Scenario**: 
  1. User talks to QA (Main).
  2. QA delegates to Fault Expert (Sub).
  3. Fault Expert delegates to Equipment Expert (Sub).
  4. Result bubbles back up: Equipment -> Fault -> QA -> User.

---

## 5. ACP Integration (Stage 1)

**Hybrid Approach**:
- `AgentRuntime`: Full ACP implementation (Remote Delegation).
- Registries: Stubs.

## 6. Testing Strategy

**TDD (Red-Green-Refactor)**:
1.  Test `delegate_task` recursion guardrails (Depth/Cycle).
2.  Test `allow_delegation_to` permissions.
3.  Test `SkillRegistry` binding validation.
