# Learnings - Xeno Agent Pool Refactor

## Task 1: Setup Test Scaffolding

### Completed Items
- ✅ `agentpool` dependency confirmed in `packages/xeno-agent/pyproject.toml` (line 24)
- ✅ Test file `packages/xeno-agent/tests/test_agentpool_integration.py` exists with two tests
- ✅ Tests verified to run: `uv run pytest packages/xeno-agent/tests/test_agentpool_integration.py`

### Test Results
- `test_agentpool_import`: **PASSED** - Confirms agentpool can be imported
- `test_node_creation`: **FAILED** - As expected in TDD RED phase

### Key Findings
1. **agentpool version 0.0.1 is a minimal stub** - The package currently only contains version information and no actual implementation yet.
2. **MessageNode does not exist** in the current version of agentpool
3. **TDD approach validated** - The failing test correctly identifies what needs to be implemented
4. **Test infrastructure is working** - pytest setup is correct and tests execute properly

### Next Steps
The failing test `test_node_creation` should be updated once the actual `MessageNode` class (or equivalent) is available in the agentpool library. For now, the RED phase of TDD is complete - we have identified what needs to be built.

---

## Task 2: Implement XenoMessageNode Wrapper

### Completed Items
- ✅ Created `packages/xeno-agent/src/xeno_agent/pydantic_ai/pool.py` with `MessageNode` base class
- ✅ Created `XenoMessageNode` class that inherits from `MessageNode`
- ✅ Implemented mapping from `pydantic_ai.messages.ModelMessage` to `XenoMessageNode` attributes
- ✅ All tests pass in `test_agentpool_integration.py`

### Test Results (8/8 PASSED)
- `test_agentpool_import`: ✅ PASSED
- `test_message_node_base`: ✅ PASSED - Base MessageNode class works correctly
- `test_node_creation`: ✅ PASSED - Can create MessageNode from text
- `test_xeno_message_node_from_model_response`: ✅ PASSED - Wraps ModelResponse correctly
- `test_xeno_message_node_with_tool_calls`: ✅ PASSED - Handles ToolCallPart extraction
- `test_xeno_message_node_with_tool_returns`: ✅ PASSED - Handles ToolReturnPart extraction
- `test_xeno_message_node_to_dict`: ✅ PASSED - Serialization works
- `test_xeno_message_node_inheritance`: ✅ PASSED - XenoMessageNode is subclass of MessageNode

### Key Findings
1. **Local MessageNode required** - Since agentpool is a stub, created local `MessageNode` base class in `pool.py` with standard fields: `id`, `parent_id`, `content`, `role`, `metadata`, `parts`, `tool_calls`, `tool_returns`

2. **XenoMessageNode factory pattern** - Implemented two factory methods:
   - `from_message(ModelResponse, ...)` - Wraps pydantic_ai ModelResponse
   - `from_text(text, ...)` - Creates simple text-based node

3. **Part extraction logic** - Successfully maps pydantic_ai parts to XenoMessageNode:
   - `TextPart` → `content` string
   - `ThinkingPart` → `<thinking>...</thinking>` tags in content
   - `ToolCallPart` → `tool_calls` list with `tool_call_id`, `tool_name`, `args`
   - `ToolReturnPart` → `tool_returns` list with `tool_call_id`, `content`

4. **ToolReturnPart requires tool_name** - Discovered that `ToolReturnPart.__init__()` requires a `tool_name` argument, not just `tool_call_id` and `content`

5. **None handling for timestamp** - `message.timestamp` can be `None`, so need to check `if message.timestamp is not None` rather than just `hasattr`

6. **Usage metadata handling** - Need to check `if message.usage is not None` before accessing `message.usage.request_tokens` etc.

7. **Inheritance verification** - `XenoMessageNode` correctly inherits from `MessageNode`, allowing `isinstance(node, MessageNode)` checks

### Implementation Details

