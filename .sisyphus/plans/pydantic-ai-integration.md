# Plan: Xeno Agent Implementation (PydanticAI + AgentPool)

## Context

### Original Request
Implement the `xeno-agent` system architecture (RFC 001) using `pydantic-ai` as the core engine and `agentpool` components for infrastructure.

### Critical Revisions (Momus Verified)
- **Deep Integration**: Inherit `BaseAgent`. Implement ALL 9 abstract methods.
- **Custom Runtime**: `uv run xeno-agent serve` using `packages/xeno-agent/src/xeno_agent/main.py`.
- **Paths**: All paths explicit from repo root (`packages/xeno-agent/...`).
- **Protocol Validation**: Use `acp.agent.implementations.testing.TestAgent` (verified existing class) or generic functional tests if imports fail.
- **RFC Reproduction**: `xeno_config.yaml` recreates RFC 001 roles.

---

## Work Objectives

### Core Objective
Build a fully functional Xeno Agent system that runs alongside standard AgentPool agents, served via a custom ACP-compatible CLI, validated by rigorous tests.

### Concrete Deliverables
1.  `packages/xeno-agent/src/xeno_agent/agentpool/core/config.py`: Custom config loader.
2.  `packages/xeno-agent/src/xeno_agent/agentpool/tools/routing.py`: Routing tools.
3.  `packages/xeno-agent/src/xeno_agent/agentpool/agent.py`: `XenoAgent` class (BaseAgent).
4.  `packages/xeno-agent/src/xeno_agent/main.py`: Custom Entry Point.
5.  `packages/xeno-agent/config/xeno_config.yaml`: Recreated configuration.

### Definition of Done
- [ ] `XenoAgent` implements all 9 abstract methods of `BaseAgent`.
- [ ] `pytest` passes with 100% coverage of new code.
- [ ] `uv run xeno-agent serve` starts successfully.
- [ ] `xeno_config.yaml` contains all 4 roles (Q&A, Fault, Equipment, Material).

---

## Task Flow

```
1. Config/Deps (TDD) → 2. Config Recreation → 3. Routing Tools (TDD) → 4. XenoAgent Core (TDD) → 5. Entry Point & Integration
```

---

## TODOs

- [x] 1. Define Xeno Configuration & Deps (TDD)
    **What to do**:
    1.  Create `packages/xeno-agent/tests/agentpool/core/test_config.py`.
    2.  Implement `packages/xeno-agent/src/xeno_agent/agentpool/core/config.py`.
    3.  Implement `packages/xeno-agent/src/xeno_agent/agentpool/core/deps.py`.
    4.  Verify: Tests pass.

- [x] 2. Recreate xeno_config.yaml (from RFC Text)
    **What to do**:
    1.  Analyze `packages/xeno-agent/docs/rfc/001_agent_system_design/001_agent_system_architecture.md`.
    2.  Create `packages/xeno-agent/config/xeno_config.yaml`.
    3.  Define Roles & Capabilities.
    4.  Verify: Config validates against schema.

- [x] 3. Implement Routing Tools (TDD)
    **What to do**:
    1.  Create `packages/xeno-agent/tests/agentpool/tools/test_routing.py`.
    2.  Implement `packages/xeno-agent/src/xeno_agent/agentpool/tools/routing.py`.
    3.  Verify: Tests pass.

- [ ] 4. Implement XenoAgent (TDD - ALL 9 Abstract Methods)
    **What to do**:
    1.  Create `packages/xeno-agent/tests/agentpool/test_agent.py`.
    2.  Implement `packages/xeno-agent/src/xeno_agent/agentpool/agent.py`:
        - `_stream_events`: Core logic (PydanticAI).
        - `list_sessions`: Delegate to `self.agent_pool`.
        - `load_session`: Delegate to `self.agent_pool`.
        - `model_name`: Return string from config.
        - `get_available_models`: Return static list.
        - `_interrupt`: No-op.
        - `get_modes`: Return routing modes.
        - `_set_mode`: No-op.
        - `set_model`: Implement (update internal state).
    3.  Verify: Tests pass.

- [ ] 5. Implement Custom Entry Point & Fix Config
    **What to do**:
    1.  Update `packages/xeno-agent/pyproject.toml`: Set `[project.scripts] xeno-agent = "xeno_agent.main:main"`.
    2.  Create `packages/xeno-agent/tests/integration/test_server.py`.
    3.  Implement `packages/xeno-agent/src/xeno_agent/main.py`.
    4.  Verify: Integration tests pass.

---

## Commit Strategy
| After Task | Message | Files |
|------------|---------|-------|
| 1 | feat(config): add xeno config models (TDD) | packages/xeno-agent/src/xeno_agent/agentpool/core/ |
| 2 | feat(config): recreate xeno_config.yaml from RFC | packages/xeno-agent/config/xeno_config.yaml |
| 3 | feat(tools): implement routing tools (TDD) | packages/xeno-agent/src/xeno_agent/agentpool/tools/ |
| 4 | feat(agent): implement XenoAgent with BaseAgent interface (TDD) | packages/xeno-agent/src/xeno_agent/agentpool/agent.py |
| 5 | feat(server): implement custom ACP server and fix entry point (TDD) | packages/xeno-agent/src/xeno_agent/main.py, packages/xeno-agent/pyproject.toml |
