# Plan: Xeno-Agent Refactoring (Target: phil65/agentpool)

## Context

### Original Request
Refactor `xeno-agent` to use the `phil65/agentpool` library, replacing the custom factory/runtime implementation while preserving PydanticAI-based agent logic.

### Interview Summary
**Key Decisions**:
- **Strategy**: "Wrapper First" migration. Wrap existing logic in `agentpool` nodes first, then migrate internals incrementally.
- **Dependency**: Add `phil65/agentpool` as a core dependency.
- **Safety**: Preserve `TraceID`, recursion limits, and cycle detection.
- **IDE Integration**: Maintain compatibility with ACP events (`AgentSwitchEvent`) via an adapter.

**Metis Review (Guardrails)**:
- **Risk**: Losing custom prompt composition (4-layer). -> **Mitigation**: Implement `XenoPromptBuilder` compatible with `agentpool`.
- **Risk**: Breaking IDE visualization. -> **Mitigation**: Create `ACPEventAdapter` to map `agentpool` events to `xeno-agent` schemas.
- **Risk**: Infinite loops. -> **Mitigation**: Port `TraceID` logic to `MessageNode` wrapper.

---

## Work Objectives

### Core Objective
Replace the custom `AgentFactory` and `LocalAgentRuntime` with `agentpool`'s `AgentPool` and `MessageNode` architecture, while ensuring zero regression in agent capabilities and IDE integration.

### Concrete Deliverables
- `packages/xeno-agent/src/xeno_agent/agentpool/`: New module for integration.
- `packages/xeno-agent/scripts/migrate_to_agentpool.py`: Tool to convert YAMLs.
- `packages/xeno-agent/tests/test_agentpool_integration.py`: Verification suite.
- Updated `packages/xeno-agent/pyproject.toml` with `agentpool` dependency.

### Definition of Done
- [ ] `agentpool` dependency installed.
- [ ] Existing agents run via `agentpool` runtime.
- [ ] Delegation works with cycle detection.
- [ ] ACP events are emitted correctly for IDE.
- [ ] All tests pass (TDD).

### Must Have
- **Cycle Detection**: Max recursion depth = 5.
- **Event Compatibility**: `AgentSwitchEvent`, `ToolStartEvent` must be emitted.
- **Config Support**: Load existing flow/agent YAML logic.

### Must NOT Have
- **Logic Rewrites**: Do not rewrite the *internal* logic of agents (prompts, tools) yet. Just wrap them.

---

## Verification Strategy

### Test Decision
- **Infrastructure**: Existing `pytest`.
- **Approach**: TDD (Red-Green-Refactor).

### TDD Workflow
1.  **RED**: Write test case in `packages/xeno-agent/tests/test_agentpool_integration.py` asserting `agentpool` can load a mock Xeno agent.
2.  **GREEN**: Implement `XenoAgentNode` wrapper.
3.  **REFACTOR**: Optimize the wrapper.

### Manual Verification
- **ACP Integration**:
    - Run `xeno-agent` with ACP enabled.
    - Connect from VS Code / Zed (if applicable).
    - Verify "Switch Agent" notifications appear.

---

## Task Flow

```
1. Setup & Dep (TDD) → 2. Config Migration → 3. XenoNode Wrapper → 4. Runtime & Interfaces → 5. Cleanup
```

## Parallelization

| Group | Tasks | Reason |
|-------|-------|--------|
| A | 2, 3 | Config script and Node wrapper are independent initially |

---

## TODOs

- [x] 1. Add `agentpool` dependency and setup test scaffolding
    - **What to do**:
        - Add `agentpool` to `packages/xeno-agent/pyproject.toml`.
        - Create `packages/xeno-agent/tests/test_agentpool_integration.py`.
        - Write failing test: `test_agentpool_import` and `test_node_creation`.
    - **Acceptance Criteria**:
        - [ ] `uv pip install -e .` succeeds.
        - [ ] `pytest packages/xeno-agent/tests/test_agentpool_integration.py` passes (after impl).

- [x] 2. Implement `XenoAgentNode` Wrapper (The Bridge)
    - **What to do**:
        - Create `packages/xeno-agent/src/xeno_agent/agentpool/node.py`.
        - Implement `class XenoAgentNode(MessageNode)`:
            - Initialize with `AgentFactory` (preserving prompt logic).
            - Implement `run()` method calling `pydantic_ai_agent.run()`.
            - **CRITICAL**: Inject `TraceID` and check recursion limit here.
    - **References**:
        - `packages/xeno-agent/src/xeno_agent/pydantic_ai/runtime.py:105-148` (Safety Logic).
        - `agentpool/agents/base.py` (MessageNode interface - strictly follow library).
    - **Acceptance Criteria**:
        - [ ] Test `XenoAgentNode` can execute a simple prompt.
        - [ ] Test recursion limit throws error at depth 6.

- [ ] 3. Implement Event Adapter for ACP
    - **What to do**:
        - Create `packages/xeno-agent/src/xeno_agent/agentpool/events.py`.
        - Listen to `agentpool` events (via callback or subclassing).
        - Transform them into `AgentSwitchEvent` / `ToolStartEvent`.
        - Re-emit using `xeno-agent`'s event bus (if exists) or print to stdout (if that's how ACP reads).
    - **References**:
        - `packages/xeno-agent/src/xeno_agent/pydantic_ai/tool_manager.py` (Event emission usage).
        - `packages/xeno-agent/src/xeno_agent/pydantic_ai/events.py` (Event definitions).
    - **Acceptance Criteria**:
        - [ ] Test: `XenoAgentNode` run emits `AgentSwitchEvent`.

- [ ] 4. Create Config Migration Script
    - **What to do**:
        - Create `packages/xeno-agent/scripts/migrate_to_agentpool.py`.
        - Logic: Read `packages/xeno-agent/config/agents/*.yaml` + `packages/xeno-agent/config/flows/*.yaml`.
        - Output: `packages/xeno-agent/config/agentpool_config.yaml` (Unified structure).
        - Map `skills` to `tools`.
    - **Acceptance Criteria**:
        - [ ] Script runs without error.
        - [ ] Output YAML passes `agentpool` schema validation.

- [ ] 5. Update Entry Point (New CLI)
    - **What to do**:
        - Create `packages/xeno-agent/src/xeno_agent/agentpool/main.py` (New CLI implementation using `agentpool`).
        - Update `packages/xeno-agent/src/xeno_agent/main.py` (the shim) to import `main` from the new `agentpool/main.py`.
        - Switch runtime: Initialize `agentpool.AgentPool` with `agentpool_config.yaml`.
    - **Acceptance Criteria**:
        - [ ] `python -m xeno_agent.main` starts successfully using the new runtime.
        - [ ] Can interact with agent via CLI/ACP.

- [ ] 6. Cleanup & Deprecation
    - **What to do**:
        - Mark `AgentFactory` and `LocalAgentRuntime` as deprecated.
        - Remove unused code paths (if safe).
    - **Acceptance Criteria**:
        - [ ] Codebase clean, no dead imports.

---

## Success Criteria
- [ ] `pytest` suite passes with new tests.
- [ ] Agent behavior (delegation, tools) remains identical.
- [ ] Safety limits (recursion) are enforced.
