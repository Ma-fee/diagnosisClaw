# Issues

## Resolved: NameError: name 'XenoAgentDeps' is not defined

### Problem
When running the Xeno agent, PydanticAI inspection of tool functions in `routing.py` failed with `NameError: name 'XenoAgentDeps' is not defined`.
This was because `XenoAgentDeps` was imported inside `if TYPE_CHECKING:` block in `routing.py`, but it was used in tool function signatures like `def ask_followup(..., ctx: RunContext[XenoAgentDeps])`.
PydanticAI inspects these signatures at runtime to generate tool schemas for the LLM.

### Solution
Moved `XenoAgentDeps` import out of `TYPE_CHECKING` block in `packages/xeno-agent/src/xeno_agent/agentpool/core/routing.py`.

### Verification
- Added a `prompt` test case to `packages/xeno-agent/tests/integration/test_server.py`.
- Ran `uv run pytest packages/xeno-agent/tests/integration/test_server.py` and it passed.
- Verified that `agent.py` and `deps.py` also handle runtime types correctly.
