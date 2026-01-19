# Xeno Agent Architecture

## 1. Overview

Xeno Agent employs a **parallel four-layer architecture** for defining agent capabilities. This design ensures separation of concerns, modularity, and compatibility with Claude Skills standards.

```
                ┌───────────────────────────────────┐
                │        Agent (Role)          │
                │  YAML: capabilities[], tasks[] │
                │        tools[], skills[]        │
                └───────────────┬───────────────┘
                                │
        ┌───────────────┼───────────────┬───────────────┬───────────────┐
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌───────────┐ ┌─────────────┐ ┌─────────────┐
│ Capability  │ │   Task    │ │   Skill     │ │   Tool      │
│ (Declarative)│ │  (CrewAI)  │ │ (Claude SKILL)│ │ (Executable)│
│ capabilities │ │ description │ │  SKILL.md   │ │  BaseTool   │
│  [] Strings  │ │expected_out │ │  instructions │ │             │
└─────────────┘ └───────────┘ └─────────────┘ └─────────────┘
```

## 2. Core Components

### 2.1 Agent (Role)
Defined in `config/roles/*.yaml`. The central configuration that binds the four components together.

- **Identity**: `name`, `role`, `goal`, `backstory`
- **Bindings**: `tools`, `skills`, `tasks`, `capabilities`

### 2.2 Tool Layer (Executable)
- **Definition**: Atomic, executable Python functions.
- **Location**:
  - Implementation: `src/xeno_agent/tools/*.py`
  - Configuration: `config/tools/builtin/*.yaml`
- **Loader**: `ToolLoader` (loads instances and descriptions)
- **Examples**: `search_engine`, `collect_metrics`, `switch_mode`

### 2.3 Skill Layer (Instructional)
- **Definition**: High-level capability instructions (Prompt Expansion) compatible with Claude Skills.
- **Location**: `skills/<skill_name>/SKILL.md`
- **Format**: Markdown with YAML frontmatter.
- **Loader**: `SkillLoader`
- **Examples**: `fa_skill_fault_analysis`, `fa_skill_deep_search`

### 2.4 Task Layer (Operational)
- **Definition**: Specific units of work to be performed.
- **Location**: Defined in Agent YAML `tasks` list.
- **Usage**: Used to initialize the agent's work queue or define its scope.

### 2.5 Capability Layer (Declarative)
- **Definition**: Semantic tags describing what the agent *can* do.
- **Location**: Agent YAML `capabilities` list.
- **Usage**: Documentation, search, and potential future routing/verification.

## 3. Directory Structure

```
packages/xeno-agent/
├── config/
│   ├── roles/           # Agent definitions
│   └── tools/           # Tool YAML configurations
├── skills/              # Claude Skills (SKILL.md)
└── src/xeno_agent/
    ├── agents/          # Agent construction (Builder)
    ├── core/            # Loaders (ToolLoader, SkillLoader)
    └── tools/           # Tool implementations
```

## 4. Key Classes

- **`XenoAgentBuilder`**: Assembles the agent by loading tools via `ToolLoader` and skills via `SkillLoader`.
- **`ToolLoader`**: Scans `config/tools/builtin` and instantiates tools using `DynamicToolFactory`.
- **`SkillLoader`**: Scans `skills/` directory and parses `SKILL.md` files.
