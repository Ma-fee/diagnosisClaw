---
rfc_id: RFC-007
title: Dynamic Context Pruning (DCP) System for Xeno-Agent
status: REVIEW
author: Yuchen Liu
reviewers: []
created: 2026-01-27
last_updated: 2026-01-27
decision_date:
---

## Overview

This RFC proposes implementing a Dynamic Context Pruning (DCP) system for Xeno-Agent to reduce token consumption in long-running conversations while maintaining dialogue quality. The system will combine automated pruning strategies with LLM-driven tools, inspired by OpenCode's DCP plugin design but adapted to the agentpool/pydantic-ai architecture.

**Why Now**: Xeno-Agent is designed for long-running tasks where token consumption grows exponentially. Without proactive context management, sessions become inefficient and costly, especially on per-request billing models.

**Expected Outcome**: A configurable, extensible context pruning system that:
- Automatically removes redundant tool outputs
- Provides LLM-driven tools for intelligent content reduction
- Maintains conversation quality while reducing costs
- Integrates seamlessly with existing agentpool infrastructure

## Background & Context

### Reference Materials

This RFC is informed by the detailed architecture survey of OpenCode's DCP plugin:
- **Survey Document**: [`docs/survey/oh-my-opencode/opencode_dcp_architecture_survey.md`](../survey/oh-my-opencode/opencode_dcp_architecture_survey.md)

The survey covers OpenCode DCP's complete implementation including:
- Hook-based plugin integration with 6 lifecycle hooks
- Automated strategies (deduplication, supersede writes, purge errors)
- LLM-driven tools (discard, extract) with validation and protection
- Placeholder replacement mechanism preserving message structure
- Session state management and persistence patterns
- Multi-layer protection (tool, file, turn-based)

### Current State

Xeno-Agent is built on agentpool (a high-level wrapper around pydantic-ai) and manages message history through:

- **MessageHistory class** (`src/agentpool/messaging/message_history.py`)
  - Stores messages in `ChatMessageList`
  - Configurable via `MemoryConfig` (max_messages, max_tokens)
  - Provides `get_history(do_filter=True)` for automatic filtering

- **CompactionPipeline** (`src/agentpool/messaging/compaction.py`)
  - Composable pipeline with filtering, truncation, and summarization steps
  - Configurable via YAML manifest
  - Steps: FilterThinking, TruncateToolOutputs, KeepLastMessages, Summarize, etc.

- **Hook System** (`src/agentpool/hooks/base.py`)
  - Pre/post run hooks, pre/post tool hooks
  - Supports CallableHook, CommandHook, PromptHook
  - Can modify inputs and inject context

### OpenCode DCP Analysis

Research of OpenCode's DCP plugin reveals:

**Key Features**:
1. **Automated Strategies** (zero LLM cost):
   - Deduplication: Remove duplicate tool calls, keep newest
   - Supersede Writes: Prune write inputs covered by subsequent reads
   - Purge Errors: Remove large inputs from failed tools after N turns

2. **LLM-Driven Tools** (intelligent pruning):
   - `discard`: Remove completed tool outputs without knowledge retention
   - `extract`: Preserve distilled knowledge before removal

3. **Placeholder Replacement**:
   - Doesn't delete messages, replaces content with short strings
   - Preserves message structure and metadata

4. **Protection Mechanisms**:
   - Tool protection (certain tools never pruned)
   - File protection (glob patterns for sensitive files)
   - Turn protection (recent tools immune for N turns)

5. **Session State**:
   - Per-session pruning decisions
   - Token savings tracking
   - Tool metadata cache (rebuilt from messages, not persisted)

### Differences in Architecture

| Aspect | OpenCode DCP | Agentpool/Xeno-Agent |
|---------|---------------|----------------------|
| Plugin System | 6 hooks (experimental.chat.messages.transform, etc.) | pre_run, post_run, pre_tool_use, post_tool_use |
| Message Format | `WithParts` with `Part[]` array | `ChatMessage` with pydantic-ai `ModelMessage` |
| Tool Registration | Plugin tool registry | agentpool tool system |
| State Persistence | File-based (~/.local/share/opencode/storage/plugin/) | SQLSessionStore for metadata, storage providers for messages |
| Context Injection | Synthetic assistant messages with `ignored: true` | PromptInjectionManager, `additional_context` in hooks |

## Problem Statement

### Specific Problem

As conversations progress in Xeno-Agent, message history accumulates, leading to:

1. **Exponential Token Growth**:
   - Tool outputs (file reads, code execution results) are often large
   - Repeated file reads duplicate content in history
   - Error retries add redundant command sequences

2. **Context Window Waste**:
   - Duplicate tool calls provide no additional value
   - Write operations superseded by reads contain redundant information
   - Failed tool calls retain large inputs while only error messages are relevant

3. **Increased Latency and Cost**:
   - More input tokens = longer processing time
   - Per-request billing models accumulate costs linearly with history
   - Cache hit rates decrease as context grows (observed 85% → 65% in DCP study)

### Evidence and Impact

**Quantified Issues**:
- Long sessions (>200K tokens) become impractical without pruning
- Repeated `read` operations on same files can consume 5K+ tokens each
- Failed `bash` commands may retain multi-line command blocks after error is resolved

**Impact of Not Solving**:
- **Cost**: Prohibitive for production use on per-request billing
- **Quality**: Context window pollution can degrade LLM focus
- **User Experience**: Slower responses in long conversations

## Goals & Non-Goals

### Goals

1. **Implement Automated Pruning Strategies**
   - Deduplicate identical tool calls (keep newest)
   - Remove write inputs covered by subsequent reads
   - Prune failed tool inputs after N turns

2. **Provide LLM-Driven Pruning Tools**
   - Tool to discard tool outputs without knowledge retention
   - Tool to extract/distill knowledge before removal

3. **Maintain Message Structure (Placeholder Replacement)**
   - **NEVER delete messages or tool results** - only replace content with placeholders
   - Replace tool output content with short placeholder strings (e.g., `"[Content pruned...]"`)
   - Preserve message structure, metadata, and tool_call_id linking
   - Keep message count and order intact for conversation coherence
   - Placeholder format must preserve JSON schema validity (see Type-Safe Placeholders)

4. **Multi-Layer Protection**
   - Configure protected tools (never prune)
   - Configure protected file patterns
   - Configure turn-based immunity

5. **Seamless Integration**
   - Leverage existing CompactionPipeline
   - Extend hook system for pruning hooks
   - Configure via YAML manifest

6. **Track and Report**
   - Token savings statistics per session
   - Cross-session cumulative savings
   - User-facing commands to inspect state

### Non-Goals

- **Automated Summarization**: LLM-based summarization already exists in CompactionPipeline
- **Memory Compression**: Focus on message-level pruning, not binary compression
- **Context Window Management**: Token budgeting handled by existing `max_tokens` config
- **Message Deletion**: Never delete messages, only replace content with placeholders
- **Automatic Decision-Making**: Pruning is explicit (automated strategies + LLM tools), not heuristic

### Critical Safety Requirements

Based on architecture analysis and Metis review, these requirements are **MANDATORY** to prevent API errors and data corruption:

#### 1. Atomic Pairing Rule

**Problem**: Modern LLM APIs (OpenAI/Anthropic) enforce strict `ToolCallPart` ↔ `ToolReturnPart` pairing. If DCP prunes a tool return content but corrupts the pairing, the API will return a 400 error ("Missing output for tool_call_id...").

**Requirement**:
- `ToolCallPart` and `ToolReturnPart` MUST remain linked via `tool_call_id`
- When pruning, only replace `content` field of `ToolReturnPart` with placeholder
- NEVER remove the `ToolReturnPart` message entirely
- NEVER break the `tool_call_id` reference

```python
# CORRECT: Replace content only, preserve structure
part.content = "[Content pruned to save context]"

# WRONG: Remove the part entirely (breaks pairing)
parts.remove(tool_return_part)  # ❌ API will reject
```

#### 2. Type-Safe Placeholders

**Problem**: Replacing a JSON object/array with a string placeholder breaks pydantic-ai's validation for function arguments.