#### MessageNode Base Class
```python
@dataclass
class MessageNode:
    id: str
    parent_id: str | None
    content: str
    role: str
    metadata: dict[str, Any]
    parts: list[ModelResponsePart]
    tool_calls: list[dict[str, Any]]
    tool_returns: list[dict[str, Any]]
```

#### XenoMessageNode Key Methods
- `from_message(ModelResponse, parent_id, role)` - Factory for ModelResponse wrapping
- `from_text(text, parent_id, role)` - Factory for simple text nodes
- `get_text_content()` - Returns content string
- `has_tool_calls()` - Returns True if tool_calls non-empty
- `get_tool_call_count()` - Returns number of tool calls
- `to_dict()` - Serializes to dictionary

### Code Structure
- `packages/xeno-agent/src/xeno_agent/pydantic_ai/pool.py` - Main implementation file containing both `MessageNode` and `XenoMessageNode`
- `packages/xeno-agent/tests/test_agentpool_integration.py` - Updated with comprehensive test suite

### Next Steps
Task 2 complete. The wrapper is ready for integration with agentpool runtime once the library provides actual MessageNode implementation.


---

## Task 2: Implement XenoAgentNode Wrapper (The Bridge)

### Completed Items
- ✅ Created `packages/xeno-agent/src/xeno_agent/agentpool/` directory structure
- ✅ Moved `MessageNode` and `XenoMessageNode` from `pydantic_ai/pool.py` to `agentpool/node.py`
- ✅ Deleted `pydantic_ai/pool.py` (noted as completed - file ignored by git)
- ✅ Implemented `XenoAgentNode` class with `run()` method
- ✅ `XenoAgentNode.run()` integrates `AgentFactory`, `TraceID`, and recursion limit
- ✅ Updated `test_agentpool_integration.py` with comprehensive XenoAgentNode tests
- ✅ All 12 tests PASS

### Test Results (12/12 PASSED)
- `test_agentpool_import`: ✅ PASSED - agentpool package available
- `test_message_node_base`: ✅ PASSED - Base MessageNode class works
- `test_node_creation`: ✅ PASSED - XenoMessageNode.from_text() works
- `test_xeno_message_node_from_model_response`: ✅ PASSED - Wraps ModelResponse correctly
- `test_xeno_message_node_with_tool_calls`: ✅ PASSED - Handles ToolCallPart extraction
- `test_xeno_message_node_with_tool_returns`: ✅ PASSED - Handles ToolReturnPart extraction
- `test_xeno_message_node_to_dict`: ✅ PASSED - Serialization works
- `test_xeno_message_node_inheritance`: ✅ PASSED - XenoMessageNode is subclass of MessageNode
- `test_xeno_agent_node_initialization`: ✅ PASSED - XenoAgentNode initialization works
- `test_xeno_agent_node_recursion_limit`: ✅ PASSED - Recursion depth check works
- `test_xeno_agent_node_run_without_api`: ✅ PASSED - RuntimeDeps constructed correctly (mocked)
- `test_xeno_agent_node_create_child`: ✅ PASSED - Child node creation works

### Key Findings

1. **Recursion limit check BEFORE agent creation** - Important to validate depth before attempting to create agent (which requires valid model)

2. **Parent trace reconstruction issue** - When `parent_trace_id` is passed, we cannot reconstruct the full trace path from just the ID. Added `parent_depth` parameter to `run()` method to properly track depth.

3. **Trace depth calculation** - `current_depth = len(trace.path) + parent_depth` ensures depth is correctly calculated across delegations.

4. **Mocking async methods** - Used `AsyncMock` from `unittest.mock` for mocking `AgentFactory.create()` and `Agent.run()` methods.

5. **Model validation** - Tests that don't require actual LLM API calls use mocks to avoid model availability issues (e.g., `gpt-4o-mini` not available in local environment).

### XenoAgentNode Implementation Details

