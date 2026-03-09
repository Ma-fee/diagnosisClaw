# RFC-0002: Skill Support for Delegation Subagent Creation

---

## Header Metadata

| Field | Value |
|-------|-------|
| **rfc_id** | RFC-0002 |
| **title** | Skill Support for Delegation Subagent Creation |
| **status** | DRAFT |
| **author** | @explore-agent, Claude |
| **reviewers** | TBD |
| **created** | 2026-03-08 |
| **last_updated** | 2026-03-08 |
| **decision_date** | TBD |
| **related_rfc** | RFC-0001 (Zed ACP Elicitation) |

---

## Overview

This RFC proposes extending the delegation task tool provider to support creating subagents with skill instructions. Currently, when an agent delegates a task to a subagent via the `task` (or `new_task`) tool, the subagent receives only the task prompt without any specialized skill instructions. This limits the subagent's ability to leverage domain-specific knowledge, best practices, or specialized workflows that could enhance task execution.

The implementation will allow users to optionally specify a list of skills when creating a subagent. These skills will be injected into the subagent's context using skill instruction files (similar to how agentpool's `SkillsInstructionProvider` injects skills into main agents). This enables specialized subagents to inherit expertise without requiring every skill to be explicitly described in the prompt.

**Expected Outcome**: Subagents created via delegation can optionally receive skill instructions that enhance their capabilities for specialized tasks, improving response quality and consistency.

---

## Background & Context

### Current State of Delegation in AgentPool

AgentPool provides a delegation infrastructure through the `SubagentTools` provider located at:
- `/packages/agentpool/src/agentpool_toolsets/builtin/subagent_tools.py`

This provider exposes the `task()` tool which creates subagents with these parameters:
- `agent_or_team`: Target agent/team identifier
- `prompt`: Task description for the subagent
- `description`: Optional task description
- `async_mode`: Whether to run asynchronously

The subagent creation flow (lines 329-365 in subagent_tools.py):
```python
# Generate session IDs for parent-child relationship
child_session_id = identifier.ascending("session")
parent_session_id = ctx.node.session_id or identifier.ascending("session")

# Emit spawn event for observability
spawn_event = SpawnSessionStart(...)

# Run the subagent via streaming
return await _stream_task(
    ctx,
    source_name=agent_or_team,
    source_type=source_type,
    stream=node.run_stream(prompt, session_id=child_session_id, parent_session_id=parent_session_id),
    ...
)
```

### Current State of Delegation in Xeno-Agent

Xeno-Agent extends AgentPool's delegation system with `XenoDelegationProvider` at:
- `/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`

This provider offers two tools:
1. `new_task`: For parent agents to delegate tasks
2. `attempt_completion`: For subagents to return results

Current `new_task` parameters (lines 152-158):
```python
async def new_task(
    self,
    ctx: AgentContext,
    mode: str,
    message: str,
    expected_output: str,
) -> str:
```

The tool formats the prompt (line 221):
```python
formatted_prompt = f"<task>\n{target_task}\n</task>\n\n<expected_output>\n{target_expected_output}\n</expected_output>"
```

### Existing Skill Infrastructure

AgentPool maintains a comprehensive skill system:

**Skill Discovery & Registry**:
- `SkillsManager` (/packages/agentpool/src/agentpool/skills/manager.py): Pool-wide skill registry
- `SkillsRegistry` (/packages/agentpool/src/agentpool/skills/registry.py): Discovers skills from `~/.claude/skills/` and `.claude/skills/`
- `Skill` model (/packages/agentpool/src/agentpool/skills/skill.py): Lazy-loaded instruction content

**Skill Injection**:
- `SkillsInstructionProvider` (/packages/agentpool/src/agentpool/resource_providers/skills_instruction.py): Injects skills as XML-formatted instructions into ALL agent system prompts
- Supports two modes: "metadata" (names/descriptions) or "full" (complete instructions)

**Runtime Skill Loading**:
- `load_skill()` tool (/packages/agentpool/src/agentpool_toolsets/builtin/skills.py): Allows agents to load skills dynamically

### The Gap