**Requirement**:
- If original content is `str` → placeholder is `str`
- If original content is `list` → placeholder is single-element list `["[Content pruned]"]`
- If original content is `dict` → placeholder is minimal dict `{"_pruned": True, "reason": "..."}`
- NEVER change the type of a field during pruning

```python
def create_type_safe_placeholder(original: Any, reason: str = "superseded") -> Any:
    """Create a placeholder that preserves the original type."""
    placeholder_text = f"[Content pruned: {reason}]"
    
    match original:
        case str():
            return placeholder_text
        case list():
            return [placeholder_text]
        case dict():
            return {"_pruned": True, "reason": reason}
        case _:
            # For other types, return string (safest fallback)
            return placeholder_text
```

#### 3. Selective Field Pruning

**Problem**: Tool arguments often have specific schemas. Replacing entire objects can break validation.

**Requirement**:
- Only prune heavy content fields: `content`, `text`, `code`, `output`, `data`
- Preserve metadata fields: `filePath`, `path`, `tool_name`, `status`, `timestamp`
- Preserve schema-critical fields that tools depend on

```python
PRUNEABLE_FIELDS = {"content", "text", "code", "output", "data", "result"}
PRESERVED_FIELDS = {"filePath", "path", "tool_name", "status", "error", "tool_call_id"}

def selective_field_prune(args: dict[str, Any], reason: str) -> dict[str, Any]:
    """Prune only heavy content fields, preserve metadata."""
    result = {}
    for key, value in args.items():
        if key in PRUNEABLE_FIELDS and isinstance(value, str) and len(value) > 100:
            result[key] = f"[Pruned: {reason}]"
        else:
            result[key] = value
    return result
```

#### 4. Negative History Retention

**Problem**: Aggressive pruning of failed tool inputs removes context about what didn't work, causing the model to repeat the same failures.

**Requirement**:
- Configure "keep last N failures" per tool type (default: 3)
- Only prune failed tool inputs after N subsequent turns AND after a successful retry
- Preserve error messages even when pruning inputs

```python
class PurgeFailedToolInputs(CompactionStep):
    keep_last_failures: int = 3  # Keep last N failures per tool type
    
    async def apply(self, messages: MessageSequence) -> list[ModelMessage]:
        # Group failures by tool type
        failures_by_tool: dict[str, list[int]] = {}
        
        for idx, failure in enumerate(self._find_failures(messages)):
            tool_name = failure["tool"]
            if tool_name not in failures_by_tool:
                failures_by_tool[tool_name] = []
            failures_by_tool[tool_name].append(idx)
        
        # Only prune if we have more than keep_last_failures
        prune_ids = []
        for tool_name, indices in failures_by_tool.items():
            if len(indices) > self.keep_last_failures:
                # Keep the last N, prune older ones
                prune_ids.extend(indices[:-self.keep_last_failures])
        
        return self._apply_pruning(messages, prune_ids)
```

## Evaluation Criteria

### Technical Criteria

| Criterion | Priority | Measurement | Minimum Threshold |
|------------|-----------|--------------|-------------------|
| Token Savings | High | % reduction in input tokens vs baseline | 20% |
| Conversation Quality | High | Task completion rate (comparing pruned vs unpruned) | 95% |
| Performance | Medium | Latency overhead of pruning pipeline | <50ms |
| Correctness | Critical | No loss of information required for task completion | 100% |

### Operational Criteria

| Criterion | Priority | Measurement | Minimum Threshold |
|------------|-----------|--------------|-------------------|
| Configurability | High | Number of config options | 5+ |
| Observability | Medium | Commands/diagnostics available | /dcp context, /dcp stats |
| Debuggability | Medium | Logging/tracing capabilities | Complete |

### Business Criteria

| Criterion | Priority | Measurement | Minimum Threshold |
|------------|-----------|--------------|-------------------|
| Implementation Effort | Medium | Development time | 2-3 weeks |
| Risk | Medium | Complexity of changes | Low-Medium |

## Options Analysis

### Option 1: Extend Existing CompactionPipeline (Recommended)

**Description**:

Add new CompactionStep classes to the existing pipeline system:
- `DeduplicateToolCalls`: Remove duplicate tool calls by signature
- `SupersedeWriteInputs`: Prune writes covered by subsequent reads
- `PurgeFailedToolInputs`: Remove inputs from failed tools

Integrate with hook system to add LLM-driven pruning tools (`discard`, `extract`).

**Architecture**:
```python
# New CompactionSteps in src/agentpool/messaging/compaction.py

class DeduplicateToolCalls(CompactionStep):
    """Remove duplicate tool calls, keep only the newest."""
    def __init__(self, protected_tools: list[str] = None, protected_files: list[str] = None):
        self.protected_tools = protected_tools or []
        self.protected_files = protected_files or []

    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        # Group by tool name + normalized parameters
        # Keep only the latest in each group
        # Return modified messages with placeholder outputs
        pass

class SupersedeWriteInputs(CompactionStep):
    """Remove write inputs covered by subsequent reads."""
    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        # Track writes and reads per file using tool_call_id
        # Build map: Map<tool_call_id, ToolCallPart>
        # Link ToolReturnPart (read output) to ToolCallPart (write input) via ID
        # Prune write inputs (content field only) if read follows
        pass

class PurgeFailedToolInputs(CompactionStep):
    """Remove inputs from failed tools after N turns."""
    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        # Find tools with status="error" and turn_age >= threshold
        # Safety check: Only prune if error is generic (e.g. timeout)
        # Preserve input if error references specific lines/tokens
        # Replace heavy input fields with placeholder
        pass
```

**Hook Integration**:
```python
# Add to agent via hooks or manifest

class DCPPruningHook(Hook):
    """Hook to execute pruning before each run."""
    async def pre_run(self, input: HookInput) -> HookResult:
        # Build and execute compaction pipeline
        pipeline = CompactionPipeline(steps=[
            DeduplicateToolCalls(protected_tools=...),
            SupersedeWriteInputs(protected_files=...),
            PurgeFailedToolInputs(turn_threshold=4),
        ])
        compacted = await pipeline.apply(input.messages)
        input.agent.conversation.set_history(compacted)
        return HookResult(decision="allow")
```

**LLM-Driven Tools**:
```python
# Add pruning tools to agent's toolset

@agent.tool
async def discard(
    ids: list[int],
    reason: str = "completion" | "noise",
    ctx: RunContext
) -> str:
    """Mark tool outputs for removal without knowledge retention."""
    # Validate IDs
    # Check protected tools/files
    # Add to prune list
    # Send notification
    pass

@agent.tool
async def extract(
    ids: list[int],
    distillation: list[str],
    ctx: RunContext
) -> str:
    """Preserve distilled knowledge before removing tool outputs."""
    # Validate distillation required
    # Validate IDs
    # Add to prune list
    # Inject distillation as ignored message
    pass
```

**Configuration**:
```yaml
# manifest.yml
agents:
  my_agent:
    model: openai:gpt-4o
    hooks:
      pre_run:
        - type: callable
          import_path: agentpool.dcp.pruning_hook

    tools:
      discard:
        type: callable
        import_path: agentpool.dcp.tools.discard
      extract:
        type: callable
        import_path: agentpool.dcp.tools.extract

    dcp:
      enabled: true
      protected_tools:
        - "task"
        - "todowrite"
        - "todoread"
        - "write"
        - "edit"
      protected_files:
        - "*.secret"
        - "config/*.json"
      turn_protection:
        enabled: true
        turns: 2
      strategies:
        deduplication:
          enabled: true
          protected_tools: []
        supersede_writes:
          enabled: true
        purge_errors:
          enabled: true
          turn_threshold: 4
      prune_notification: "minimal"  # off, minimal, detailed
```

**Advantages**:
- ✅ Leverages existing CompactionPipeline infrastructure (already async)
- ✅ Minimal code changes (new steps only)
- ✅ Composable with existing steps (FilterThinking, KeepLastMessages)
- ✅ Configurable via YAML manifest
- ✅ Extensible (easy to add new strategies)

**Disadvantages**:
- ❌ Hook integration adds complexity to agent initialization
- ❌ Placeholder replacement must respect JSON schema (cannot replace dict with string)
- ❌ Token counting requires integration with agentpool's existing mechanism

