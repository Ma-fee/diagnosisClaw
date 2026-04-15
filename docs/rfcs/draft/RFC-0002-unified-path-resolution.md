---
rfc_id: RFC-0002
title: Unified Path Resolution Mechanism for AgentPool Configuration
status: DRAFT
author: Sisyphus
reviewers: []
created: 2026-01-30
last_updated: 2026-01-30
decision_date:
---

## Overview

This RFC proposes a unified path resolution mechanism for AgentPool configuration files to resolve the asymmetry where relative paths in different configuration contexts resolve against different baselines. Currently, `system_prompt` paths resolve relative to the config file directory, while custom toolset schema paths resolve relative to the provider module directory, causing inconsistent behavior and user confusion.

The expected outcome is that all relative paths in AgentPool configuration files are resolved consistently using the config file's directory as the baseline, enabling users to write portable configurations regardless of where provider code is located.

## Background & Context

### Current State

AgentPool supports multiple types of relative paths in YAML configuration:

1. **System prompt files**: Specified in `system_prompt.path` for FilePromptConfig
2. **Custom toolset schemas**: Specified in `tools.kw_args.schemas` for CustomToolsetConfig
3. **Knowledge base paths**: Specified in agent configuration
4. **Import references**: File-based agent/team imports

### Path Resolution Asymmetry

The current implementation resolves these paths inconsistently:

| Context | Path Resolution Baseline | Code Location |
|---------|------------------------|----------------|
| `system_prompt.path` (FilePromptConfig) | Config file directory | `agents.py:370-372` ✅ |
| `system_prompt.path` (Agent init) | Config file directory | `agent.py:356-357` ✅ |
| `CustomToolsetConfig.kw_args.schemas` | Provider module directory | `delegation_provider.py:49,58-59` ❌ |
| Config inheritance (INHERIT) | Resolved primary_path | `resolution.py:302` ✅ |

### Terminology

- **Baseline directory**: The reference directory used for resolving relative paths
- **Config file directory**: The directory containing the YAML configuration file being loaded
- **Provider module directory**: The directory containing the Python module implementing a custom toolset/resource provider

### Related RFCs

None (first RFC addressing configuration path resolution)

## Problem Statement

### Specific Problem

When a user specifies a relative path in an AgentPool configuration file, the path's resolution depends on **where** in the configuration the path is specified, not on **what** the path represents. This creates inconsistent behavior:

**Example configuration** (`diag-agent.yaml`):
```yaml
agents:
  fault_expert:
    type: native
    system_prompt:
      - type: file
        path: ../docs/rfc/001_agent_system_design/capability/citation.mdc  # ✅ Works
    tools:
      - type: custom
        import_path: xeno_agent.agentpool.resource_providers.XenoDelegationProvider
        kw_args:
          schemas:
            new_task: ../docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml  # ❌ Fails
```

**File locations**:
- Config file: `/Users/yuchen.liu/src/yilab/iroot-llm/packages/xeno-agent/config/diag-agent.yaml`
- Provider module: `/Users/yuchen.liu/src/yilab/iroot-llm/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`
- Target file: `/Users/yuchen.liu/src/yilab/iroot-llm/docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml`

**Resolution behavior**:
- `system_prompt.path` resolves to: `/Users/yuchen.liu/src/yilab/iroot-llm/packages/xeno-agent/docs/...` ✅
- `schemas.new_task` resolves to: `.../resource_providers/../docs/...` ❌

### Evidence of Problem

From actual error trace:
```
FileNotFoundError: Tool schema file not found:
/Users/yuchen.liu/src/yilab/iroot-llm/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/../docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml
```

Expected path:
```
/Users/yuchen.liu/src/yilab/iroot-llm/docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml
```

### Impact of Not Solving

**User Experience**:
- Users must use absolute paths for custom toolset schemas, breaking configuration portability
- Different path resolution rules create confusion and require documentation of special cases
- Moving code (e.g., refactoring) requires updating absolute paths in configurations

**Technical Debt**:
- Path resolution logic is scattered across 3+ locations with different implementations
- Custom toolset providers must implement their own path resolution, increasing provider complexity
- No single point of control for path resolution behavior

**Maintenance Burden**:
- Adding new configuration fields requires determining where path resolution should occur
- Testing path resolution requires covering multiple code paths
- Documentation must explain the asymmetry to users

## Goals & Non-Goals

### Goals

1. **Unified baseline**: All relative paths in configuration files resolve relative to the config file directory
2. **Single responsibility**: One utility function/class handles path resolution across the codebase
3. **Backward compatibility**: Existing configurations with absolute paths continue to work unchanged
4. **Provider extensibility**: Custom providers can optionally receive config file path for advanced path resolution
5. **Testability**: Path resolution can be tested independently without loading full configurations