Currently, skills are only injected into main agents via `SkillsInstructionProvider`. When a subagent is created via delegation:
1. No skills are passed to the subagent
2. The subagent must rely solely on its system prompt and the task description
3. Specialized knowledge must be manually included in each task prompt

### External Context

This RFC addresses a common pattern in multi-agent systems where specialized subagents benefit from domain knowledge without requiring that knowledge to be encoded in the main agent's prompts. Similar to how human teams assign specialists with domain expertise, agents should be able to delegate with skill context.

---

## Problem Statement

### The Problem

1. **Limited Subagent Specialization**: When delegating to specialized subagents (e.g., "code_reviewer", "test_writer", "security_analyst"), the parent agent must include all relevant context in the task prompt. This leads to:
   - Verbose, repetitive prompts
   - Inconsistent application of best practices
   - Knowledge duplication across delegation calls

2. **Skills Not Inherited**: AgentPool's skill system is designed for main agents. Subagents created via delegation do not benefit from skill injection, even though they may need the same specialized knowledge.

3. **Manual Skill Management**: Developers must manually craft skill-like instructions in task prompts or maintain separate system prompts for every subagent type, reducing the utility of the skill system.

### Evidence

- **Current Delegation Flow**: Review of `subagent_tools.py` (lines 261-400) shows no skill injection mechanism
- **Skill System Design**: `SkillsInstructionProvider` only operates during main agent initialization, not subagent spawning
- **Configuration Pattern**: Xeno-Agent's `diag-agent.yaml` shows skills are configured at main agent level only

### Impact of Not Solving

| Aspect | Impact |
|--------|--------|
| **Developer Experience** | Must manually include skill context for every delegation |
| **Response Quality** | Subagents lack domain expertise without verbose prompts |
| **Maintainability** | Skill changes require updating all delegation tasks |
| **Consistency** | No standardized way to apply skills to subagents |

---

## Goals & Non-Goals

### Goals

1. **Skill Injection for Subagents**: Enable optional skill instruction injection when creating subagents via delegation
2. **Skill Name Parameter**: Support specifying skills by name (e.g., `["git", "python", "testing"]`)
3. **Backward Compatibility**: Existing delegation calls work unchanged
4. **Pool-Level Skill Access**: Subagents can access skills from the parent pool's `SkillsManager`
5. **Flexible Injection**: Support different injection points (prompt, system prompt, or context)

### Non-Goals

1. **Dynamic Skill Loading**: Not implementing runtime skill loading (use existing `load_skill` tool)
2. **Skill Inheritance**: Not implementing automatic inheritance of parent agent skills (explicit opt-in only)
3. **Skill Modification**: Not allowing modification of skill content during delegation
4. **Custom Skill Sources**: Not supporting skill sources beyond the pool-level `SkillsManager`
5. **Cross-Pool Skills**: Not supporting skills from other agent pools

### Success Criteria

| Criterion | Measure |
|-----------|---------|
| Skill Injection | Subagent receives specified skill instructions |
| Backward Compatibility | Existing delegation calls without skills parameter work identically |
| Skill Resolution | Invalid skill names result in clear error messages |
| Performance | Skill injection adds < 50ms to delegation setup |

---

## Evaluation Criteria

The following criteria will be used to evaluate implementation options:

| Criterion | Weight | Description | Minimum Threshold |
|-----------|--------|-------------|-------------------|
| **Implementation Complexity** | High (30%) | Effort required across agentpool and xeno-agent layers | No breaking changes to core agentpool |
| **Backward Compatibility** | High (25%) | Existing delegation calls must work unchanged | 100% backward compatible |
| **Flexibility** | Medium (20%) | Ability to customize skill injection per delegation | Support multiple injection modes |
| **Maintainability** | Medium (15%) | Code clarity and future extension ease | Follow existing patterns |
| **Performance** | Low (10%) | Delegation setup overhead | < 50ms additional latency |

---

## Options Analysis

### Option 1: AgentPool Core Extension (RECOMMENDED)

**Description**: Extend AgentPool's `SubagentTools.task()` method to accept an optional `skills` parameter and handle skill injection at the core level.

**Advantages**:
- Centralized skill injection logic
- All users of AgentPool delegation benefit (not just xeno-agent)
- Consistent with existing `SkillsInstructionProvider` patterns
- Can leverage pool's `SkillsManager` directly in `_stream_task()`
- Clean API: `task(agent_or_team, prompt, description, async_mode, skills=["git", "python"])`