**Evaluation Against Criteria**:

| Criterion | Score/Rating | Notes |
|-----------|--------------|-------|
| Token Savings | 9/10 | Proven effective in OpenCode |
| Conversation Quality | 8/10 | Placeholder-based, preserves structure |
| Performance | 9/10 | Pipeline overhead minimal, native async support |
| Correctness | 8/10 | Protection mechanisms prevent over-pruning |
| Configurability | 9/10 | YAML manifest + protected lists |
| Observability | 7/10 | Need to add stats tracking |
| Implementation Effort | 8/10 | Extends existing patterns |
| Risk | 7/10 | Low-medium complexity |

**Effort Estimate**: 2 weeks
- Week 1: Implement CompactionSteps, schema-safe placeholder logic
- Week 2: Hook integration, LLM tools, stats tracking, testing

**Risk Assessment**:
- **Low**: Async integration (natively supported)
- **Medium**: JSON Schema validation with placeholders
- **Mitigation**: Implement selective field pruning instead of full object replacement

---

### Option C: Xeno-Agent Specific CompactionSteps (Recommended Refinement)

**Description**:

Implement DCP CompactionSteps in xeno-agent with workspace and task-aware strategies.

**Why This Approach**:

1. **Xeno-Agent Specific Requirements**:
   - Workspace-aware pruning (knows about `src/`, `test/`, `docs/` structure)
   - Task integration (aware of task graphs, dependencies)
   - Build artifacts management (prune intermediate build outputs)
   - Test results optimization (preserve failures, discard passes)

2. **Flexible Step Registration**:
   - agentpool's `CompactionStep` is an abstract base class
   - Can be implemented anywhere and registered via config
   - `CompactionPipeline` accepts class references, not imports from agentpool only

3. **Faster Iteration**:
   - No agentpool release dependency
   - Can prototype and refine quickly
   - Test in xeno-agent context

**Architecture**:

```python
# xeno_agent/dcp/compaction_steps.py

from agentpool.messaging.compaction import CompactionStep
from pydantic_ai import ModelMessage, ModelRequest, ModelResponse

class XenoWorkspacePruneStep(CompactionStep):
    """Xeno-agent specific pruning based on workspace state."""
    
    def __init__(
        self,
        preserve_patterns: list[str] | None = None,
        task_aware: bool = False,
    ):
        self.preserve_patterns = preserve_patterns or [
            "src/**/*.ts",
            "test/**/*.test.ts",
            "docs/**/*.md",
        ]
        self.task_aware = task_aware

    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        # Implement workspace-aware pruning logic
        pass

class XenoBuildArtifactPruneStep(CompactionStep):
    """Prune build intermediate outputs keeping final artifacts."""
    
    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        # Track build outputs vs final artifacts
        pass

# Registration via xeno-agent manifest

compaction:
  steps:
    - type: deduplicate  # From agentpool (if available)
    - type: xeno_workspace_prune  # Custom step
      preserve_patterns:
        - "src/**/*.ts"
        - "test/**/*.test.ts"
      task_aware: true
    - type: xeno_build_artifact_prune  # Custom step
```

**Hybrid Integration Pattern**:

```python
# xeno-agent/dcp/hooks.py

from agentpool.hooks import Hook, HookResult
from agentpool.messaging.compaction import CompactionPipeline
from xeno_agent.dcp.compaction_steps import (
    XenoWorkspacePruneStep,
    XenoBuildArtifactPruneStep,
)

class XenoDCPPruningHook(Hook):
    """Xeno-Agent specific DCP hook combining agentpool and custom steps."""
    
    async def pre_run(self, input: HookInput) -> HookResult:
        # Check if DCP enabled
        if not input.agent.config.get("dcp", {}).get("enabled"):
            return HookResult(decision="allow")
        
        # Build pipeline: agentpool steps + xeno-agent steps
        pipeline = CompactionPipeline(steps=[
            # Use agentpool steps if available
            DeduplicateToolCalls(protected_tools=...),
            
            # Add xeno-agent specific steps
            XenoWorkspacePruneStep(task_aware=True),
            XenoBuildArtifactPruneStep(),
        ])
        
        # Apply pipeline
        compacted = await pipeline.apply(input.agent.conversation.get_history())
        input.agent.conversation.set_history(compacted)
        
        return HookResult(decision="allow")
```

**Advantages**:
- ✅ **Full Control**: Complete implementation freedom in xeno-agent context
- ✅ **Workspace Awareness**: Can prune based on xeno-agent's project structure
- ✅ **Fast Iteration**: No dependency on agentpool releases
- ✅ **Hybrid Approach**: Can still use agentpool steps when appropriate
- ✅ **Testing**: Test in actual xeno-agent environment

**Disadvantages**:
- ❌ **Not Shared**: Other agentpool users can't use xeno-agent steps
- ❌ **Potential Duplication**: May reimplement generic logic already in agentpool
- ❌ **Maintenance**: Need to maintain custom steps separately

**Evaluation Against Criteria**:

| Criterion | Score/Rating | Notes |
|-----------|--------------|-------|
| Token Savings | 9/10 | Same strategies, plus workspace-specific optimizations |
| Conversation Quality | 9/10 | Workspace-aware pruning preserves important files |
| Performance | 9/10 | No additional overhead |
| Correctness | 8/10 | Workspace-specific logic needs testing |
| Configurability | 8/10 | Custom steps need config |
| Observability | 7/10 | Need to add xeno-agent specific metrics |
| Implementation Effort | 7/10 | Custom implementation from scratch |
| Risk | 7/10 | Workspace assumptions may not always hold |
| **Average** | **8.1** | |

**Effort Estimate**: 1.5-2 weeks
- Week 1: Implement xeno-agent specific steps, workspace-aware logic
- Week 2: Testing, integration with hook system, metrics

**Risk Assessment**:
- **Medium**: Workspace assumptions may not hold for all projects
- **Mitigation**: Make preserve_patterns highly configurable
- **Low-Medium**: Testing complexity in xeno-agent environment

---

### Recommendation (Updated)

**Recommended Approach**: **Option A (Agentpool Extensions) for Core DCP, with Option C for Xeno-Agent Specific Enhancements**

**Two-Tier Strategy**:

1. **Tier 1: Core DCP in Agentpool** (Minimal, Shared)
   - Implement `DeduplicateToolCalls`, `SupersedeWriteInputs`, `PurgeFailedToolInputs` in agentpool
   - Benefits all agentpool users
   - Well-tested, maintained upstream

2. **Tier 2: Xeno-Agent Enhancements** (Specific, Optimized)
   - Implement `XenoWorkspacePruneStep`, `XenoBuildArtifactPruneStep` in xeno-agent
   - Workspace-aware, task-aware strategies
   - Combines with Tier 1 steps in pipeline

**Justification**:

1. **Core Functionality in Agentpool**:
   - General-purpose DCP strategies should be available to all users
   - Minimal maintenance burden on xeno-agent team
   - Leverages agentpool's proven CompactionPipeline infrastructure

2. **Xeno-Agent Customization**:
   - Workspace structure knowledge provides competitive advantage
   - Task-aware pruning enables smarter decisions
   - Fast iteration without upstream dependency

3. **Gradual Adoption**:
   - Start with Tier 1 (proven strategies from OpenCode)
   - Add Tier 2 optimizations based on real xeno-agent usage data
   - Can deprecate Tier 2 if it proves not valuable

4. **Risk Mitigation**:
   - If Tier 2 steps have bugs, Tier 1 strategies still work
   - Can disable Tier 2 via config
   - Clear separation of concerns (core vs. enhancement)

### Trade-offs Accepted

1. **Two-Layer Maintenance**: Splitting between agentpool and xeno-agent increases maintenance surface.
   - **Mitigation**: Clear ownership (agentpool owns Tier 1, xeno-agent owns Tier 2)
   - **Benefit**: xeno-agent has full control over optimizations

2. **Coordination Overhead**: Need to coordinate changes across two codebases.
   - **Mitigation**: Tier 2 adds to Tier 1, doesn't modify it
   - **Benefit**: xeno-agent can iterate independently

