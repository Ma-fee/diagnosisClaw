# Learnings - Pydantic AI Integration Exploration

## BaseAgent Definition

**Location**: `packages/agentpool/src/agentpool/agents/base_agent.py`

### 9 Abstract Methods
BaseAgent defines the following abstract methods that XenoAgent must implement:

1. **`model_name`** (property) → `str | None`
   - Get the model name used by this agent.

2. **`set_model(model: str)`** (async)
   - Set the model for this agent.
   - Parameter: `model` - New model identifier to use.

3. **`_stream_events(...)`** (async, AsyncIterator)
   - Agent-specific streaming implementation.
   - Yields `RichAgentStreamEvent[TResult]` during execution.
   - Core method that each agent type must implement for their streaming logic.

4. **`_interrupt()`** (async)
   - Subclass-specific interrupt implementation.
   - Called when agent is interrupted.

5. **`get_available_models()`** (async) → `list[ModelInfo] | None`
   - Get available models for this agent.
   - Returns list of tokonomics.ModelInfo or None if not supported.

6. **`get_modes()`** (async) → `list[ModeCategory]`
   - Get available mode categories for this agent.
   - Mode categories represent groups of mutually exclusive modes (permissions, models, behavior presets).

7. **`_set_mode(mode_id: str, category_id: str)`** (async)
   - Agent-specific mode switching implementation.
   - Core method for changing agent behavior modes.

8. **`list_sessions(cwd, limit)`** (async) → `list[SessionData]`
   - List available sessions for this agent.
   - Returns session IDs, working directories, titles, and timestamps.

9. **`load_session(session_id: str)`** (async) → `SessionData | None`
   - Load and restore a session by ID.
   - Restores conversation history for specified session.

### BaseAgent Architecture
- Inherits from `MessageNode[TDeps, TResult]`
- Provides shared infrastructure:
  - `tools`: ToolManager for tool registration/execution
  - `conversation`: MessageHistory for conversation state
  - `event_handler`: MultiEventHandler for event distribution
  - `_event_queue`: Queue for streaming events
  - `_input_provider`: Provider for user input/confirmations
  - `env`: ExecutionEnvironment for running code/commands
  - `context property`: Returns NodeContext for agent

### Key Signals
- `run_failed`: Emitted when agent execution fails
- `state_updated`: Emitted when state changes (modes, model, commands)
- `interrupted`: Emitted when agent is interrupted
- `agent_reset`: Emitted when agent is reset

## Configuration Patterns

### Pattern 1: agentpool_config (Pydantic Models)
**Location**: `packages/agentpool/src/agentpool_config/`

- **Design Philosophy**: Separated from core `agentpool` package to avoid circular imports
- All config models inherit from `pydantic.BaseModel` or `schemez.Schema`
- Uses `Field()` for rich metadata (examples, titles, descriptions)
- Example classes: `NodeConfig`, `BaseAgentConfig`, `SyncConfig`

**Key Characteristics**:
- Type-safe with Pydantic validation
- Rich field metadata for documentation generation
- Support for environment variable substitution
- Jinja2 templating in prompts
- Discriminated unions for multi-type configurations

### Pattern 2: Config Loader
**Location**: `packages/agentpool/src/agentpool_config/loaders.py`

- Loads YAML configs and converts to Pydantic models
- Supports inheritance via `INHERIT` field
- Uses `AgentsManifest` as root config model
- Key sections: agents, teams, responses, mcp_servers, storage, observability

### Pattern 3: Separate config.py in packages
Examples found:
- `packages/agentpool/src/agentpool_sync/config.py` - Simple Pydantic models
- `packages/agentpool/src/agentpool_server/opencode_server/models/config.py` - OpenCode-specific config

**Pattern**:
```python
from pydantic import BaseModel, Field

class SomeConfig(BaseModel):
    field: str = Field(default="value", description="Description")
    optional_field: str | None = Field(default=None, title="Optional")
```

### Pattern 4: YAML-based config for agents
**XenoAgent approach** (from `packages/xeno-agent/scripts/migrate_to_agentpool.py`):
- Uses YAML files in `config/agents/` and `config/flows/`
- Simple key-value structure with fields:
  - identifier, name, role, goal, backstory, tools, skills, capabilities
- Flows define participants and delegation rules
- Migration script converts to unified `agentpool_config.yaml`

## AgentPool Component Locations

### Core Components
- **`agents/`** - Agent implementations (native, ACP, AG-UI, Claude Code)
- **`delegation/`** - AgentPool orchestration, Team coordination, message routing
- **`messaging/`** - Message processing, MessageNode abstraction, compaction
- **`tools/`** - Tool framework and implementations
- **`models/`** - Pydantic data models and configuration schemas
- **`prompts/`** - Prompt management and templating
- **`storage/`** - Interaction tracking and analytics
- **`mcp_server/`** - MCP server integration
- **`running/`** - Agent execution runtime
- **`sessions/`** - Session management
- **`hooks/`** - Event hooks system