**Disadvantages**:
- Requires changes to agentpool core library
- Pushes xeno-agent-specific concerns into core
- Longer release cycle for agentpool

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Implementation Complexity | 6/10 | Core changes required, but pattern exists |
| Backward Compatibility | 10/10 | Optional parameter, no breaking changes |
| Flexibility | 7/10 | Core can support multiple injection modes |
| Maintainability | 8/10 | Centralized, follows existing patterns |
| Performance | 9/10 | Direct access to pool's skills registry |
| **Weighted Total** | **7.6/10** | |

**Effort Estimate**: 3-4 weeks (including agentpool core review and release)

**Risk Assessment**: Low-Medium - Follows established patterns, but requires coordination with agentpool maintainers

---

### Option 2: Xeno-Agent Layer Extension

**Description**: Extend `XenoDelegationProvider` to support a `skills` parameter. Skills are fetched from the pool's `SkillsManager` and injected into the formatted prompt before calling `node.run_stream()`.

**Advantages**:
- No changes to agentpool core required
- Faster iteration in xeno-agent
- Skill injection can be customized for xeno-agent's specific needs
- Can prototype and refine before pushing to core

**Disadvantages**:
- Only xeno-agent benefits
- Skill injection logic duplicated if other agents need similar 
- Potential divergence from core patterns
- Must access pool.skills via ctx.pool (less direct than core)

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Implementation Complexity | 8/10 | No core changes, but may need workarounds |
| Backward Compatibility | 10/10 | Optional parameter in new_task tool |
| Flexibility | 8/10 | Full control over injection in xeno-agent layer |
| Maintainability | 6/10 | Duplicated logic, divergence risk |
| Performance | 8/10 | Slightly less efficient skill resolution |
| **Weighted Total** | **8.0/10** | |

**Effort Estimate**: 2-3 weeks

**Risk Assessment**: Low - Self-contained, no external dependencies

---

### Option 3: Hybrid Two-Phase Approach

**Description**: Implement in xeno-agent layer as Phase 1 (immediate value), then migrate to agentpool core as Phase 2 (long-term).

**Advantages**:
- Immediate value with xeno-agent extension
- Validated design before core implementation
- Risk mitigation through prototyping
- Can gather feedback before committing to core changes

**Disadvantages**:
- Double implementation effort
- Temporary divergence from preferred architecture
- Migration work required in Phase 2

**Evaluation Against Criteria**:

| Criterion | Score | Notes |
|-----------|-------|-------|
| Implementation Complexity | 5/10 | Two implementations, migration work |
| Backward Compatibility | 10/10 | Maintained throughout |
| Flexibility | 8/10 | Prototyping allows refinement |
| Maintainability | 5/10 | Temporary duplication, cleanup needed |
| Performance | 8/10 | Same as Option 2 initially |
| **Weighted Total** | **7.2/10** | |

**Effort Estimate**: 5-6 weeks total (2-3 weeks Phase 1 + 3 weeks Phase 2)

**Risk Assessment**: Low overall - Prototyping reduces core change risk

---

## Recommendation

**Recommended Option**: **Option 2 - Xeno-Agent Layer Extension**

### Justification

Based on the evaluation criteria, Option 2 scores highest (8.0/10) primarily due to:

1. **Lower Implementation Complexity**: No need to modify agentpool core, avoiding coordination overhead and release dependency
2. **Rapid Value Delivery**: Can ship within 2-3 weeks vs 3-4 weeks for core changes
3. **Iteration Flexibility**: Allows xeno-agent to experiment with injection patterns before standardizing
4. **Minimal Risk**: Self-contained changes with no impact on other AgentPool users

The slight reduction in maintainability (6/10 vs 8/10 for core) is acceptable given:
- Xeno-agent is the primary consumer of this feature currently
- Skill injection logic is relatively small (~50-100 lines)
- Can always migrate to core later if other users need it
- The abstraction via `ctx.pool.skills` is stable

### Trade-offs Being Accepted