3. **Context Loss on Errors**: Aggressive pruning of failed inputs might remove context needed to understand syntax errors.
   - **Mitigation**: Only prune if error is generic; preserve partial content if error references line numbers.

4. **Workspace Assumptions**: Xeno-agent specific steps assume certain project structure.
   - **Mitigation**: Make preserve_patterns highly configurable
   - **Benefit**: Allows xeno-agent to optimize for its common patterns

### Scoring Summary

| Criterion | Option A | Option B | Option C | Updated (A+C) |
|-----------|-----------|-----------|-----------|----------------|
| Token Savings | 9 | 9 | 9 | **9.5** |
| Conversation Quality | 8 | 8 | 9 | **8.5** |
| Performance | 9 | 8 | 9 | **9** |
| Correctness | 8 | 8 | 8 | **8** |
| Configurability | 9 | 8 | 8 | **8.5** |
| Observability | 7 | 9 | 7 | **7** |
| Implementation Effort | 8 | 6 | 7 | **7.5** |
| Risk | 7 | 6 | 7 | **7** |
| **Average** | **8.1** | **7.8** | **8.1** | **8.1** |

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Request Flow                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  1. pre_run Hook (DCP Pruning Hook)              │
│     ├─ Check if DCP enabled                         │
│     ├─ Build CompactionPipeline                       │
│     └─ Apply pipeline to conversation history          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. CompactionPipeline Execution                   │
│     ├─ DeduplicateToolCalls                         │
│     │   └─ Group by signature, keep newest        │
│     ├─ SupersedeWriteInputs                         │
│     │   └─ Find writes covered by reads            │
│     ├─ PurgeFailedToolInputs                         │
│     │   └─ Remove old failed tool inputs            │
│     └─ (Optional: FilterThinking, KeepLastMessages)  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Placeholder Replacement                       │
│     ├─ For marked tool outputs:                      │
│     │   └─ Replace with "[Content pruned...]"     │
│     └─ For marked tool inputs:                       │
│         └─ Replace with "[Input removed...]"          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Update Conversation                          │
│     └─ agent.conversation.set_history(pruned_messages)│
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  5. LLM Request (with pruned history)              │
│     ├─ Pruned messages with placeholders            │
│     ├─ System prompt (optional pruning instructions)   │
│     └─ Prunable-tools list (if configured)          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Tool Execution (post_tool_use Hook)           │
│     ├─ Update tool cache                             │
│     ├─ Track turn count                              │
│     └─ LLM may call discard/extract                  │
└─────────────────────────────────────────────────────────────┘
```

### CompactionStep Implementation

```python
# src/agentpool/messaging/compaction.py (new additions)

from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, ToolReturnPart
from typing import Callable

class DeduplicateToolCalls(CompactionStep):
    """
    Remove duplicate tool calls, keeping only the newest.

    Strategy:
    1. Build signature for each tool (name + normalized params)
    2. Group by signature
    3. For each group, keep only the latest (highest index)
    4. Mark older duplicates for pruning
    """

    def __init__(
        self,
        protected_tools: list[str] | None = None,
        protected_files: list[str] | None = None,
        on_duplicate: str = "mark"  # "mark" | "remove"
    ):
        self.protected_tools = protected_tools or []
        self.protected_files = protected_files or []
        self.on_duplicate = on_duplicate

    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        pruned_ids = []
        signature_map: dict[str, list[int]] = {}

        # 1. Build tool index
        tool_index = self._build_tool_index(messages)

        # 2. Group by signature
        for idx, (msg, tool_info) in enumerate(tool_index):
            if tool_info is None:
                continue

            # Skip protected tools
            if tool_info["tool"] in self.protected_tools:
                continue

            # Skip protected files
            if self._is_protected_file(tool_info):
                continue

            # Create signature
            signature = self._create_signature(
                tool_info["tool"],
                tool_info["input"]
            )

            if signature not in signature_map:
                signature_map[signature] = []
            signature_map[signature].append(idx)

        # 3. Mark all but the newest in each group
        for signature, indices in signature_map.items():
            if len(indices) > 1:
                # Keep the last (newest), mark others
                indices_to_remove = indices[:-1]
                pruned_ids.extend(indices_to_remove)

        # 4. Apply placeholder replacement
        return self._apply_pruning(messages, tool_index, pruned_ids)

    def _build_tool_index(self, messages: list[ModelMessage]) -> list[tuple]:
        """Map message indices to tool call information."""
        index = []
        for msg in messages:
            if not isinstance(msg, ModelResponse):
                index.append((msg, None))
                continue

            # Look for ToolReturnPart
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    index.append((msg, {
                        "tool": part.tool_name,
                        "input": part.tool_args,
                        "output": part.content,
                        "call_id": getattr(part, "call_id", None),
                    }))
                    break
            else:
                index.append((msg, None))

        return index

    def _create_signature(self, tool: str, params: dict) -> str:
        """Create normalized signature for deduplication."""
        # Normalize: remove None values
        normalized = {k: v for k, v in params.items() if v is not None}

        # Sort keys for consistent ordering
        sorted_params = dict(sorted(normalized.items()))

        # Serialize
        return f"{tool}::{json.dumps(sorted_params, sort_keys=True)}"

    def _is_protected_file(self, tool_info: dict) -> bool:
        """Check if tool operates on protected file."""
        import fnmatch

        file_path = tool_info["input"].get("filePath") or tool_info["input"].get("path")
        if not file_path:
            return False

        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.protected_files)

    def _apply_pruning(
        self,
        messages: list[ModelMessage],
        tool_index: list[tuple],
        pruned_ids: list[int]
    ) -> list[ModelMessage]:
        """Apply placeholder replacement to pruned tools."""
        if not pruned_ids:
            return messages

        placeholder = "[Output removed to save context - duplicate tool call]"

        for msg_idx, (msg, tool_info) in enumerate(tool_index):
            if msg_idx not in pruned_ids:
                continue

            if tool_info is None:
                continue

            # Replace output with placeholder
            for part in msg.parts:
                if isinstance(part, ToolReturnPart) and part.tool_name == tool_info["tool"]:
                    part.content = placeholder
                    break

        return messages


class SupersedeWriteInputs(CompactionStep):
    """
    Remove write inputs that are covered by subsequent reads.

    Strategy:
    1. Track all write operations per file (with indices)
    2. Track all read operations per file (with indices)
    3. For each write, check if any read occurs after it
    4. If yes, the write input is redundant (current state is in read)
    """

    def __init__(self, write_tools: list[str] | None = None):
        self.write_tools = write_tools or ["write", "edit"]
        self.read_tools = ["read"]

    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        writes_by_file: dict[str, list[int]] = {}
        reads_by_file: dict[str, list[int]] = {}

        # 1. Build tool index
        tool_index = self._build_tool_index(messages)

        # 2. Track writes and reads
        for idx, (msg, tool_info) in enumerate(tool_index):
            if tool_info is None:
                continue

            file_path = tool_info["input"].get("filePath") or tool_info["input"].get("path")
            if not file_path:
                continue

            if tool_info["tool"] in self.write_tools:
                if file_path not in writes_by_file:
                    writes_by_file[file_path] = []
                writes_by_file[file_path].append(idx)

            elif tool_info["tool"] in self.read_tools:
                if file_path not in reads_by_file:
                    reads_by_file[file_path] = []
                reads_by_file[file_path].append(idx)

        # 3. Find writes covered by reads
        pruned_ids = []
        for file_path, write_indices in writes_by_file.items():
            read_indices = reads_by_file.get(file_path, [])

            for write_idx in write_indices:
                # Check if any read occurs after this write
                has_subsequent_read = any(read_idx > write_idx for read_idx in read_indices)
                if has_subsequent_read:
                    pruned_ids.append(write_idx)

        # 4. Apply placeholder replacement to write inputs
        return self._apply_pruning(messages, tool_index, pruned_ids, target="input")

    def _build_tool_index(self, messages: list[ModelMessage]) -> list[tuple]:
        """Same as DeduplicateToolCalls._build_tool_index"""
        # Implementation similar to above
        pass

    def _apply_pruning(
        self,
        messages: list[ModelMessage],
        tool_index: list[tuple],
        pruned_ids: list[int],
        target: str = "output"  # "input" | "output"
    ) -> list[ModelMessage]:
        """Apply placeholder replacement."""
        if not pruned_ids:
            return messages

        if target == "input":
            placeholder = "[Input removed to save context - superseded by read]"
        else:
            placeholder = "[Content removed to save context]"

        for msg_idx, (msg, tool_info) in enumerate(tool_index):
            if msg_idx not in pruned_ids:
                continue

            if tool_info is None:
                continue

            if target == "output":
                # For outputs (ToolReturnPart), we can simply replace content string
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart) and part.tool_name == tool_info["tool"]:
                        part.content = placeholder
                        break
            
            elif target == "input":
                # For inputs (ToolCallPart), we MUST preserve JSON schema
                # Do NOT replace the whole args dict with a string
                for part in msg.parts:
                    if isinstance(part, ToolCallPart) and part.tool_name == tool_info["tool"]:
                        args = part.args
                        if isinstance(args, dict):
                            # Selective field pruning
                            for key in ["content", "text", "code", "input"]:
                                if key in args and isinstance(args[key], str) and len(args[key]) > 100:
                                    args[key] = placeholder
                            part.args = args
                        break

        return messages