### Config Components
- **`agentpool_config/`** - Configuration models (separated for clean imports)
  - YAML schema definitions for agents, teams, tools, MCP servers

### Server Components
- **`agentpool_server/`** - Protocol servers
  - `acp_server/` - Agent Communication Protocol server
  - `opencode_server/` - OpenCode TUI/Desktop server
  - `agui_server/` - AG-UI protocol server
  - `openai_api_server/` - OpenAI-compatible API server
  - `mcp_server/` - Model Context Protocol server

### Toolset Components
- **`agentpool_toolsets/`** - Reusable toolset implementations
  - `builtin/` - Built-in toolsets (code, debug, subagent, file_edit, workers)
  - `mcp_discovery/` - MCP server discovery with semantic search

### Storage Components
- **`agentpool_storage/`** - Storage providers
  - `sql_provider/` - SQLAlchemy-based storage
  - `zed_provider/` - Zed IDE storage integration
  - `claude_provider/` - Claude storage integration
  - `opencode_provider/` - OpenCode storage integration

## XenoAgent Context

**Current Implementation**:
- Located in `packages/xeno-agent/src/xeno_agent/`
- Multi-agent system with CrewAI framework
- Uses RFC 002 4-role collaboration model:
  - qa_assistant
  - fault_expert
  - equipment_expert
  - material_assistant
- Config loading via `XenoAgentBuilder` with YAML files
- Migration script exists to convert YAML configs to agentpool format

**Integration Path**:
XenoAgent needs to:
1. Inherit from `BaseAgent` and implement all 9 abstract methods
2. Create config models in `agentpool_config/` pattern
3. Provide YAML configuration support via loader pattern
4. Register in `AgentsManifest` union type
5. Integrate with AgentPool lifecycle management

## Key Design Patterns Observed

1. **Type Safety**: Strict type hints required, checked with mypy --strict
2. **Pydantic-First**: All config uses Pydantic models for validation
3. **Async Everywhere**: All agent methods are async
4. **Event-Driven**: Rich event system with signals for state changes
5. **Streaming-First**: Primary interface is async iterators yielding events
6. **Context Objects**: Agents use `AgentContext` for tool execution state
7. **Protocol Abstraction**: `MessageNode` provides unified agent/team interface
8. **Separation of Concerns**: Config separated from implementation to avoid circular imports

## Xeno Config Implementation Learnings

### Task 1: Define Xeno Configuration & Deps (TDD)

**Files Created**:
- `packages/xeno-agent/tests/agentpool/core/test_config.py` - 12 TDD tests
- `packages/xeno-agent/src/xeno_agent/agentpool/core/config.py` - Pydantic models
- `packages/xeno-agent/src/xeno_agent/agentpool/core/deps.py` - Dependency injection

### Pattern 1: RoleType Enum vs Literal
**Discovery**: Initial implementation used `Literal[...]` type alias, but tests expected enum attributes like `RoleType.QA_ASSISTANT`.

**Solution**: Created `str` enum that inherits both from `Enum` and `str`:
```python
class RoleType(str, Enum):
    QA_ASSISTANT = "qa_assistant"
    FAULT_EXPERT = "fault_expert"
    EQUIPMENT_EXPERT = "equipment_expert"
    MATERIAL_ASSISTANT = "material_assistant"
```

**Benefits**:
- Supports enum syntax: `RoleType.QA_ASSISTANT`
- Compatible with string literals: `type: RoleType = Field(...)`
- Type-safe with IDE autocomplete

### Pattern 2: RFC 001 Role Definitions
Implemented 4 roles exactly as specified in RFC 001:

1. **Q&A Assistant** (`qa_assistant`): Gateway/Front Desk
   - User intent recognition
   - Simple query handling
   - Routing to experts

2. **Fault Expert** (`fault_expert`): Orchestrator/Diagnostician
   - Phenomenon clarification
   - Hypothesis generation
   - Diagnostic planning
   - Coordinating other agents

3. **Equipment Expert** (`equipment_expert`): Hybrid Worker+Active
   - Device image analysis
   - Diagram analysis
   - Step-by-step user guidance

4. **Material Assistant** (`material_assistant`): Worker/Researcher
   - Document retrieval
   - Historical case search
   - Industry standard lookup

### Pattern 3: Frozen Config Models
Following AgentPool pattern with `ConfigDict(frozen=True)`:
```python
class XenoRoleConfig(Schema):
    model_config = ConfigDict(
        frozen=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "x-icon": "octicon:robot-16",
            "x-doc-title": "Xeno Role Configuration",
        },
    )
```

