# Skills Overview

This directory contains standardized skill definitions for the Xeno Agent system. Each skill represents a reusable capability that can be invoked by multiple agents.

## Skills List

### 1. [search_capability.mdc](./search_capability.mdc)
**Purpose**: Comprehensive multi-source search and information retrieval capability

**Key Capabilities**:
- Multi-source search strategy (academic, technical, news, references)
- Information quality assessment and verification hierarchy
- Cross-referencing protocol for validating critical information
- Iterative search refinement based on results

**Used By**:故障专家, 资料助手

---

### 2. [markdown_formatting.mdc](./markdown_formatting.mdc)
**Purpose**: Structured markdown response formatting with proper citations

**Key Capabilities**:
- Inline footnote citation system with meaningful identifiers
- Clickable file and code references with line numbers
- Complete source attribution protocols
- Mobile-first document structure formatting

**Used By**: All agents (universally required)

---

### 3. [information_verification.mdc](./information_verification.mdc)
**Purpose**: Rigorous information verification and source attribution

**Key Capabilities**:
- Source quality hierarchy (Primary → Tertiary → Unverified)
- Fact-checking protocols for numerics, specs, historical claims
- Citation requirements for academic, web, technical, and news sources
- Transparency standards for verified vs. interpreted information
- Image reference verification protocol (source whitelist)

**Used By**: All agents (especially 资料助手 and 故障专家)

---

### 4. [image_handling.mdc](./image_handling.mdc)
**Purpose**: Comprehensive image processing and formatting for fault diagnosis

**Key Capabilities**:
- Mandatory HTML5 `<figure>` structure with complete annotations
- Detailed purpose descriptions (visuals, correspondence, technical specs)
- Source whitelist verification
- Support for diagnostic flowcharts, component locations, measurement procedures
- Quality assurance checklist for image inclusion

**Used By**:故障专家 (diagnostic reports), 设备专家 (visual aids)

---

### 5. [mermaid_generation.mdc](./mermaid_generation.mdc)
**Purpose**: Standardized mermaid diagram generation for technical workflows

**Key Capabilities**:
- **CRITICAL**: All string values MUST be quoted to prevent parse errors
- Proper syntax for flowcharts, decision trees, and component schematics
- Visual styling with meaningful colors and shapes
- Validation protocol before rendering
- Common pitfalls prevention (unquoted strings, improper syntax)

**Used By**:故障专家, 设备专家 (all diagnostic and procedure diagrams)

---

### 6. [diagnostic_planning.mdc](./diagnostic_planning.mdc)
**Purpose**: Structured fault diagnosis planning and execution

**Key Capabilities**:
- **Phase 1**: Information collection with priority-based questioning
- **Phase 2**: Comprehensive diagnosis plan generation
- **Phase 3**: Multi-round interactive fault localization
- **Phase 4**: Failure case report generation
- Dynamic todo list management with `update_todo_list`
- Root cause confirmation at >90% confidence

**Used By**:故障专家

---

### 7. [maintenance_guidance.mdc](./maintenance_guidance.mdc)
**Purpose**: Interactive execution monitoring for equipment maintenance tasks

**Key Capabilities**:
- **Phase 1**: Task decomposition and planning with `update_todo_list`
- **Phase 2**: Real-time RAG retrieval integration (specs, diagrams, procedures)
- **Phase 3**: Interactive execution monitoring with exception handling
- **Phase 4**: Image analysis with multimodal tools
- **Phase 5**: Comprehensive analysis of operation results
- **Phase 6**: Task confirmation and result summary
- **Phase 7**: Task delivery and record preservation with `attempt_completion`

**Used By**:设备专家

---

## Skill Dependencies

### Core Foundation Skills (Used by All)
1. **markdown_formatting** - Universal formatting requirement
2. **information_verification** - Source credibility and accuracy

### Shared Capability Skills
3. **search_capability** - Information retrieval (故障专家, 资料助手)
4. **image_handling** - Visual support (故障专家, 设备专家)
5. **mermaid_generation** - Diagram generation (故障专家, 设备专家)

### Role-Specific Skills
6. **diagnostic_planning** - Exclusive to 故障专家
7. **maintenance_guidance** - Exclusive to 设备专家

---

## Skill Usage Pattern

### Order of Skill Application

1. **Universal Skills First**: Always apply `markdown_formatting` and `information_verification` first
2. **Capability Skills Next**: Apply `search_capability`, `image_handling`, or `mermaid_generation` as needed
3. **Role-Specific Skills Last**: Apply `diagnostic_planning` or `maintenance_guidance` based on agent role

### Critical Rules

1. **Mermaid Diagrams**: ALL string values MUST be double-quoted
2. **Image Inclusion**: Never fabricate image URLs; verify against source whitelist
3. **Citations**: Every factual claim must have a verifiable source
4. **Todo Updates**: Only pass changed items to `update_todo_list` (incremental updates)

---

## File Format

All skill files use `.mdc` extension (Markdown Capability definition):
- Structured sections with clear headings
- Code blocks for examples and protocols
- Tables for structured information
- Mermaid diagrams for visual workflows

---

## Maintenance

When updating skills:
1. Maintain consistency with role definitions in `../roles/`
2. Ensure compatibility with core protocols in `../tools/`
3. Update dependency graphs when adding/removing skills
4. Test skill integration with multiple agents
5. Keep skill descriptions focused and modular

---

## Referenced Documents

These skills are based on:
- `docs/capability/` - Shared capabilities documentation
- `docs/roles/` - Agent role specifications
- `docs/rfc/001_agent_system_design/001_agent_system_architecture.md` - System architecture

---

## Contact

For questions or issues with skill definitions, refer to:
- Main agent architecture documentation
- Role-specific configuration files
- Core tool definitions and protocols