class PurgeFailedToolInputs(CompactionStep):
    """
    Remove inputs from failed tools after N turns.

    Strategy:
    1. Track turn count (messages with user inputs)
    2. Find tools with status="error"
    3. Check if turn age >= threshold
    4. Replace input with placeholder, keep error message
    """

    def __init__(self, turn_threshold: int = 4):
        self.turn_threshold = turn_threshold

    async def apply(self, messages: list[ModelMessage]) -> list[ModelMessage]:
        turn_count = 0
        tool_index = []

        # 1. Count turns and build tool index
        for msg in messages:
            if isinstance(msg, ModelRequest):
                # Check if user prompt
                if any(part for part in msg.parts if hasattr(part, 'content')):
                    turn_count += 1

            # Track tools
            if isinstance(msg, ModelResponse):
                for part in msg.parts:
                    if isinstance(part, ToolReturnPart):
                        tool_index.append({
                            "msg": msg,
                            "part": part,
                            "tool": part.tool_name,
                            "input": part.tool_args,
                            "output": part.content,
                            "error": getattr(part, 'error', None),
                            "turn": turn_count,
                        })

        # 2. Find failed tools past threshold
        pruned_items = []
        for item in tool_index:
            if item["error"]:
                turn_age = turn_count - item["turn"]
                if turn_age >= self.turn_threshold:
                    pruned_items.append(item)

        # 3. Apply placeholder to inputs
        for item in pruned_items:
            # Modify the ModelRequest that had the input
            # This requires tracking request-response pairs
            # For now, we'll mark the ToolReturnPart
            placeholder = "[Input removed due to failed tool call]"
            # Implementation needs more context
            pass

        return messages
```

### Hook Integration

```python
# src/agentpool/dcp/pruning_hook.py

from agentpool.hooks import Hook, HookResult, HookInput
from agentpool.messaging.compaction import (
    CompactionPipeline,
    DeduplicateToolCalls,
    SupersedeWriteInputs,
    PurgeFailedToolInputs,
)

class DCPPruningHook(Hook):
    """
    Hook to execute DCP pruning before each agent run.

    Integrates with agentpool's hook system to apply
    automated pruning strategies.
    """

    event = "pre_run"

    def __init__(self, config: dict):
        self.config = config
        self.session_stats = DCPStats()

    async def execute(self, input: HookInput) -> HookResult:
        """Execute pruning pipeline."""
        if not self.config.get("enabled", False):
            return HookResult(decision="allow")

        # Build pipeline from config
        steps = []

        if self.config.get("strategies", {}).get("deduplication", {}).get("enabled"):
            steps.append(DeduplicateToolCalls(
                protected_tools=self.config.get("protected_tools", []),
                protected_files=self.config.get("protected_files", []),
            ))

        if self.config.get("strategies", {}).get("supersede_writes", {}).get("enabled"):
            steps.append(SupersedeWriteInputs())

        if self.config.get("strategies", {}).get("purge_errors", {}).get("enabled"):
            steps.append(PurgeFailedToolInputs(
                turn_threshold=self.config.get("strategies", {}).get("purge_errors", {}).get("turn_threshold", 4)
            ))

        if not steps:
            return HookResult(decision="allow")

        # Apply pipeline
        pipeline = CompactionPipeline(steps=steps)
        current_history = input.agent.conversation.get_history()
        pruned_history = await pipeline.apply(current_history)

        # Update conversation
        input.agent.conversation.set_history(pruned_history)

        # Track stats
        # (implementation details for token counting)

        return HookResult(decision="allow")
```

### LLM-Driven Tools via ResourceProvider

The `discard` and `extract` tools are implemented as a **ResourceProvider**, enabling:
- Clean separation from CompactionSteps (strategies vs. tools)
- Access to AgentContext for conversation history manipulation
- Reusability across different agents via provider registration

```python
# src/agentpool/dcp/dcp_provider.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from agentpool.resource_providers import StaticResourceProvider
from agentpool.tools.base import Tool

if TYPE_CHECKING:
    from agentpool.agents.context import AgentContext


@dataclass
class DCPStats:
    """Track pruning statistics per session."""
    tokens_saved_session: int = 0
    tokens_saved_total: int = 0
    tools_pruned: int = 0
    extractions: int = 0