- **Limited Scope**: Only xeno-agent benefits initially (acceptable given current requirements)
- **Potential Duplication**: If other packages need similar, may need to extract common utility
- **Abstraction Dependency**: Relies on `ctx.pool.skills` interface remaining stable

### Alternative Consideration

Option 1 (Core Extension) should be reconsidered if:
- AgentPool maintainers confirm willingness to accept this feature
- The skill injection pattern proves stable in xeno-agent
- Other packages express need for subagent skill support

At that point, xeno-agent's implementation can serve as a reference for the core migration.

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Delegation With Skills                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────┐        ┌─────────────────────────────────────┐ │
│  │   Parent Agent          │        │   XenoDelegationProvider            │ │
│  │                         │        │   (delegation_provider.py)          │ │
│  │  Calls:                 │        │                                     │ │
│  │  new_task(              │───────▶│  1. Fetch skills from               │ │
│  │    mode="code_reviewer",│        │     ctx.pool.skills                 │ │
│  │    message="Review PR", │        │                                     │ │
│  │    expected_output="...",│       │  2. Format skill instructions       │ │
│  │    skills=["git",       │        │     as XML                          │ │
│  │            "python"]    │        │                                     │ │
│  │  )                      │        │  3. Prepend to formatted_prompt     │ │
│  └─────────────────────────┘        │                                     │ │
│                                     └──────────────────┬──────────────────┘ │
│                                                        │                    │
│                                     ┌──────────────────▼──────────────────┐ │
│                                     │   Formatted Prompt                   │ │
│                                     │                                      │ │
│                                     │   <skills>                           │ │
│                                     │     <skill name="git">...              │ │
│                                     │     <skill name="python">...           │ │
│                                     │   </skills>                          │ │
│                                     │   <task>Review PR...</task>          │ │
│                                     │   <expected_output>...</expected_    │ │
│                                     │   output>                            │ │
│                                     └──────────────────┬──────────────────┘ │
│                                                        │                    │
│                                     ┌──────────────────▼──────────────────┐ │
│                                     │   Subagent (code_reviewer)           │ │
│                                     │                                      │ │
│                                     │   Receives skill instructions        │ │
│                                     │   + task context                     │ │
│                                     │                                      │ │
│                                     └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Data Structures

#### Enhanced new_task Tool Parameters

```python
# Current signature (line 152-158 in delegation_provider.py)
async def new_task(
    self,
    ctx: AgentContext,
    mode: str,
    message: str,
    expected_output: str,
) -> str

# Enhanced signature with skills parameter
async def new_task(
    self,
    ctx: AgentContext,
    mode: str,
    message: str,
    expected_output: str,
    skills: list[str] | None = None,  # NEW: Optional list of skill names
) -> str
```

#### Skill Instruction Format

Skill instructions follow AgentPool's lazy-loading pattern and include the skill's base directory for file reference resolution:

```xml
<skills>
  <skill name="{skill_name}" base="{skill_path}">
    <description>{skill_description}</description>
    <instructions>
{skill_instruction_content}
    </instructions>
  </skill>
  ...
</skills>
```

**Format Notes**:
- **`base` attribute**: Path to the skill directory (e.g., `/Users/.../.claude/skills/git/`), not the project root. This allows subagents to resolve `@path` references within skill files correctly.
- **Lazy Loading**: AgentPool's `Skill.load_instructions()` method lazy-loads content from `SKILL.md` only when first accessed, then caches the result.
- **Frontmatter Handling**: The `SKILL.md` file contains YAML frontmatter (separated by `---`) and markdown body. Only the body (instructions) is injected.

### Backend Implementation

#### XenoDelegationProvider Extension

In `/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`:

