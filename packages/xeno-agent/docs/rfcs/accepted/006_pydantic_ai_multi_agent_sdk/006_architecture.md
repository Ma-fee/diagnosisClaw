# RFC 006: Interface-Based PydanticAI Multi-Agent SDK

## 1. Summary

This RFC defines the architecture for the **PydanticAI-based Agent Framework SDK**. The goal is to provide a production-grade SDK that replicates the functionality of the RFC 001 system using a simplified, **delegation-based architecture**.

**Key Architectural Decisions:**
1.  **Pure Delegation Model**: Replaces GOTO/Stack-Machine with explicit **Task Delegation** (Main Agents delegating to Sub Agents).
2.  **Flow-Driven Topology**: Flows (`flow.yaml`) define the entry point and allowed delegation paths, overriding static agent configs.
3.  **Prompt Composition**: System prompts are dynamically assembled from 4 layers (Identity > Flow > Delegation > Skills).
4.  **Interface-Driven Design**: Core components (Runtime, Persistence, Config, Skills, Tools) are abstract protocols with dual implementations (Python/Local vs ACP/Remote).
5.  **Safety Guardrails**: Strict recursion depth limits and cycle detection.

---

## 2. Core Architecture

### 2.1 The Delegation Pattern

We rely on PydanticAI's native recursive tool calling capabilities with strict safety controls.

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

    # 2. Check permissions (Injected by Flow Config)
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

### 2.2 Flow Configuration (`flow.yaml`)

Flows define the "Business Process" topology, overriding individual agent settings.

```yaml
# config/flows/fault_diagnosis.yaml
name: "Fault Diagnosis SOP"
description: "Standard operating procedure for hardware faults"

# Entry Point
entry_agent: "qa_assistant"

# Participants (Resource Loading Optimization)
participants:
  - "qa_assistant"
  - "fault_expert"
  - "equipment_expert"
  - "material_assistant"

# Global Context (Injected into Layer 2 of Prompt)
global_instructions: |
  You are participating in the Fault Diagnosis SOP.
  Protocol: QA -> Fault -> Equipment/Material.
  Do not deviate from this chain.

# Topology Overrides (Defines the Graph)
delegation_rules:
  qa_assistant:
    allow_delegation_to: ["fault_expert"]
  fault_expert:
    allow_delegation_to: ["equipment_expert", "material_assistant"]
  equipment_expert:
    allow_delegation_to: []  # Leaf node
```

### 2.3 Interface Layer

| Interface | Description | Local Implementation | ACP Implementation |
|-----------|-------------|----------------------|-------------------|
| `AgentRuntime` | Executes agent logic | `LocalAgentRuntime` | `ACPAgentRuntime` |
| `StatePersistence` | Saves/Loads session state | `SQLitePersistence` | *(Stub)* |
| `ConfigLoader` | Loads agent/flow definitions | `YAMLConfigLoader` | *(Stub)* |
| `SkillLoader` | Loads Anthropic-format skills | `AnthropicSkillLoader` | *(Stub)* |
| `ToolRegistry` | Manages tool allow/blocklists | `LocalToolRegistry` | *(Stub)* |
| `WorkflowLoader` | Loads Flow definitions | `YAMLWorkflowLoader` | *(Stub)* |

---

## 3. Agent System Design

### 3.1 Prompt Composition Layers

The `AgentFactory` assembles the System Prompt dynamically from 4 sources using PydanticAI's decorator pattern:

1.  **Identity Layer** (from `agent.yaml`):
    > "Role: QA Assistant. Backstory: You are the first point of contact..."
2.  **Flow Layer** (from `flow.yaml`):
    > "Context: Fault Diagnosis SOP. Protocol: QA -> Fault..."
3.  **Delegation Layer** (computed from `delegation_rules`):
    > "You can delegate to: Fault Expert (for root cause analysis)..."
4.  **Skill Layer** (from `skills/*.xml`):
    > "<tool_definition>...</tool_definition>"

### 3.2 Agent Definition Schema

Agents are defined in `config/agents/*.yaml`.

```yaml
# qa_assistant.yaml
identifier: "qa_assistant"
type: "main"  # or "sub"
role: "QA Assistant"
backstory: "You are the first point of contact..."
when_to_use: "General inquiries"

# Delegation Permissions (Default, overridden by Flow)
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

### 3.3 Skill System (Anthropic Format)

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
- Implement `TraceID` logic for cycle detection.

### Phase 2: Agent Factory & Config
- Implement `AgentConfig` and `FlowConfig` models.
- Implement `PromptBuilder` (4-layer strategy).
- Implement `AgentFactory` that merges Agent+Flow configs.

### Phase 3: Skills & Registry
- Implement `AnthropicSkillLoader` and `SkillRegistry`.

### Phase 4: Reproduction Demo
- Port RFC 001 roles to `agent.yaml` + `flow.yaml`.
- Run reproduction script.

---

## 5. ACP Integration (Stage 1)

**Hybrid Approach**:
- `AgentRuntime`: Full ACP implementation (Remote Delegation).
- Registries: Stubs.

## 6. Testing Strategy

**TDD (Red-Green-Refactor)**:
1.  Test `delegate_task` recursion guardrails (Depth/Cycle).
2.  Test Flow topology enforcement (can A call C if Flow says no?).
3.  Test Prompt layering correctness.