### Non-Goals

1. **Path resolution in Python import paths**: This RFC does not address module import path resolution
2. **Path resolution in INHERIT field**: Already handled correctly by yamling
3. **Path resolution in user-provided callable paths**: User-supplied Python paths are out of scope
4. **Breaking changes to existing provider APIs**: Custom providers continue to work without modification

## Evaluation Criteria

| Criterion | Weight | Acceptance Criteria |
|-----------|---------|-------------------|
| **Consistency** | High | All relative paths use same baseline (config file directory) |
| **Maintainability** | High | Single path resolution utility, no duplicated logic |
| **Backward Compatibility** | High | Existing configurations (absolute paths) work unchanged |
| **Performance** | Medium | Path resolution does not add noticeable overhead |
| **Testability** | Medium | Path resolution can be unit tested independently |
| **Provider Flexibility** | Low | Providers can optionally access config file path |

## Options Analysis

### Option 1: Use Absolute Paths in Configuration

**Description**:
Document that custom toolset schema paths must be absolute. Users update their configurations to use full paths.

**Advantages**:
- Zero implementation effort
- No risk of breaking existing functionality
- Simple documentation update

**Disadvantages**:
- Breaks configuration portability (different users may have different base paths)
- Violates user expectations (why do `system_prompt` paths work but `schemas` don't?)
- Creates friction for developers (updating paths when moving directories)

**Evaluation Against Criteria**:
| Criterion | Score | Notes |
|-----------|-------|-------|
| Consistency | ⭐ | Introduces inconsistency by requiring special handling for some paths |
| Maintainability | ⭐ | No new code, but documentation complexity increases |
| Backward Compatibility | ⭐⭐⭐⭐⭐⭐ | Existing configs work, but new ones are less portable |
| Performance | ⭐⭐⭐⭐⭐⭐ | No runtime overhead |
| Testability | ⭐⭐⭐⭐⭐ | No tests needed |
| Provider Flexibility | ⭐ | No provider changes needed |

**Effort Estimate**: Very Low (documentation only)

**Risk Assessment**:
- Low risk (no code changes)
- High user frustration risk (inconsistent behavior)

### Option 2: Unified Path Resolution in Manifest Loading

**Description**:
Implement a unified path resolution mechanism that resolves all relative paths in configuration during `AgentsManifest.from_file()` or `AgentsManifest.from_resolved()` loading. Create a `PathResolver` utility class and inject it into the configuration loading pipeline.

**Advantages**:
- Consistent behavior for all relative paths
- Centralized path resolution logic (single source of truth)
- Backward compatible (absolute paths still work)
- Improves provider experience (providers can optionally use config file path)

**Disadvantages**:
- Requires identifying all path-containing fields in configuration schema
- Must traverse nested configuration structures to find paths
- Potential performance overhead from deep config traversal
- Risk of missing path fields in future config additions

**Evaluation Against Criteria**:
| Criterion | Score | Notes |
|-----------|-------|-------|
| Consistency | ⭐⭐⭐⭐⭐ | All paths use same baseline |
| Maintainability | ⭐⭐⭐⭐⭐ | Single PathResolver utility |
| Backward Compatibility | ⭐⭐⭐⭐⭐ | Absolute paths work unchanged |
| Performance | ⭐⭐ | Minimal overhead from config traversal |
| Testability | ⭐⭐⭐⭐ | PathResolver independently testable |
| Provider Flexibility | ⭐⭐⭐ | Providers can receive optional config path |

**Effort Estimate**: Medium (3-5 days implementation + testing)

**Risk Assessment**:
- Medium risk (config traversal complexity)
- High benefit (fixes root cause, improves extensibility)

### Option 3: Provider-Specific Path Resolution with Config Path Injection

**Description**:
Modify `CustomToolsetConfig.get_provider()` to pass config file path to providers as a special parameter (e.g., `_config_base_path`). Providers can use this parameter if they need to resolve relative paths.

**Advantages**:
- Minimal changes to agentpool core (only CustomToolsetConfig)
- Providers maintain control over their path resolution
- Backward compatible (providers can ignore the parameter)

**Disadvantages**:
- Provider implementations must be updated to use the parameter
- Doesn't fix path resolution for other configuration fields (knowledge, file agents)
- Pushes complexity to providers instead of centralizing in agentpool
- Relies on provider authors to implement correctly

**Evaluation Against Criteria**:
| Criterion | Score | Notes |
|-----------|-------|-------|
| Consistency | ⭐⭐ | Only fixes custom toolset paths |
| Maintainability | ⭐⭐⭐ | Provider code scattered, core simple |
| Backward Compatibility | ⭐⭐⭐⭐ | Providers can ignore parameter |
| Performance | ⭐⭐⭐⭐⭐ | No runtime overhead |
| Testability | ⭐⭐ | Requires testing provider implementations |
| Provider Flexibility | ⭐⭐⭐ | Providers can opt-in to config path |

**Effort Estimate**: Low (1-2 days core changes + provider updates)

**Risk Assessment**:
- Medium risk (provider fragmentation)
- Medium benefit (partial fix)

### Option 4: Environment Variable Expansion for Paths

**Description**:
Support environment variables in path fields (e.g., `$PROJECT_ROOT/docs/...`) and expand them during config loading. Users set `$PROJECT_ROOT` to their project base directory.

**Advantages**:
- Gives users control over path baselines
- Works for all relative paths consistently
- No changes needed to provider code
- Familiar pattern (used in many tools)

**Disadvantages**:
- Requires environment setup (users must remember to set variables)
- Configuration not self-contained (depends on external state)
- Documentation burden (explain env vars, setup instructions)
- Adds cognitive load (different from user expectations in YAML)

**Evaluation Against Criteria**:
| Criterion | Score | Notes |
|-----------|-------|-------|
| Consistency | ⭐⭐⭐ | All paths resolve to PROJECT_ROOT |
| Maintainability | ⭐⭐⭐⭐ | Single env expansion logic |
| Backward Compatibility | ⭐⭐⭐⭐ | Existing absolute paths still work |
| Performance | ⭐⭐⭐⭐ | Minimal overhead |
| Testability | ⭐⭐⭐ | Testable independently |
| Provider Flexibility | ⭐⭐⭐ | No provider changes needed |

**Effort Estimate**: Low-Medium (2-3 days implementation + documentation)

**Risk Assessment**:
- Low risk (well-understood pattern)
- Medium benefit (improves portability)

### Option 5: ContextVar-based Runtime Path Resolution

**Description**:
Use Python's `contextvars.ContextVar` to set a `CONFIG_DIR` context variable during configuration loading. All code within the loading context (prompts, providers, etc.) can access `CONFIG_DIR.get()` to resolve relative paths.

```python
from contextvars import ContextVar
from pathlib import Path

CONFIG_DIR: ContextVar[Path | None] = ContextVar('config_dir', default=None)

def load_config(config_path: Path):
    token = CONFIG_DIR.set(config_path.parent)
    try:
        data = yamling.load_yaml_file(config_path)
        manifest = AgentsManifest.model_validate(data)
        return manifest
    finally:
        CONFIG_DIR.reset(token)
```

**Advantages**:
- Elegant, Pythonic approach
- Providers can opt-in by importing and using CONFIG_DIR
- Works with async code (contextvars are async-safe)
- No dictionary traversal needed
- Future extensibility (any code can access the context)

**Disadvantages**:
- **FATAL FLAW**: Provider initialization happens OUTSIDE the context
- Providers are instantiated in `AgentPool.__aenter__()`, after `from_file()` returns
- When provider calls `CONFIG_DIR.get()`, context has already been reset
- Requires providers to explicitly import and use CONFIG_DIR
- Invisible state makes debugging harder
- Third-party providers must be modified to use the context

**Timing Analysis (Why This Fails)**:

```
1. AgentsManifest.from_file()    ← CONFIG_DIR.set(path.parent)
2. return manifest               ← CONFIG_DIR.reset() - CONTEXT ENDS!
3. AgentPool(manifest)           
4. async with pool:              
5.   agent = pool.get_agent()    
6.     get_tool_providers()      ← provider.__init__() called here
7.       CONFIG_DIR.get()        ← Returns None! Context already reset
```

**Evidence from codebase**:
- `CustomToolsetConfig.get_provider()` is called from `agents.py:260-298` in `get_tool_providers()`
- `get_tool_providers()` is called during agent initialization in `AgentPool.__aenter__()`
- This happens AFTER `from_file()` has already returned and reset the context

**Evaluation Against Criteria**:
| Criterion | Score | Notes |
|-----------|-------|-------|
| Consistency | ❌ | FAILS - providers called outside context |
| Maintainability | ⭐⭐ | Invisible state, debugging difficulty |
| Backward Compatibility | ⭐⭐ | Providers must be modified |
| Performance | ⭐⭐⭐⭐⭐ | No overhead |
| Testability | ⭐⭐ | Context state hard to test |
| Provider Flexibility | ⭐ | Requires explicit opt-in |

**Effort Estimate**: Low (but doesn't solve the problem)

**Risk Assessment**:
- **CRITICAL RISK**: Does not work for the primary use case (custom toolset providers)
- Timing issue is fundamental to the current architecture
- Would require restructuring when providers are instantiated

**Conclusion**: This option is **NOT VIABLE** for solving the path resolution problem due to the timing mismatch between config loading and provider instantiation.

## Recommendation

**Recommended Option**: **Option 2 (Enhanced) - Unified Path Resolution with Value-Based Heuristics**

### Why Not ContextVar (Option 5)?

The ContextVar approach is elegant in theory but **fundamentally incompatible** with the current architecture:

1. **Timing Mismatch**: Providers are instantiated in `AgentPool.__aenter__()`, which happens AFTER `from_file()` returns. The context would already be reset when providers need it.

2. **Provider Coupling**: Requires all providers (including third-party) to explicitly import and use `CONFIG_DIR`, creating tight coupling.

3. **Invisible State**: ContextVars make debugging harder - the configuration appears correct but paths resolve incorrectly due to missing context.

### Why Option 2 (Enhanced)?

The original Option 2 has a critical gap: it only matches paths by **key names** (`path`, `file`, etc.), but the actual problem involves paths as **values** under arbitrary keys:

```yaml
kw_args:
  schemas:
    new_task: ../docs/new_task.yaml      # key is "new_task", not "path"
    attempt_completion: ../docs/ac.yaml  # key is "attempt_completion"
```

**Enhanced Option 2** adds **value-based heuristics** to detect path-like strings regardless of their key names.

### Justification

Based on evaluation criteria, Enhanced Option 2 scores highest:
- **Consistency** (⭐⭐⭐⭐⭐): All relative paths use the same baseline, eliminating user confusion
- **Maintainability** (⭐⭐⭐⭐⭐): Single PathResolver utility centralizes logic, reducing duplication
- **Backward Compatibility** (⭐⭐⭐⭐⭐): Absolute paths continue to work exactly as before
- **Testability** (⭐⭐⭐⭐): PathResolver and heuristics can be unit tested independently
- **Solves kw_args.schemas** (⭐⭐⭐⭐⭐): Value heuristics catch paths under arbitrary keys

**Trade-offs accepted**:
- **Performance** (⭐⭐): Accepting minimal overhead from config traversal
- **False positives risk** (Low): Heuristics may resolve non-path strings, but explicit exclusions minimize this

### Comparison Summary

| Aspect | Option 2 (Original) | Option 2 (Enhanced) | Option 5 (ContextVar) |
|--------|---------------------|---------------------|------------------------|
| Solves `kw_args.schemas` | ❌ No | ✅ Yes | ❌ Timing issue |
| Lazy loading safe | ✅ Yes | ✅ Yes | ❌ No |
| Third-party providers | ✅ Transparent | ✅ Transparent | ❌ Must modify |
| Provider API changes | None | None | Required |
| Debugging | ✅ Visible | ✅ Visible | ❌ Invisible state |

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     YAML Configuration File                     │
│                                                             │
│  agents:                                                   │
│    my_agent:                                                │
│      system_prompt:                                            │
│        path: ../docs/prompts/system.md                        │
│      tools:                                                   │
│        - type: custom                                            │
│          kw_args:                                               │
│            schemas: {../docs/schemas/tool.yaml}                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ load
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              AgentsManifest.from_file()                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │   1. Load YAML with yamling                     │   │
│  │   2. Validate with Pydantic                       │   │
│  │   3. Create PathResolver(config_file_path)        │   │
│  │   4. Travers config and resolve paths           │   │
│  │   5. Propagate config_file_path to agents/teams  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
        ▼                                       ▼
┌──────────────────┐                  ┌──────────────────┐
│  PathResolver    │                  │  All configs    │
│  Utility Class   │                  │  receive        │
│                  │                  │  config_file_path │
│  resolve(path)   │                  │                  │
│  ───────────────>                  │                  │
└──────────────────┘                  └──────────────────┘
```

### PathResolver Utility Class (Enhanced)

**File**: `/packages/agentpool/src/agentpool/utils/path_resolution.py`

```python
"""Path resolution utilities for AgentPool configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable


class PathResolver:
    """Resolves paths relative to a baseline directory.

    This class provides a unified mechanism for resolving relative paths
    in AgentPool configuration files. All relative paths are resolved
    against the config file's directory as the baseline.

    Example:
        resolver = PathResolver("/project/config/agents.yml")
        resolver.resolve("../docs/prompts/system.md")
        # Returns: /project/docs/prompts/system.md

        resolver.resolve("/absolute/path/to/file.txt")
        # Returns: /absolute/path/to/file.txt (unchanged)
    """

    def __init__(self, config_file_path: str | Path) -> None:
        """Initialize path resolver.

        Args:
            config_file_path: Path to the configuration file being loaded.
                             Relative paths will be resolved relative
                             to this file's directory.
        """
        self._baseline = Path(config_file_path).parent

    def resolve(self, path: str | Path) -> Path:
        """Resolve a path relative to config file directory.

        Args:
            path: Path to resolve. If absolute, returned unchanged.
                  If relative, resolved against config file directory.

        Returns:
            Resolved absolute path.

        Example:
            >>> resolver = PathResolver("/project/config/agents.yml")
            >>> resolver.resolve("../docs/prompts/system.md")
            Path('/project/docs/prompts/system.md')

            >>> resolver.resolve("/absolute/file.txt")
            Path('/absolute/file.txt')
        """
        path_obj = Path(path)

        if path_obj.is_absolute():
            return path_obj

        return self._baseline / path_obj


# Known path field names (high confidence)
PATH_KEYS: set[str] = {
    "path",
    "file",
    "directory",
    "file_path",
    "schema_file",
    "cwd",
    "working_directory",
}

# File extensions that indicate a path
PATH_EXTENSIONS: tuple[str, ...] = (
    ".yaml", ".yml", ".json", ".md", ".mdc", ".txt",
    ".py", ".js", ".ts", ".toml", ".ini", ".cfg",
)

# Patterns that are NOT paths (exclusions)
NON_PATH_PATTERNS: tuple[str, ...] = (
    "http://", "https://", "file://", "ftp://",  # URLs
    "s3://", "gs://", "az://",                    # Cloud storage
)

# Regex for Python import paths (module.submodule:ClassName)
IMPORT_PATH_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*:[a-zA-Z_][a-zA-Z0-9_]*$")


def is_path_like(value: str) -> bool:
    """Detect if a string value looks like a file path.
    
    This heuristic identifies path-like strings for resolution,
    while excluding URLs, Python imports, and other non-path patterns.
    
    Args:
        value: String to check
        
    Returns:
        True if the value appears to be a file path
        
    Examples:
        >>> is_path_like("../docs/schema.yaml")
        True
        >>> is_path_like("./config/agents.yml")
        True
        >>> is_path_like("https://example.com/file.yaml")
        False
        >>> is_path_like("mymodule.submodule:ClassName")
        False
        >>> is_path_like("just_a_string")
        False
    """
    if not value or not isinstance(value, str):
        return False
    
    # Sanity check - paths shouldn't be extremely long
    if len(value) > 500:
        return False
    
    # Exclude non-path patterns
    value_lower = value.lower()
    for pattern in NON_PATH_PATTERNS:
        if value_lower.startswith(pattern):
            return False
    
    # Exclude environment variable references
    if value.startswith("$") or value.startswith("${"):
        return False
    
    # Exclude special tokens
    if value in ("INHERIT", "null", "None", "true", "false"):
        return False
    
    # Exclude Python import paths (module.submodule:ClassName)
    if IMPORT_PATH_PATTERN.match(value):
        return False
    
    # Exclude Python dotted imports without colon (module.submodule.name)
    # But allow paths like "./module/file.py"
    if "." in value and "/" not in value and "\\" not in value:
        # Likely a Python import like "mypackage.mymodule"
        if all(part.isidentifier() for part in value.split(".")):
            return False
    
    # Positive indicators - explicit relative paths
    if value.startswith("./") or value.startswith("../"):
        return True
    
    # Positive indicators - known file extensions
    if value.endswith(PATH_EXTENSIONS):
        return True
    
    # Negative - no path separators at all
    if "/" not in value and "\\" not in value:
        return False
    
    # Has path separator and doesn't match exclusions
    return True


def resolve_paths_in_dict(
    data: dict[str, object],
    resolver: Callable[[Path], Path],
    path_keys: set[str] | None = None,
) -> dict[str, object]:
    """Recursively resolve paths in a nested dictionary.

    Uses two strategies:
    1. Key-based: Fields in `path_keys` are always resolved
    2. Value-based: Strings matching `is_path_like()` are resolved
    
    Args:
        data: Dictionary to process (typically from loaded YAML)
        resolver: Function that resolves a path (e.g., PathResolver.resolve)
        path_keys: Set of known path-containing keys. Defaults to PATH_KEYS.

    Returns:
        Dictionary with relative paths resolved to absolute paths.

    Note:
        This function modifies the dictionary in place for efficiency.
    """
    if path_keys is None:
        path_keys = PATH_KEYS

    for key, value in data.items():
        if isinstance(value, dict):
            # Recurse into nested dictionaries
            resolve_paths_in_dict(value, resolver, path_keys)
        elif isinstance(value, list):
            # Process lists
            _resolve_paths_in_list(value, resolver, path_keys)
        elif isinstance(value, str):
            # Strategy 1: Known path keys (high confidence)
            if key in path_keys:
                data[key] = str(resolver(Path(value)))
            # Strategy 2: Value heuristics (for kw_args.schemas etc.)
            elif is_path_like(value):
                data[key] = str(resolver(Path(value)))

    return data


def _resolve_paths_in_list(
    data: list[object],
    resolver: Callable[[Path], Path],
    path_keys: set[str],
) -> list[object]:
    """Recursively resolve paths in a list."""
    for i, item in enumerate(data):
        if isinstance(item, dict):
            resolve_paths_in_dict(item, resolver, path_keys)
        elif isinstance(item, list):
            _resolve_paths_in_list(item, resolver, path_keys)
        # Note: We don't resolve bare strings in lists by default
        # as they're more likely to be non-path values

    return data
```

### Modified AgentsManifest.from_file()

**File**: `/packages/agentpool/src/agentpool/models/manifest.py` (modify lines 676-710)

```python
@classmethod
def from_file(cls, path: JoinablePathLike) -> Self:
    """Load agent configuration from file.

    Args:
        path: Path to configuration file.

    Returns:
        Loaded agent configuration.

    Raises:
        ValueError: If loading fails
    """
    import yamling

    from agentpool.utils.path_resolution import PathResolver, resolve_paths_in_dict

    try:
        data = yamling.load_yaml_file(path, resolve_inherit=True)

        # NEW: Create path resolver for this config file
        resolver = PathResolver(path)

        # NEW: Resolve relative paths in configuration using dual strategy:
        # 1. Key-based: known path field names
        # 2. Value-based: is_path_like() heuristics
        resolve_paths_in_dict(data, resolver.resolve)

        agent_def = cls.model_validate(data)
        path_str = str(Path(path).resolve())  # Store absolute path

        def update_with_path(nodes: dict[str, Any]) -> dict[str, Any]:
            return {
                name: config.model_copy(update={"config_file_path": path_str})
                for name, config in nodes.items()
            }

        return agent_def.model_copy(
            update={
                "config_file_path": path_str,
                "agents": update_with_path(agent_def.agents),
                "teams": update_with_path(agent_def.teams),
            }
        )
    except Exception as exc:
        raise ValueError(f"Failed to load agent config from {path}") from exc
```

### Optional: Config Path Injection for Providers

**File**: `/packages/agentpool/src/agentpool_config/toolsets.py` (modify lines 639-656)

```python
def get_provider(self) -> ResourceProvider:
    """Get the resource provider instance.

    Returns:
        Initialized resource provider.

    Raises:
        ImportError: If provider module cannot be imported
        TypeError: If provider initialization fails
    """
    provider_cls = import_class(self.import_path)
    kwargs = self.kw_args.copy()

    # OPTIONAL: Inject config file path for providers that need it
    # Providers can access this as: kwargs.get('_config_base_path')
    # Note: This is optional, providers can ignore it
    if hasattr(self, 'config_file_path') and self.config_file_path:
        from pathlib import Path
        kwargs['_config_base_path'] = Path(self.config_file_path).parent

    name = kwargs.pop("name", provider_cls.__name__)
    try:
        return provider_cls(name=name, **kwargs)
    except TypeError as e:
        # Provide more helpful error for parameter mismatches
        raise TypeError(
            f"Provider '{self.import_path}' initialization failed. "
            f"Expected parameters: {inspect.signature(provider_cls.__init__).parameters}. "
            f"Received: {list(kwargs.keys())}. "
            f"Error: {e}"
        ) from e
```

### Modified XenoDelegationProvider (Optional Enhancement)

**File**: `/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py` (modify lines 48-67)

```python
def __init__(
    self,
    name: str = "delegation",
    schemas: dict[str, str] | None = None,
    _config_base_path: Path | None = None,  # NEW: Optional config file path
) -> None:
    """Initialize delegation provider.

    Args:
        name: Provider name
        schemas: Mapping of schema names to file paths
        _config_base_path: Optional path to config file directory.
                          If provided, paths resolve relative to this
                          instead of provider module directory.
    """
    super().__init__(name=name)

    # Use config file path if provided, otherwise use provider directory
    this_file_dir = _config_base_path or Path(__file__).parent

    if schemas:
        if (new_task_schema_path := schemas.get("new_task")) is not None:
            schema_path = Path(new_task_schema_path)
            if not schema_path.is_absolute():
                schema_path = this_file_dir / schema_path
            new_task_schema = load_tool_schema(str(schema_path))
            # ... rest of initialization
```

### Path Detection Heuristics (Enhanced)

The `is_path_like()` function uses a dual-strategy approach:

**Strategy 1: Key-Based Detection (High Confidence)**
Fields with known path-containing names are always resolved:
- `path`, `file`, `directory`, `file_path`, `schema_file`, `cwd`, `working_directory`

**Strategy 2: Value-Based Detection (For kw_args Flexibility)**
Strings matching path-like patterns are resolved regardless of key name:

| Pattern | Example | Result |
|---------|---------|--------|
| Starts with `./` or `../` | `../docs/schema.yaml` | ✅ Resolve |
| Ends with path extension | `config/tool.yaml` | ✅ Resolve |
| Contains `/` or `\` | `schemas/new_task.yaml` | ✅ Resolve |
| URL prefix | `https://example.com/file.yaml` | ❌ Skip |
| Env var reference | `$HOME/config.yaml` | ❌ Skip |
| Python import | `mymodule.submodule:ClassName` | ❌ Skip |
| Python dotted path | `agentpool.utils.path` | ❌ Skip |
| Special tokens | `INHERIT`, `null`, `None` | ❌ Skip |

**Exclusion Rules** (non-path patterns):
- URLs: `http://`, `https://`, `file://`, `s3://`, `gs://`, `az://`
- Environment variables: `$VAR`, `${VAR}`
- Python imports: `module.submodule:ClassName`
- Python dotted imports: `package.module.name` (no path separators)
- Special tokens: `INHERIT`, `null`, `None`, `true`, `false`
- Extremely long strings (>500 chars)

## Implementation Plan

### Phase 1: Foundation (Week 1)

**Milestone**: PathResolver utility and unit tests

**Tasks**:
1. Create `/packages/agentpool/src/agentpool/utils/path_resolution.py`
   - Implement `PathResolver` class
   - Implement `resolve_in_dict()` function
   - Implement `_resolve_in_list()` helper

2. Add comprehensive unit tests
   - Test absolute path resolution (unchanged)
   - Test relative path resolution (to config file directory)
   - Test nested dictionary traversal
   - Test list processing
   - Test edge cases (empty paths, special characters)

**Dependencies**: None (self-contained)

**Rollback**: Delete utility file and tests

### Phase 2: Core Integration (Week 2)

**Milestone**: Unified path resolution in manifest loading

**Tasks**:
1. Modify `AgentsManifest.from_file()`
   - Import `PathResolver` and `resolve_in_dict`
   - Create resolver instance
   - Call `resolve_in_dict()` before validation
   - Store absolute config file path

2. Modify `AgentsManifest.from_resolved()`
   - Apply same path resolution logic
   - Ensure layered configs work correctly

3. Update existing path resolution code
   - Remove redundant resolution in `agents.py:370-372`
   - Remove redundant resolution in `agent.py:356-357`
   - Update to use `PathResolver` if needed elsewhere

**Dependencies**: Phase 1 complete

**Rollback**: Revert changes to manifest.py, restore old code

### Phase 3: Provider Integration (Week 2-3)

**Milestone**: Optional config path injection for providers

**Tasks**:
1. Modify `CustomToolsetConfig.get_provider()`
   - Add `_config_base_path` parameter injection
   - Add helpful error messages for parameter mismatches

2. Update XenoDelegationProvider (optional)
   - Accept `_config_base_path` parameter
   - Use config path if provided, fall back to provider directory

3. Document provider enhancement
   - Add to provider development guide
   - Include examples of using config path

**Dependencies**: Phase 2 complete

**Rollback**: Remove parameter injection, revert provider changes

### Phase 4: Testing & Documentation (Week 3)

**Milestone**: Validated feature with user documentation

**Tasks**:
1. Add integration tests
   - Test with real-world configurations
   - Test with nested configs
   - Test with INHERIT

2. Update user documentation
   - Document path resolution behavior
   - Provide examples of relative paths
   - Explain config file directory as baseline

3. Update migration guide
   - Document breaking changes (none expected)
   - Explain new behavior for users

**Dependencies**: Phase 3 complete

**Rollback**: Revert all code changes

## Open Questions

1. **INHERIT semantics** (RESOLVED): When child config inherits from parent, all paths in the merged result resolve relative to the **child** config file's directory.
   - This is the expected behavior - users load the child config, so paths should be relative to it.
   - yamling merges parent content into child before returning, so paths are just strings at resolution time.
   - **Decision**: All paths resolve relative to the file passed to `from_file()`.

2. **Path identification scope** (RESOLVED): Use dual strategy - key-based AND value-based detection.
   - **Key-based**: Known field names (`path`, `file`, etc.) are always resolved.
   - **Value-based**: `is_path_like()` heuristics catch paths under arbitrary keys (like `kw_args.schemas`).
   - **Decision**: Implement both strategies in `resolve_paths_in_dict()`.

3. **Environment variable support**: Should we support environment variable expansion before path resolution?
   - Example: `$PROJECT_ROOT/docs/...` expands before resolution
   - Impact: Adds complexity but improves portability
   - **Recommendation**: Defer to separate RFC (out of scope for this fix)

4. **Custom toolset provider migration**: How to handle existing providers that rely on current behavior?
   - With enhanced approach, providers receive already-resolved absolute paths in `kw_args`
   - Providers using `Path(__file__).parent` will still work (absolute paths are unchanged)
   - **Recommendation**: No migration needed - resolved paths are transparent to providers

5. **Testing depth**: How comprehensive should path resolution tests be?
   - **Recommendation**: Comprehensive testing including:
     - `is_path_like()` heuristic edge cases
     - Nested `kw_args` structures
     - URL and Python import exclusions
     - Integration with real configs

## Decision Record

**Status**: Pending stakeholder review

**Approver**: TBD

**Decision Date**: TBD

**Discussion Points**:
- Consistency is the primary user-facing improvement
- Performance overhead is acceptable for maintainability gains
- Provider compatibility must be maintained (no breaking changes)
- Implementation effort is justified by fixing root cause

**Conditions on Approval**:
- PathResolver unit tests achieve >90% coverage
- Integration tests pass for all configuration types
- No regressions in existing functionality
- Documentation updated before merge

**Superceded By**: None

---

## Appendix A: Alternative Approaches Considered

### A1. Load-Time Path Resolution in yamling

**Considered**: Extending yamling module to handle path resolution automatically

**Rejected**: yamling is an external dependency; modifying it increases maintenance burden and creates divergence from upstream.

### A2. Runtime Path Resolution with Lazy Evaluation

**Considered**: Resolve paths only when accessed (lazy resolution)

**Rejected**: Adds complexity, harder to debug, potential for paths to resolve differently across accesses.

### A3. Path Normalization in All Agent Implementations

**Considered**: Have each agent type implement path resolution for its own config fields

**Rejected**: Duplicates logic, inconsistent implementations, maintenance burden.

### A4. ContextVar-based Runtime Path Resolution

**Considered**: Use Python's `contextvars.ContextVar` to set a `CONFIG_DIR` context during configuration loading. Providers would call `CONFIG_DIR.get()` to resolve paths at runtime.

```python
from contextvars import ContextVar

CONFIG_DIR: ContextVar[Path | None] = ContextVar('config_dir', default=None)

def load_config(config_path: Path):
    token = CONFIG_DIR.set(config_path.parent)
    try:
        # Load config...
        return manifest
    finally:
        CONFIG_DIR.reset(token)
```

**Rejected**: Fatal timing issue. Provider initialization happens in `AgentPool.__aenter__()`, which executes AFTER `from_file()` returns and resets the context. When providers call `CONFIG_DIR.get()`, the context has already been reset to `None`.

**Timeline demonstrating the issue**:
```
1. from_file() called    → CONFIG_DIR.set(path.parent)
2. return manifest       → CONFIG_DIR.reset() - CONTEXT ENDS
3. AgentPool(manifest)   
4. async with pool:      
5.   get_tool_providers()  → provider.__init__() called HERE
6.     CONFIG_DIR.get()    → Returns None (context already reset)
```

This approach would require fundamental changes to when providers are instantiated, which is out of scope.

## Appendix B: Migration Examples

### Example 1: Before and After

**Before** (using absolute paths):
```yaml
tools:
  - type: custom
    import_path: xeno_agent.agentpool.resource_providers.XenoDelegationProvider
    kw_args:
      schemas:
        new_task: /Users/yuchen.liu/src/yilab/iroot-llm/docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml
```

**After** (using relative paths):
```yaml
tools:
  - type: custom
    import_path: xeno_agent.agentpool.resource_providers.XenoDelegationProvider
    kw_args:
      schemas:
        new_task: ../../docs/rfc/001_agent_system_design/builtin_tools/new_task.yaml
```

### Example 2: Portable Configuration

A single configuration works in different developer environments:

**Developer A** (`~/project/config/agents.yml`):
```yaml
system_prompt:
  path: ../docs/prompts/system.md  # Resolves to ~/project/docs/prompts/system.md
```

**Developer B** (`/workspaces/project/config/agents.yml`):
```yaml
system_prompt:
  path: ../docs/prompts/system.md  # Resolves to /workspaces/project/docs/prompts/system.md
```

Both work correctly without modification.