**Benefits**:
- Prevents accidental mutation
- Ensures thread safety
- Compatible with YAML serialization
- Rich metadata for documentation

### Pattern 4: Field Metadata
Used Pydantic `Field()` for rich metadata:
- `examples`: Provide concrete examples for UI/docs
- `title`: Human-readable field names
- `description`: Detailed field documentation
- `default`: Optional field defaults

**Example**:
```python
type: RoleType = Field(
    ...,
    examples=[RoleType.QA_ASSISTANT, RoleType.FAULT_EXPERT],
    title="Role type",
    description="The type of role this agent plays in Xeno system",
)
```

### Pattern 5: XenoConfig Helper Methods
Added utility methods for role lookup:
- `get_role(role_id: str)`: Get role by identifier
- `get_roles_by_type(role_type)`: Filter roles by type

**Use Case**: Delegation scenarios where agents need to reference other roles:
```python
deps.get_other_role("fault")  # Get Fault Expert config
deps.get_roles_by_type(RoleType.WORKER)  # Get all worker roles
```

### Pattern 6: XenoAgentDeps Dependency Injection
Created `XenoAgentDeps` following PydanticAI `RunContext` pattern:

**Core Properties**:
- `xeno_config`: Complete Xeno system configuration
- `role_config`: Current agent's role configuration
- `agent_pool`: AgentPool for inter-agent delegation
- `storage_manager`: Storage provider for interaction tracking
- `tool_manager`: Tool manager for tool registration

**Usage Pattern**:
```python
@agent.tool
async def delegate_to_material(
    research_query: str,
    ctx: RunContext[XenoAgentDeps],
) -> str:
    deps = ctx.deps
    # Access configuration
    material_config = deps.get_other_role("material")
    # Delegate through AgentPool
    result = await deps.agent_pool.get_agent("material").run(research_query)
    return result
```

**Key Design Decisions**:
1. **Optional Dependencies**: `agent_pool`, `storage_manager`, `tool_manager` are optional to support testing
2. **Async Context Manager**: Implements `__aenter__`/`__aexit__` for resource cleanup
3. **Cross-Role Access**: Methods to reference other roles support RFC 001's collaboration model
4. **TYPE_CHECKING Imports**: All external types imported in TYPE_CHECKING block to avoid circular imports
5. **Type-Safe Delegation**: `get_roles_by_type` accepts `RoleType | RoleTypeLiteral | str` for flexibility

### Pattern 7: File Corruption Recovery
**Issue**: Orchestrator accidentally corrupted `deps.py` (only 2 lines remaining)

**Fix**: Restored entire file with:
1. Complete `XenoAgentDeps` class implementation
2. Proper TYPE_CHECKING imports including `Any`
3. All properties and methods for dependency injection
4. Correct type annotations for `get_roles_by_type` method

**Learning**: Always verify file state after changes. Use `read` tool to check content before assuming corruption.

### Pattern 8: TYPE_CHECKING for Type Hints
Following AgentPool pattern for type safety:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Any, Self

    from agentpool.agents.context import AgentContext
    # ... other imports
```

**Benefits**:
- Avoids circular import errors at runtime
- Provides type hints for IDE/autocomplete
- Allows optional dependencies without runtime import overhead

**Import Groups in TYPE_CHECKING**:
- `types`: `TracebackType` for `__aexit__` signature
- `typing`: `Any, Self` for generic types
- `agentpool.*`: `AgentContext`, `AgentPool`, `StorageManager`, `ToolManager`
- Local modules: `RoleType`, `RoleTypeLiteral`, `XenoConfig`, `XenoRoleConfig`

### Pattern 7: TDD Workflow
Followed strict TDD approach:
1. Write failing tests first
2. Implement minimal code to pass
3. Run tests to verify
4. Refactor if needed

**Test Coverage Achieved**:
- 12 tests, all passing
- Tests cover all 4 role types
- Validation tests for required fields
- Immutability tests
- Enum value tests
- Dictionary parsing tests

### Key Insights from AgentPool Patterns

**Inherited from AgentPool**:
- `Schema` base class from `schemez` package (Pydantic-like)
- `ConfigDict` for model configuration
- `Field()` metadata for documentation generation
- Type hints with `TYPE_CHECKING` for circular import avoidance

**Xeno-Specific Adaptations**:
- Role-based enum matching RFC 001 exactly
- Dependency injection class for agent delegation
- Helper methods for cross-role communication

### Files Structure
```
packages/xeno-agent/
├── src/xeno_agent/agentpool/core/
│   ├── __init__.py              # Exports: RoleType, XenoConfig, XenoRoleConfig, XenoAgentDeps
│   ├── config.py                # Pydantic models for Xeno configuration
│   └── deps.py                  # Dependency injection for PydanticAI agents
└── tests/agentpool/core/
    └── test_config.py             # 12 TDD tests
```
