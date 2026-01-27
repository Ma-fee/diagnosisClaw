<file>
00815| 
00816| ## Task 4: XenoAgent Implementation (TDD)
00817| 
00818| - Implemented `XenoAgent` inheriting from `BaseAgent`.
00819| - Implemented all 9 abstract methods:
00820|     - `model_name`: delegates to current role config.
00821|     - `set_model`: stubbed (immutable config limitation, but runtime state updated).
00822|     - `_stream_events`: uses `PydanticAgent` with `agent.iter` for streaming.
00823|     - `_interrupt`: cancels current stream task.
00824|     - `get_available_models`: stubbed (returns None).
00825|     - `get_modes`: exposes roles as "mode" category.
00826|     - `_set_mode`: switches active role ID.
00827|     - `list_sessions`: delegates to `agent_pool.sessions.store`.
00828|     - `load_session`: delegates to `agent_pool.sessions.store`.
00829| - Implemented `_process_node_stream` to handle PydanticAI streaming events (`ModelRequestNode`, `CallToolsNode`) and convert them to `RichAgentStreamEvent`.
00830| - Registered routing tools (`ask_followup`, `switch_mode`, etc.) with `PydanticAgent`.
00831| - **Learnings**:
00832|     - `PydanticAgent` initialization requires precise type alignment or `type: ignore` due to complex overloads and generics.
00833|     - `BaseAgent.AGENT_TYPE` is a restrictive Literal in the base class, requiring `type: ignore` when extending with a new type like "xeno" without modifying the base.
00834|     - `SessionData` requires `agent_name` during initialization.
00835|     - Testing async methods requires `@pytest.mark.asyncio`.
00836|     - `ModeCategory` uses `available_modes` attribute, not `modes`.
00837| 
00838| ## Task 5: ACP Server Implementation
00839| - **ACP Protocol**: The `Agent` protocol requires implementing `initialize`, `new_session`, `load_session`, `list_sessions`, `prompt`, `cancel`, `fork_session`, `resume_session`, `authenticate`, `set_session_mode`, `set_session_model`, `set_session_config_option`, `ext_method`, `ext_notification`.
00840| - **Typer & Subcommands**: When using `typer.Typer()` with a single command, Typer treats it as the main command by default. Adding a second command (e.g., `version`) forces subcommand mode, which is often safer for preserving explicit `cli command` syntax.
00841| - **ACP Serve**: Using `acp.serve` simplifies server implementation compared to manually managing `AgentSideConnection` and stdio streams.
00842| - **Initialization Response**: The `InitializeResponse.create` helper puts agent name into `agentInfo`. Tests should check `result["agentInfo"]["name"]` rather than top-level `name`.
</file>## Final Verification - 2026-01-26
- All 10 tests in packages/xeno-agent pass.
- XenoAgent correctly implements all 9 abstract methods.
- xeno-agent CLI entry point verified.
- Integration tests confirm ACP server functionality.

## Runtime Type Availability for PydanticAI
- **Problem**: PydanticAI inspects tool function signatures at runtime to generate schemas.
- **Issue**: Importing dependency types (like `XenoAgentDeps`) only inside `if TYPE_CHECKING:` causes `NameError` during inspection.
- **Solution**: Ensure types used in tool signatures (even if just for `RunContext[T]`) are imported at runtime.