```python
async def new_task(
    self,
    ctx: AgentContext,
    mode: str,
    message: str,
    expected_output: str,
    skills: list[str] | None = None,  # NEW parameter
) -> str:
    # ... existing validation code ...
    
    # Fetch and format skill instructions
    skills_content = ""
    if skills and ctx.pool and hasattr(ctx.pool, 'skills'):
        skills_content = await self._format_skills_instructions(
            ctx.pool.skills, skills
        )
    
    # Format prompt with skills prepended
    if skills_content:
        formatted_prompt = f"{skills_content}\n\n<task>\n{target_task}\n</task>\n\n<expected_output>\n{target_expected_output}\n</expected_output>"
    else:
        formatted_prompt = f"<task>\n{target_task}\n</task>\n\n<expected_output>\n{target_expected_output}</expected_output>"
    
    # ... rest of existing delegation logic ...

async def _format_skills_instructions(
    self,
    skills_manager: SkillsManager,
    skill_names: list[str],
) -> str:
    """Format skill instructions as XML for injection into subagent prompt.
    
    Uses AgentPool's lazy-loading Skill model to load instructions on-demand.
    Each skill's base directory is included to enable @path resolution.
    
    Args:
        skills_manager: Pool-level skills manager
        skill_names: List of skill names to load
        
    Returns:
        XML-formatted skills section
    """
    skill_sections = []
    
    for skill_name in skill_names:
        try:
            # Get skill from registry
            skill = skills_manager.get_skill(skill_name)
            if not skill:
                logger.warning(f"Skill '{skill_name}' not found in registry")
                continue
            
            # Lazy-load skill instruction content from SKILL.md
            # Skill.load_instructions() caches content after first read
            instruction_content = skill.load_instructions()
            
            # Get skill directory path for base attribute
            # This is the skill's location, not the project root
            skill_base_path = str(skill.skill_path)
            
            skill_sections.append(
                f"  <skill name=\"{skill_name}\" base=\"{skill_base_path}\">\n"
                f"    <description>{skill.description or ''}</description>\n"
                f"    <instructions>\n{instruction_content}\n    </instructions>\n"
                f"  </skill>"
            )
        except Exception as e:
            logger.error(f"Failed to load skill '{skill_name}': {e}")
            continue
    
    if not skill_sections:
        return ""
    
    return "<skills>\n" + "\n".join(skill_sections) + "\n</skills>"
```

#### Tool Schema Update

Update `/packages/xeno-agent/config/tools/new_task.yaml` to include skills parameter:

```yaml
name: new_task
description: |
  Delegate a task to another specialized agent or team.
  
  Use this tool when you need expertise that another agent possesses,
  or when a task can be parallelized across multiple agents.
parameters:
  type: object
  properties:
    mode:
      type: string
      description: The specialized mode/agent to delegate to
    message:
      type: string
      description: The task description for the subagent
    expected_output:
      type: string
      description: Description of what the subagent should produce
    skills:
      type: array
      description: |
        Skills to provide to the subagent for this task.
        Each skill injects specialized instructions into the subagent's context
        to guide its behavior (loaded from ~/.claude/skills/).

        **Examples:**
        - ["git-master"] for Git operations (commit, rebase, history)
        - ["systematic-debugging"] for structured debugging
        - ["uv-package-manager"] for Python package management
        - ["code-review-excellence"] for code review tasks

        Skills are lazy-loaded from the skill registry. Only available skills can be used.
      items:
        type: string
        description: |
          Skill name (e.g., "git-master", "uv-package-manager", "systematic-debugging").
          Must match the name defined in the skill's SKILL.md frontmatter.
      default: []
  required:
    - mode
    - message
    - expected_output
```

### Error Handling

```python
class SkillNotFoundError(ToolError):
    """Raised when a requested skill is not found in the registry."""
    pass

# In _format_skills_instructions:
if strict_mode and not found_skills:
    raise SkillNotFoundError(
        f"Skills not found: {missing_skills}. "
        f"Available skills: {', '.join(skills_manager.list_skills())}"
    )
```

### Configuration Example

```yaml
# In diag-agent.yaml - Parent agent configuration
agents:
  fault_expert:
    type: native
    tools:
      - type: skills  # Main agent has access to skills
      - type: custom
        import_path: xeno_agent.agentpool.resource_providers.XenoDelegationProvider
        # Delegation provider can pass skills to subagents

# Example delegation call:
# new_task(
#   mode="code_reviewer",
#   message="Review this PR for security issues",
#   expected_output="Security analysis report",
#   skills=["security", "code_review", "python"]
# )
```

---

## Implementation Plan