class DCPResourceProvider(StaticResourceProvider):
    """
    Resource provider for Dynamic Context Pruning tools.
    
    Provides `discard` and `extract` tools that allow the LLM to
    intelligently manage context by marking tool outputs for pruning.
    
    Unlike automated CompactionSteps that run before each request,
    these tools give the LLM agency to decide what to prune.
    """
    
    kind = "custom"
    
    def __init__(
        self,
        name: str = "dcp_tools",
        protected_tools: list[str] | None = None,
        protected_files: list[str] | None = None,
    ) -> None:
        super().__init__(name=name)
        self.protected_tools = protected_tools or [
            "task", "todowrite", "todoread", "discard", "extract",
            "write", "edit", "batch", "plan_enter", "plan_exit",
        ]
        self.protected_files = protected_files or []
        self._session_stats: dict[str, DCPStats] = {}
        
        # Register tools
        self.add_tool(self.create_tool(
            self._discard,
            name_override="discard",
            description_override=self._get_discard_description(),
        ))
        self.add_tool(self.create_tool(
            self._extract,
            name_override="extract",
            description_override=self._get_extract_description(),
        ))
    
    async def _discard(
        self,
        ctx: AgentContext,
        ids: list[str],
    ) -> str:
        """
        Mark tool outputs for removal without knowledge retention.
        
        Args:
            ctx: AgentContext with access to conversation history
            ids: First element is reason ('completion'|'noise'), rest are numeric IDs
        
        Returns:
            Summary of pruned outputs
        """
        if len(ids) < 2:
            return "Error: ids must contain reason followed by numeric IDs"
        
        reason = ids[0]
        numeric_ids = [int(id_str) for id_str in ids[1:]]
        
        # Build prunable tools index from conversation
        prunable_index = self._build_prunable_index(ctx)
        
        # Validate IDs
        validation_error = self._validate_ids(numeric_ids, prunable_index)
        if validation_error:
            return validation_error
        
        # Apply placeholder replacement
        tokens_saved = await self._apply_pruning(ctx, numeric_ids, prunable_index)
        
        # Update stats
        self._update_stats(ctx.session_id, tokens_saved, len(numeric_ids))
        
        return f"Pruned {len(numeric_ids)} tool outputs (~{tokens_saved} tokens saved)"
    
    async def _extract(
        self,
        ctx: AgentContext,
        ids: list[str],
        distillation: list[str],
    ) -> str:
        """
        Preserve distilled knowledge before removing tool outputs.
        
        Args:
            ctx: AgentContext with access to conversation history
            ids: Numeric ID strings from prunable-tools list
            distillation: Distilled knowledge for each ID (required, positional)
        
        Returns:
            Summary of extracted outputs
        """
        if not distillation or len(distillation) != len(ids):
            return "Error: distillation required with one string per ID"
        
        numeric_ids = [int(id_str) for id_str in ids]
        
        # Build prunable tools index
        prunable_index = self._build_prunable_index(ctx)
        
        # Validate IDs
        validation_error = self._validate_ids(numeric_ids, prunable_index)
        if validation_error:
            return validation_error
        
        # Apply placeholder replacement
        tokens_saved = await self._apply_pruning(ctx, numeric_ids, prunable_index)
        
        # Inject distillation as context (stored in message metadata)
        knowledge_summary = "\n".join([f"- {d}" for d in distillation])
        await self._inject_extracted_knowledge(ctx, knowledge_summary)
        
        # Update stats
        stats = self._get_session_stats(ctx.session_id)
        stats.extractions += len(ids)
        self._update_stats(ctx.session_id, tokens_saved, len(numeric_ids))
        
        return f"Extracted {len(numeric_ids)} tool outputs, preserving knowledge (~{tokens_saved} tokens saved)"
    
    def _build_prunable_index(self, ctx: AgentContext) -> dict[int, dict[str, Any]]:
        """Build index of prunable tool calls from conversation history."""
        from pydantic_ai.messages import ToolReturnPart
        
        index: dict[int, dict[str, Any]] = {}
        history = ctx.agent.conversation.get_history()
        counter = 0
        
        for msg in history:
            for model_msg in msg.messages:
                for part in model_msg.parts:
                    if isinstance(part, ToolReturnPart):
                        # Skip protected tools
                        if part.tool_name in self.protected_tools:
                            continue
                        # Skip protected files
                        if self._is_protected_file(part):
                            continue
                        
                        index[counter] = {
                            "tool_call_id": part.tool_call_id,
                            "tool_name": part.tool_name,
                            "part": part,
                            "message": msg,
                        }
                        counter += 1
        
        return index
    
    def _validate_ids(
        self, ids: list[int], prunable_index: dict[int, dict[str, Any]]
    ) -> str | None:
        """Validate IDs against prunable index. Returns error string or None."""
        for id_ in ids:
            if id_ not in prunable_index:
                return f"Error: Invalid ID {id_}. Not in prunable-tools list."
        return None
    
    async def _apply_pruning(
        self,
        ctx: AgentContext,
        ids: list[int],
        prunable_index: dict[int, dict[str, Any]],
    ) -> int:
        """Apply placeholder replacement to tool outputs. Returns tokens saved."""
        from agentpool.messaging.token_counter import count_tokens
        
        placeholder = "[Content pruned to save context - information superseded or no longer needed]"
        tokens_saved = 0
        
        for id_ in ids:
            entry = prunable_index[id_]
            part = entry["part"]
            
            # Count tokens before replacement
            if isinstance(part.content, str):
                tokens_saved += count_tokens(part.content)
            
            # Replace content with placeholder (mutate in place)
            # NOTE: This preserves message structure and tool_call_id linking
            part.content = placeholder
        
        return tokens_saved
    
    async def _inject_extracted_knowledge(self, ctx: AgentContext, knowledge: str) -> None:
        """Inject extracted knowledge as metadata in a system message."""
        from agentpool.messaging.messages import ChatMessage
        
        # Add extracted knowledge as metadata on a new message
        # This preserves the knowledge without cluttering conversation
        extraction_msg = ChatMessage(
            content=f"[Extracted Knowledge]\n{knowledge}",
            role="assistant",
            metadata={"dcp_extraction": True, "knowledge": knowledge},
        )
        ctx.agent.conversation.add_chat_messages([extraction_msg])
    
    def _is_protected_file(self, part: Any) -> bool:
        """Check if tool operates on a protected file."""
        import fnmatch
        
        # Try to extract file path from tool args
        if hasattr(part, "tool_args") and isinstance(part.tool_args, dict):
            file_path = part.tool_args.get("filePath") or part.tool_args.get("path")
            if file_path:
                return any(fnmatch.fnmatch(file_path, p) for p in self.protected_files)
        return False
    
    def _get_session_stats(self, session_id: str | None) -> DCPStats:
        """Get or create session stats."""
        key = session_id or "default"
        if key not in self._session_stats:
            self._session_stats[key] = DCPStats()
        return self._session_stats[key]
    
    def _update_stats(self, session_id: str | None, tokens: int, count: int) -> None:
        """Update session statistics."""
        stats = self._get_session_stats(session_id)
        stats.tokens_saved_session += tokens
        stats.tokens_saved_total += tokens
        stats.tools_pruned += count
    
    def _get_discard_description(self) -> str:
        return """Mark tool outputs for removal without knowledge retention.

Use when:
- Task is complete and old tool outputs are no longer needed
- Tool outputs are noise/debug information
- Information has been superseded by newer data

Args:
    ids: First element is reason ('completion' or 'noise'), followed by numeric IDs from prunable-tools list
    
Example: discard(ids=["completion", "5", "20", "21"])"""
    
    def _get_extract_description(self) -> str:
        return """Preserve distilled knowledge before removing tool outputs.

Use when:
- Important insights should be retained for future reference
- Key information from tool outputs is needed later
- 'Uncertain' about discarding - extract is safer

Args:
    ids: Numeric ID strings from prunable-tools list
    distillation: Array of strings, one per ID, containing distilled knowledge (required)
    
Example: extract(ids=["10", "11"], distillation=["auth.ts uses JWT with 5min TTL", "User model has permissions array"])"""
```

**Configuration via YAML:**

```yaml
# manifest.yml
agents:
  my_agent:
    model: openai:gpt-4o
    
    # Register DCP tools via resource provider
    resource_providers:
      - type: dcp_tools
        import_path: agentpool.dcp.dcp_provider.DCPResourceProvider
        config:
          protected_tools:
            - "task"
            - "todowrite"
            - "todoread"
            - "write"
            - "edit"
          protected_files:
            - "*.secret"
            - "*.env"
```

### Session Management and Stats Persistence

DCP statistics and session state are stored using a hybrid approach:

1. **In-Memory Stats** (per-agent-instance): `DCPResourceProvider._session_stats`
   - Fast access during agent execution
   - Tracks `tokens_saved_session`, `tools_pruned`, `extractions`

2. **Persistent Stats** (via ChatMessage.metadata): Stored in conversation history
   - Each extraction creates a message with `metadata={"dcp_extraction": True, "knowledge": ...}`
   - Survives session restarts when conversation is persisted

3. **Session Metadata** (via StorageManager): For cross-session statistics
   - Uses `StorageManager.replace_conversation_messages()` for compacted history
   - DCP stats can be attached to session metadata in storage providers

```python
# src/agentpool/dcp/session.py

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DCPStats:
    """Track pruning statistics per session."""
    tokens_saved_session: int = 0
    tokens_saved_total: int = 0
    tools_pruned: int = 0
    extractions: int = 0


@dataclass
class DCPSessionState:
    """Per-session DCP state."""
    session_id: str
    prune_tool_ids: list[str] = field(default_factory=list)
    stats: DCPStats = field(default_factory=DCPStats)
    current_turn: int = 0


