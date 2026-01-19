# AGENTS.md - Guidelines for Agentic Coding

## DEVELOPMENT ENVIRONMENT

### Package Structure
```
packages/xeno-agent/
├── config/              # Agent roles, tools configuration (YAML)
│   ├── roles/           # Agent role definitions (qa_assistant, fault_expert, etc.)
│   └── tools/           # Tool definitions (search_engine, etc.)
├── src/xeno_agent/
│   ├── agents/          # CrewAI agent building (XenoAgentBuilder)
│   ├── core/            # Flow orchestration, signals, state management
│   ├── skills/          # MCP tools and builtin meta tools
│   └── utils/            # Logging, config loading
├── examples/            # Usage examples (rfc_compliant_example.py)
├── tests/              # pytest test files
└── pyproject.toml        # uv workspace configuration
```

## DEVELOPMENT COMMANDS

### Dependency Management
```bash
# Sync dependencies from pyproject.toml
uv sync

# Add dependency
uv add <package-name>
```

### Running Code
```bash
# Run main entry point
uv run python -m xeno_agent

# Run example scripts
uv run python examples/rfc_compliant_example.py
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_builder.py

# Run specific test function
uv run pytest tests/test_builder.py::test_agent_creation

# Run with coverage (if configured)
uv run pytest --cov=xeno_agent tests/
```

### Linting & Formatting
```bash
# Check code quality
uv run ruff check .

# Format code
uv run ruff format .

# Run both (common workflow)
uv run ruff check . && uv run ruff format .
```

## CODE STYLE GUIDELINES

### Python Version & Formatting
- **Target**: Python 3.12
- **Line Length**: 180 characters (configured in ruff.toml)
- **Quote Style**: Double quotes (ruff.toml: `quote-style = "double"`)
- **Import Style**: isort (handled by ruff)

### Type Hints
- Use type hints for all function signatures
- Use `typing.Union` (PEP 604) for type unions
- Example: `def from_yaml(self, yaml_path: str) -> "XenoAgentBuilder"`

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `XenoAgentBuilder`, `SimulationSignal`)
- **Functions/Methods**: `snake_case` (e.g., `from_yaml`, `execute_agent_step`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `mode_slug`)
- **Private Methods**: `_leading_underscore_` (e.g., `_config_loader`)
- **Variables**: `snake_case` for local variables

### Error Handling
- Use specific exception types (ValueError, TypeError, etc.)
- Never use bare `except:` without exception type
- Always include descriptive error messages
- Example:
  ```python
  try:
      config = self._config_loader.load_role_config(role_name)
  except ValueError as e:
      logger.error(f"Failed to load config: {e}")
      raise
  ```

### Logging
- Use `src/xeno_agent/utils/logging.py::get_logger(__name__)`
- Prefer structured logging with f-strings
- Info level for normal operations, debug for detailed flow
- Example:
  ```python
  logger.info(f"Agent {agent_name} initialized")
  logger.debug(f"Configuration: {config}")
  logger.error(f"Failed to execute: {error}")
  ```

### Agent Configuration (YAML)
- Use double quotes for string values
- `identifier` field sets mode_slug (used for routing)
- `thought_process` provides step-by-step reasoning instructions
- `constraints` agent must-follow rules
- `capabilities` what agent can do
- Example:
  ```yaml
  identifier: qa_assistant
  name: Q&A Assistant
  goal: Route user queries to appropriate experts
  tools:
    - switch_mode
    - ask_followup_question
  thought_process: |
    1. Analyze user query
    2. If simple, answer directly
    3. If complex, switch_to fault_expert
  ```

### CrewAI Integration
- Use `XenoAgentBuilder` to construct CrewAI Agents
- Agents require: `role`, `goal`, `backstory`, `tools`, `llm`
- Backstory includes: backstory + thought_process + constraints + capabilities + examples
- Use `@start`, `@listen()`, `@router()` decorators for flow control

### Comments & Documentation
- Use docstrings for modules, classes, public methods
- Prefer single-line comments over multi-block
- Can use Chinese comments for domain-specific logic
- Chinese punctuation should use half-width characters (,) instead of full-width （），
- Avoid trailing whitespace

### Imports
- Group imports: stdlib, third-party, local
- Use absolute imports for local modules: `from xeno_agent.core.flow import XenoSimulationFlow`
- Avoid wildcard imports (`from module import *`)

## COMMON PATTERNS

### Building an Agent
```python
from xeno_agent.agents.builder import XenoAgentBuilder

agent = (XenoAgentBuilder(role_name="qa_assistant", ...)
    .from_yaml("qa_assistant.yaml")
    .with_llm(llm)
    .build())
```

### Creating a Tool
```python
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

class CustomTool(BaseTool):
    name: str = "custom_tool"
    description: str = "Tool description for LLM"
    args_schema: type[BaseModel] = InputSchema

    def _run(self, arg1: str, arg2: int):
        # Tool implementation
        return result
```

### Flow Control
- Use `SwitchModeSignal` for GOTO (complete role switch)
- Use `NewTaskSignal` for GOSUB (temporary delegation)
- Use `CompletionSignal` for RETURN (task completion)
- Use `AskFollowupSignal` for HITL (user interaction)
- Signals must call `super().__init__()` for proper pickling

## PRECOMMIT HOOKS
- Automatically runs `uv-lock` (skipped if no changes)
- Runs `ruff check` (linting)
- Runs `ruff format` (formatting)
- Hook will fail if code doesn't pass checks

## PROJECT-SPECIFIC NOTES
- MCP tools are registered in `src/xeno_agent/skills/registry.py`
- Tool names should NOT have prefixes (e.g., use `switch_mode`, not `xeno_meta_switch_mode`)
- Agent roles are defined in `config/roles/*.yaml`
- Signal exceptions inherit from `BaseException` for Flow interception
- Use `uv` instead of `pip` for all dependency operations