### Phase 1: Foundation (Week 1)

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 1.1 Update new_task schema | Backend | 1 day | None | `config/tools/new_task.yaml` |
| 1.2 Implement skill resolution | Backend | 2 days | 1.1 | `delegation_provider.py` |
| 1.3 Implement XML formatting | Backend | 1 day | 1.2 | `delegation_provider.py` |
| 1.4 Integrate into new_task flow | Backend | 1 day | 1.3 | `delegation_provider.py` |
| 1.5 Add error handling | Backend | 1 day | 1.4 | `delegation_provider.py` |

**Deliverable**: Skills parameter functional in new_task tool

### Phase 2: Testing & Validation (Week 2)

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 2.1 Unit tests for skill resolution | Backend | 2 days | Phase 1 | `tests/agentpool/resource_providers/test_delegation_provider_schema.py` |
| 2.2 Integration tests | Backend | 2 days | 2.1 | `tests/integration/` |
| 2.3 Error handling tests | Backend | 1 day | 2.1 | `tests/agentpool/resource_providers/` |
| 2.4 Performance benchmark | Backend | 1 day | 2.2 | `tests/performance/` |

**Deliverable**: Test coverage > 80%, benchmark showing < 50ms overhead

### Phase 3: Documentation & Polish (Week 3)

| Task | Owner | Duration | Dependencies | File(s) Affected |
|------|-------|----------|--------------|------------------|
| 3.1 Update configuration docs | Docs | 2 days | Phase 2 | `docs/configuration.md` |
| 3.2 Add delegation skill examples | Docs | 2 days | 3.1 | `examples/` |
| 3.3 Type stubs update | Backend | 1 day | Phase 1 | `src/xeno_agent/` |

**Deliverable**: Documentation and examples complete

### Skill Loading Flow

```
Subagent Creation with Skills
    │
    ├─► new_task(skills=["git", "python"])
    │
    ├─► _format_skills_instructions(["git", "python"])
    │   │
    │   └─► For each skill:
    │       │
    │       ├─► skills_manager.get_skill("git") ──▶ Skill instance (metadata only)
    │       │
    │       ├─► skill.load_instructions()  ◄── LAZY LOAD TRIGGER
    │       │   │
    │       │   ├─► Check: skill.instructions already loaded?
    │       │   │   ├─► Yes: Return cached content
    │       │   │   └─► No: Read SKILL.md file
    │       │   │       │
    │       │   │       ├─► Parse frontmatter (YAML between ---)
    │       │   │       ├─► Extract body (after second ---)
    │       │   │       └─► Cache in skill.instructions
    │       │   │
    │       │   └─► Return instruction content
    │       │
    │       └─► skill.skill_path ──▶ "/Users/.../.claude/skills/git/"
    │
    └─► Format as XML with base= attribute
```

### SKILL.md Format