class DCPSessionManager:
    """
    Manage DCP session state with multiple persistence options.
    
    Storage Options:
    1. In-memory: For single-agent, single-process scenarios
    2. ChatMessage.metadata: Attached to extraction messages in conversation
    3. Session metadata: Via StorageManager for cross-session persistence
    """

    def __init__(self, storage_manager: Any | None = None) -> None:
        self.storage_manager = storage_manager
        self._sessions: dict[str, DCPSessionState] = {}

    def get_session(self, session_id: str) -> DCPSessionState:
        """Get or create session state."""
        if session_id not in self._sessions:
            self._sessions[session_id] = DCPSessionState(session_id=session_id)
        return self._sessions[session_id]

    def mark_pruned(self, session_id: str, tool_call_ids: list[str]) -> None:
        """Mark tool calls as pruned."""
        session = self.get_session(session_id)
        session.prune_tool_ids.extend(tool_call_ids)

    def update_stats(self, session_id: str, tokens_saved: int, count: int) -> None:
        """Update pruning statistics."""
        session = self.get_session(session_id)
        session.stats.tokens_saved_session += tokens_saved
        session.stats.tokens_saved_total += tokens_saved
        session.stats.tools_pruned += count

    async def persist_to_storage(self, session_id: str) -> None:
        """
        Persist DCP state to storage manager.
        
        Stats are stored as session metadata, not in a separate file.
        This integrates with existing agentpool storage infrastructure.
        """
        if not self.storage_manager:
            return
        
        session = self.get_session(session_id)
        
        # Store in session metadata (provider-dependent)
        # SQL: dcp_stats column in sessions table
        # OpenCode: Additional field in session JSON
        # Claude: Metadata in session storage
        await self.storage_manager.update_session_metadata(
            session_id=session_id,
            metadata={
                "dcp_stats": {
                    "tokens_saved_total": session.stats.tokens_saved_total,
                    "tools_pruned": session.stats.tools_pruned,
                    "extractions": session.stats.extractions,
                },
                "dcp_prune_ids": session.prune_tool_ids,
            }
        )

    async def load_from_storage(self, session_id: str) -> DCPSessionState | None:
        """Load DCP state from storage manager."""
        if not self.storage_manager:
            return None
        
        metadata = await self.storage_manager.get_session_metadata(session_id)
        if not metadata or "dcp_stats" not in metadata:
            return None
        
        dcp_data = metadata["dcp_stats"]
        session = DCPSessionState(
            session_id=session_id,
            prune_tool_ids=metadata.get("dcp_prune_ids", []),
            stats=DCPStats(
                tokens_saved_total=dcp_data.get("tokens_saved_total", 0),
                tools_pruned=dcp_data.get("tools_pruned", 0),
                extractions=dcp_data.get("extractions", 0),
            ),
        )
        self._sessions[session_id] = session
        return session
```

**Storage Location Summary:**

| Data | Storage Location | Persistence |
|------|------------------|-------------|
| `prune_tool_ids` | Session metadata (via StorageManager) | Cross-restart |
| `stats.tokens_saved_*` | Session metadata | Cross-restart |
| Extracted knowledge | `ChatMessage.metadata` | With conversation |
| Tool parameter cache | In-memory (rebuilt from messages) | Per-request |

### Configuration Schema

```python
# src/agentpool_config/dcp.py (new file)

from pydantic import BaseModel, Field
from typing import list, dict

class DCPPurgeErrorsConfig(BaseModel):
    enabled: bool = True
    turn_threshold: int = 4

class DCPSupersedeWritesConfig(BaseModel):
    enabled: bool = True

class DCPDeduplicationConfig(BaseModel):
    enabled: bool = True
    protected_tools: list[str] = []

class DCPStrategiesConfig(BaseModel):
    deduplication: DCPDeduplicationConfig = Field(default_factory=DCPDeduplicationConfig)
    supersede_writes: DCPSupersedeWritesConfig = Field(default_factory=DCPSupersedeWritesConfig)
    purge_errors: DCPPurgeErrorsConfig = Field(default_factory=DCPPurgeErrorsConfig)

class DCPConfig(BaseModel):
    enabled: bool = False
    protected_tools: list[str] = Field(
        default_factory=lambda: ["task", "todowrite", "todoread", "write", "edit"]
    )
    protected_files: list[str] = Field(default_factory=list)
    turn_protection: dict[str, int] = Field(default_factory=lambda: {"enabled": True, "turns": 2})
    strategies: DCPStrategiesConfig = Field(default_factory=DCPStrategiesConfig)
    prune_notification: str = "minimal"  # off, minimal, detailed