#### Class Structure
```python
class XenoAgentNode:
    """Bridge wrapper that executes pydantic_ai agents via agentpool interface."""

    def __init__(self, agent_id, factory, flow_config, tool_manager, model=None):
        self.agent_id = agent_id
        self.factory = factory
        self.flow_config = flow_config
        self.tool_manager = tool_manager
        self.model = model
```

#### run() Method Flow
1. **Trace creation** - Creates new trace or child trace from `parent_trace_id`
2. **Recursion check** - Validates `current_depth <= MAX_DELEGATION_DEPTH (5)`
3. **Agent creation** - Calls `factory.create(agent_id, flow_config, tool_manager)`
4. **RuntimeDeps injection** - Creates deps with `trace`, `factory`, `tool_manager`, `session_id`
5. **Execution** - Calls `agent.run(message, deps=deps, message_history=deps.message_history)`
6. **Result wrapping** - Wraps `ModelResponse` in `XenoMessageNode` with metadata

#### create_child_node() Method
Creates child node for delegation:
```python
def create_child_node(self, target_agent_id) -> XenoAgentNode:
    return XenoAgentNode(
        agent_id=target_agent_id,
        factory=self.factory,
        flow_config=self.flow_config,
        tool_manager=self.tool_manager,
        model=self.model,
    )
```

### Testing Strategy

#### Mock-based Testing
Since actual LLM calls require valid API keys and available models, tests use mocks:
- `AsyncMock(return_value=mock_result)` - For async method mocking
- `patch.object(factory, "create", ...)` - For mocking factory creation
- Mock `Agent` and `ModelResponse` - For simulating agent execution

#### Test Coverage
- **Initialization**: Verifies node setup with factory, flow_config, tool_manager
- **Recursion limit**: Tests depth check with `parent_depth` parameter
- **RuntimeDeps construction**: Verifies deps are built correctly when agent runs
- **Child node creation**: Tests delegation capability
- **MessageNode wrapping**: Verifies ModelResponse → XenoMessageNode conversion

### Integration Points

1. **AgentFactory** - `XenoAgentNode` uses `factory.create()` to get `Agent` instances
2. **RuntimeDeps** - Injects `TraceID`, `factory`, `tool_manager` into deps
3. **Message history** - Maintains history across multiple `run()` calls via `deps.message_history`
4. **Token usage** - Captures usage from `result.usage()` and stores in metadata

### Design Decisions

1. **Added `parent_depth` parameter** - Allows explicit depth tracking when reconstructing traces from `parent_trace_id`
2. **Separate `create_child_node()`** - Clean delegation pattern - parent creates child node
3. **XenoMessageNode for wrapping** - Maintains compatibility with existing message node structure
4. **MAX_DELEGATION_DEPTH = 5** - Enforced safety limit for recursion

### Known Limitations

1. **Trace path reconstruction** - When `parent_trace_id` is provided, we cannot reconstruct full path (only have root ID). This is mitigated by `parent_depth` parameter.
2. **No ACP event emission** - Not yet implemented (Task 3)
3. **No cycle detection** - Not yet tested (would need full trace path to check `has_cycle()`)

### File Changes
- ✅ Created: `packages/xeno-agent/src/xeno_agent/agentpool/__init__.py`
- ✅ Created: `packages/xeno-agent/src/xeno_agent/agentpool/node.py` (MessageNode, XenoMessageNode, XenoAgentNode)
- ❌ Deleted: `packages/xeno-agent/src/xeno_agent/pydantic_ai/pool.py` (ignored by git - not yet tracked)
- ✅ Updated: `packages/xeno-agent/tests/test_agentpool_integration.py` (4 new tests for XenoAgentNode)

### Next Steps
Task 2 complete. The `XenoAgentNode` bridge is ready for:
- Task 3: Event Adapter for ACP integration
- Task 4: Config migration script
- Task 5: Update entry point to use agentpool runtime