AgentPool skills follow the [Agent Skills Spec](https://github.com/agentskills/agentskills):

```markdown
---
name: git-best-practices
description: Best practices for Git operations
license: MIT
---

# Git Best Practices

When working with Git:
1. Always create feature branches from main
2. Use conventional commit messages
3. ...
```

**Structure**:
- **Frontmatter** (YAML between `---`): Metadata like name, description, license
- **Body**: The actual instruction content loaded via `load_instructions()`

**Key Points**:
- Only the **body** is injected into subagent prompt (not the frontmatter)
- The `base=` attribute points to the skill directory (**not project root**), enabling `@path` resolution within skill context
- Lazy loading ensures skills are only read from disk when actually used

### Rollback Strategy

1. **Feature Flag**: Wrap skill injection in feature flag
   ```python
   if ctx.pool.config.get("enable_delegation_skills", True) and skills:
       skills_content = await self._format_skills_instructions(...)
   ```

2. **Graceful Degradation**: If skill loading fails, log warning and continue without skills
   ```python
   try:
       skills_content = await self._format_skills_instructions(...)
   except Exception as e:
       logger.warning(f"Failed to load skills: {e}")
       skills_content = ""
   ```

3. **Revert**: Remove skills parameter from schema and revert to original implementation

---

## Open Questions

### Technical Questions

1. **Skill Injection Point**: Should skills be injected at the prompt level (Option A) or passed to the subagent's system prompt via `deps` (Option B)?
   - Option A (Recommended): Prepend to formatted_prompt - simpler, visible in logs
   - Option B: Pass via deps to subagent's system prompt - cleaner separation but requires subagent support
   - Impact: Option A is immediate; Option B requires investigation of subagent initialization

2. **Strict vs Lenient Mode**: Should missing skills cause error (strict) or warning (lenient)?
   - Recommendation: Lenient by default (log warning), strict mode opt-in
   - Rationale: Delegation failures should be avoided for non-critical skill missing

3. **Skill Caching**: Should skill instructions be cached to avoid repeated file reads?
   - Options: No cache (simple), Memory cache (performance), Disk cache (persistence)
   - Recommendation: Leverage existing `SkillsRegistry` caching if available

4. **Skill Format**: Should we support plain text (current) or allow different formats?
   - Options: XML only (structured), Plain text, Markdown code blocks
   - Recommendation: XML for consistency with agentpool patterns

### Design Questions

1. **Skill vs Tool Naming**: Should the parameter be `skills` or `skill_instructions`?
   - Recommendation: `skills` - simpler, matches configuration terminology

2. **Default Skills**: Should there be a way to specify default skills for all delegations?
   - Options: Per-agent config, Per-pool config, No defaults
   - Recommendation: Future enhancement - out of scope for initial implementation

3. **Parent Skill Inheritance**: Should subagents optionally inherit parent agent skills?
   - Options: Explicit override only, Inherit + explicit adds, Inherit flag
   - Recommendation: Explicit only initially, inheritance as future opt-in feature

---

## Decision Record

*This section will be filled when the RFC moves to APPROVED status*

| Field | Value |
|-------|-------|
| **Decision** | TBD |
| **Date** | TBD |
| **Approvers** | TBD |
| **Key Discussion Points** | TBD |
| **Conditions on Approval** | TBD |
| **Implementation Ticket** | TBD |

---

## Appendix A: Skill Resolution Flow

```python
# Flow diagram for skill resolution

Parent Agent
    │
    ▼
new_task(skills=["git", "python"])
    │
    ▼
XenoDelegationProvider.new_task()
    │
    ▼
_format_skills_instructions(skills_manager, ["git", "python"])
    │
    ├──▶ skills_manager.get_skill("git")
    │       │
    │       ▼
    │   SkillsRegistry.lookup("git")
    │       │
    │       ▼
    │   └──▶ Skill(name="git", instruction_path="...")
    │            │
    │            ▼
    │        skill.get_instruction_content()
    │            │
    │            ▼
    │        Read file at instruction_path
    │            │
    │            ▼
    │        Return instruction content
    │
    ├──▶ skills_manager.get_skill("python")
    │       ... same flow ...
    │
    ▼
Format as XML: <skills><skill name="git">...</skill>...</skills>
    │
    ▼
Prepend to formatted_prompt
    │
    ▼
node.run_stream(enhanced_prompt)
```

---

## Appendix B: Configuration Examples

### Example 1: Security Review Delegation

```python
# Parent agent: fault_expert
tools.new_task(
    mode="security_analyst",
    message="Review the equipment maintenance logs for any security anomalies",
    expected_output="Security analysis report with any anomalies flagged",
    skills=["security_audit", "log_analysis"]
)

# Subagent receives:
<skills>
  <skill name="security_audit">
    <instructions>
When analyzing logs for security issues:
1. Look for unauthorized access attempts
2. Check for unusual patterns in maintenance timing
3. Flag any missing log entries
...
    </instructions>
  </skill>
  ...
</skills>

<task>Review the equipment maintenance logs...</task>
<expected_output>Security analysis report...</expected_output>
```

### Example 2: Code Review Delegation

```python
# Parent agent: developer_assistant
tools.new_task(
    mode="code_reviewer",
    message="Review the pull request for code quality and adherence to standards",
    expected_output="Code review comments with severity ratings",
    skills=["python_best_practices", "testing_standards", "git_workflows"]
)
```

---

## Related Documentation

- AgentPool Skills System: `/packages/agentpool/src/agentpool/skills/`
- Xeno Delegation Provider: `/packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`
- AgentPool Subagent Tools: `/packages/agentpool/src/agentpool_toolsets/builtin/subagent_tools.py`