```

## Implementation Plan

### Part 1: Agentpool Extensions (Minimal, Reusable)

**Goal**: Add DCP infrastructure to agentpool core for all users.

**Phase 1.1: Core CompactionSteps (Week 1)**

**Tasks**:
1. Implement `DeduplicateToolCalls` CompactionStep
   - Build tool index from ModelMessage list
   - Signature creation with normalization
   - Placeholder replacement logic

2. Implement `SupersedeWriteInputs` CompactionStep
   - Track writes and reads per file using `tool_call_id`
   - Detect writes covered by reads
   - Selective field pruning for inputs

3. Implement `PurgeFailedToolInputs` CompactionStep
   - Track turn count
   - Find failed tools past threshold
   - Safety check for error messages
   - Replace heavy fields with placeholder

4. Add unit tests for each step
   - Test with realistic tool call sequences
   - Verify protected tools/files are skipped
   - Validate placeholder format

**Dependencies**: None

**Success Criteria**:
- All three steps pass unit tests
- Steps integrate with existing CompactionPipeline
- Placeholder replacement preserves message structure
- Selective field pruning maintains JSON schema

---

**Phase 1.2: Configuration Schema (Week 1)**

**Tasks**:
1. Create `agentpool_config/dcp.py`
   - `DCPConfig` pydantic model
   - Merge with existing agent config

2. Add YAML manifest support
   - Parse `dcp` section from manifest
   - Auto-register hooks and tools

**Dependencies**: None

**Success Criteria**:
- Configuration loaded from YAML
- Hooks/tools auto-registered

---

**Phase 1.3: Token Counting Utility (Week 1)**

**Tasks**:
1. Add token counting helper
   - Use agentpool's existing `MessageHistory.get_history_tokens()`
   - Calculate tokens saved by pruning
   - Reusable utility function

**Dependencies**: None

**Success Criteria**:
- Token counting accurate
- Utility reusable across contexts

---

### Part 2: Xeno-Agent Core Extensions

**Goal**: Xeno-Agent specific DCP integration with resource providers.

**Phase 2.1: Session Persistence (Week 2)**

**Tasks**:
1. Create `xeno_agent/dcp/storage.py`
   - `DCPStorage` class using agentpool's `StorageManager`
   - Persist/load session state (prune_tool_ids, stats)

2. Integrate with resource providers
   - Use existing storage providers (SQLSessionStore, FileStorage)
   - Session metadata persistence

**Dependencies**: Phase 1 completion

**Success Criteria**:
- Session state persisted to storage
- Load correctly on resume

---

**Phase 2.2: Hook Registration (Week 2)**

**Tasks**:
1. Create `xeno_agent/dcp/pruning_hook.py`
   - `DCPPruningHook` class for pre_run hook
   - Build and execute CompactionPipeline
   - Update conversation history

2. Add to xeno-agent manifest
   ```yaml
   # xeno_agent/manifest.yml
   agents:
     my_agent:
       hooks:
         pre_run:
           - type: callable
             import_path: xeno_agent.dcp.pruning_hook
       tools:
         discard:
           type: callable
           import_path: xeno_agent.dcp.tools.discard
         extract:
           type: callable
           import_path: xeno_agent.dcp.tools.extract
   ```

**Dependencies**: Phase 1.2

**Success Criteria**:
- Hook executes on agent.run()
- Tools accessible to LLM

---

**Phase 2.3: LLM-Driven Tools (Week 2)**

**Tasks**:
1. Implement `xeno_agent/dcp/tools/discard.py`
   - Validation of IDs
   - Check protected tools/files
   - Placeholder application
   - Token counting
   - Notification sending

2. Implement `xeno_agent/dcp/tools/extract.py`
   - Validation of IDs
   - Distillation required check
   - Knowledge injection via ignored message
   - Token counting
   - Notification sending

**Dependencies**: Phase 2.2

**Success Criteria**:
- Tools accessible to LLM
- Validation and protection working
- Notifications sent correctly

---

**Phase 2.4: Diagnostics and Observability (Week 2-3)**

**Tasks**:
1. Add diagnostic commands
   - `/dcp context` - current session stats
   - `/dcp stats` - cumulative stats
   - `/dcp help` - available commands

2. Add logging
   - Debug mode for troubleshooting
   - Trace pruning decisions
   - Performance metrics

3. Update session stats
   - Track tokens saved per session
   - Track total savings across sessions
   - Integrate with `DCPStorage`

**Dependencies**: Phase 2.1, Phase 2.3

**Success Criteria**:
- Commands work via agentpool command system
- Logging provides visibility
- Stats persisted correctly

---

**Phase 2.5: Xeno-Agent Specific Strategies (Week 3)**

**Tasks**:
1. Add xeno-agent specific strategies
   - File-aware pruning (workspace structure)
   - Task-aware pruning (integrate with task system)
   - Custom protection rules

2. Custom DCP config for xeno-agent
   - Workspace-based file protection
   - Task-related tool protection

**Dependencies**: Phase 2.2

**Success Criteria**:
- Xeno-Agent specific pruning working
- Custom rules effective

---

### Phase 3: Testing and Documentation (Week 3)

**Goal**: Ensure reliability and provide user documentation.

**Tasks**:
1. Integration testing
   - Test with long-running agents
   - Verify conversation quality
   - Measure token savings

2. Performance testing
   - Measure pipeline overhead
   - Test with 200+ message histories
   - Validate <50ms target

3. Documentation
   - User guide for configuration
   - API documentation for CompactionSteps
   - Troubleshooting guide
   - Xeno-Agent specific usage

4. Examples
   - Sample YAML configurations
   - Example agent with DCP enabled
   - Before/after token usage comparison

**Dependencies**: All previous phases

**Success Criteria**:
- All integration tests pass
- Documentation complete
- Performance targets met

---

### Dependencies

- **Agentpool Core**: MessageHistory, CompactionPipeline, hook system
- **Pydantic-AI**: ModelMessage structure, Part types
- **Configuration**: Pydantic models, YAML parsing
- **Storage**: StorageManager for session persistence
- **Xeno-Agent**: Task system, workspace structure

---

### Rollback Strategy

If issues arise during deployment:

1. **Disable via Config**: Set `dcp.enabled: false` in manifest
2. **Remove Hook**: Delete pre_run hook registration
3. **Revert Changes**: Git revert to pre-DCP commit
4. **Rollback Part 1**: Separate revert for agentpool changes if needed

## Open Questions

### Part 1: Agentpool Extensions (Option A)

1. **Request-Response Tracking for `SupersedeWriteInputs`**: 
   - **Question**: Can we reliably track the link between a `ToolCallPart` (in `ModelRequest`) and its corresponding `ToolReturnPart` (in `ModelResponse`)?
   - **Current Proposal**: Use `tool_call_id` field provided by pydantic-ai to link writes and reads
   - **Risk**: If tool calls are batched or interleaved, simple sequential matching may fail
   - **Decision Needed**: Can we rely on `tool_call_id` being set consistently?

2. **Placeholder Schema Enforcement**:
   - **Question**: How do we ensure placeholder strings don't break pydantic-ai's validation for function arguments?
   - **Current Proposal**: Implement **selective field pruning**. Instead of replacing entire object, replace only heavy fields (e.g., `content`, `text`) with placeholder strings, while preserving metadata fields (e.g., `path`, `filename`).
   - **Open**: Is selective field pruning (only modifying `content`, `text`, `code` fields inside the JSON) sufficient?

3. **Token Counting Integration**:
   - **Question**: Should we add DCP-specific token counting or reuse agentpool's existing mechanism?
   - **Current Proposal**: Use `MessageHistory.get_history_tokens()` for baseline, add `calculate_tokens_saved()` utility
   - **Risk**: Need to accurately measure tokens saved without double-counting
   - **Decision Needed**: Should we expose token counting API in `CompactionStep` base class?

4. **Async Pipeline Behavior**:
   - **Question**: Is `CompactionPipeline.apply()` blocking or does it integrate well with agentpool's async flow?
   - **Observation**: Current code shows `async def apply()`, so it's already async
   - **Decision**: No architectural changes needed (documentation update only)

5. **Config Schema Location**:
   - **Question**: Should `DCPConfig` be in `agentpool_config/dcp.py` (shared) or `xeno_agent/dcp/config.py` (xeno-specific)?
   - **Current Proposal**: Core schema in agentpool, xeno-specific extensions in xeno_agent
   - **Open**: Where should xeno-agent specific config (workspace patterns, task awareness) live?

### Part 2: Xeno-Agent Specific Integration (Option C)

6. **Workspace Pruning Safety**:
   - **Question**: Xeno-agent's workspace structure varies by project. How do we ensure workspace-based pruning doesn't accidentally remove important files?
   - **Current Proposal**: Configurable `preserve_patterns` with sensible defaults
   - **Risk**: Default patterns may not match all project structures
   - **Decision Needed**: Should we learn patterns from git history or require explicit configuration?

7. **Task State Awareness**:
   - **Question**: Xeno-agent uses task graphs. How should DCP interact with task lifecycle?
   - **Current Proposal**: Task-aware pruning (prune intermediate steps, preserve task results)
   - **Complexity**: Need to understand task state without adding heavy dependency
   - **Decision Needed**: Should we integrate with task metadata or keep it simple?

8. **Hybrid Pipeline Coordination**:
   - **Question**: How do we coordinate between agentpool steps (Tier 1) and xeno-agent steps (Tier 2)?
   - **Current Proposal**: Tier 2 wraps and extends Tier 1 pipeline
   - **Risk**: Execution order and state conflicts between tiers
   - **Decision Needed**: Should xeno-agent steps run before, after, or interleaved with agentpool steps?

9. **Resource Provider Schema**:
   - **Question**: DCP needs to persist session state. Should we add tables to SQLSessionStore or use file-based storage?
   - **Current Proposal**: Extend storage schema with `dcp_state` column or use separate file per session
   - **Decision Needed**: Does xeno-agent need cross-session persistence or is per-session sufficient?

10. **Two-Layer Maintenance**:
    - **Question**: Splitting logic between agentpool and xeno-agent increases maintenance burden. How do we minimize duplication?
    - **Current Proposal**: Tier 1 provides core, Tier 2 provides xeno-specific enhancements
    - **Open**: Is this separation worth the maintenance overhead?

## Decision Record

**Status**: Pending review

**Date**: Not yet decided

**Approvers**: TBD

---

## Appendices

### Appendix A: Token Counting Reference

OpenCode DCP uses `@anthropic-ai/tokenizer`. Agentpool should use its existing mechanism in `MessageHistory.get_history_tokens()`.

### Appendix B: Placeholder Schema

To ensure consistency and parseability by the LLM, placeholders follow a structured XML-like format.

```python
# Standard Template
PLACEHOLDER_TEMPLATE = "<{action} pruned='{reason}' original_length={length} />"

# Examples
PLACEHOLDER_OUTPUT_PRUNED = "<content_pruned reason='superseded' />"
PLACEHOLDER_INPUT_PRUNED = "<input_pruned reason='superseded_by_read' />"
PLACEHOLDER_INPUT_FAILED = "<input_pruned reason='failed_tool_call' />"
PLACEHOLDER_DUPLICATE = "<content_pruned reason='duplicate_tool_call' />"
```

### Appendix C: Protected Tools (Default)

```python
DEFAULT_PROTECTED_TOOLS = [
    "task",
    "todowrite",
    "todoread",
    "discard",
    "extract",
    "batch",
    "write",
    "edit",
    "plan_enter",
    "plan_exit",
]
```

### Appendix D: Configuration Example

```yaml
# .agentpool/manifest.yml
agents:
  my_agent:
    model: openai:gpt-4o

    # Enable DCP
    dcp:
      enabled: true

      # Tools never to prune
      protected_tools:
        - "task"
        - "todowrite"
        - "todoread"
        - "write"
        - "edit"

      # File patterns to protect
      protected_files:
        - "*.secret"
        - "*.env"
        - "config/*.json"

      # Turn-based protection
      turn_protection:
        enabled: true
        turns: 2

      # Automated strategies
      strategies:
        deduplication:
          enabled: true
          protected_tools: []  # Additional per-strategy tools
        supersede_writes:
          enabled: true
        purge_errors:
          enabled: true
          turn_threshold: 4

      # Notification level
      prune_notification: "minimal"  # off, minimal, detailed

    # DCP hooks registered automatically
    hooks:
      pre_run:
        - type: callable
          import_path: agentpool.dcp.pruning_hook.DCPPruningHook

    # LLM-driven tools
    tools:
      discard:
        type: callable
        import_path: agentpool.dcp.tools.discard
      extract:
        type: callable
        import_path: agentpool.dcp.tools.extract

    # Optional: Combine with existing compaction
    compaction:
      steps:
        - type: filter_thinking
        - type: deduplicate  # New DCP step
        - type: supersede_writes  # New DCP step
        - type: purge_errors  # New DCP step
        - type: keep_last
          count: 10
```
