# RFC-001: Offline Agent System Simulation Design using CrewAI (v6)

| Status | Proposed |
| :--- | :--- |
| **Author** | Antigravity (Sisyphus) |
| **Date** | 2026-01-18 |
| **Scope** | Offline Simulation, CrewAI Integration, xeno-agent |

## 1. Overview & Objectives

This design details the implementation of an offline simulation for the Xeno Fault Diagnosis System using **CrewAI**. It specifically addresses the mechanisms for dynamic routing (GOTO), task delegation (GOSUB), context preservation, and skill injection.

**Crucially, it incorporates:**
1.  **Human-in-the-Loop (HITL) via a Decorator Pattern**, simplifying the Flow logic.
2.  **Builder Pattern for Agent Construction**, providing a fluent API for defining Xeno Agents and injecting skills.

**Code Location**: All implementation will reside in `packages/xeno-agent/src/xeno_agent/`.

## 2. Architecture: "The Stack-Based Flow"

To support both `switch_mode` (transfer) and `new_task` (sub-routine), we employ a **Stack-Based State Machine** pattern within a CrewAI Flow.

### 2.1 State Model (`SimulationState`)

We define a robust state object managed by the Flow.

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class TaskFrame(BaseModel):
    """Represents a stack frame for a task execution context."""
    mode_slug: str
    task_id: str
    trigger_message: str  # The prompt/instruction for this specific frame
    caller_mode: Optional[str] = None
    is_isolated: bool = False 

class SimulationState(BaseModel):
    stack: List[TaskFrame] = []
    conversation_history: List[Dict[str, str]] = []
    final_output: Optional[str] = None
    is_terminated: bool = False
    last_signal: Any = None
```

### 2.2 Routing Logic (The "Kernel")

The Flow's router acts as the OS kernel, managing context switching based on "System Calls" (Tools) returned by agents.

*   **`switch_mode(target)`**: Pops current frame, pushes new frame (same level).
*   **`new_task(target, message)`**: Pushes new frame on top of current frame.
*   **`attempt_completion(result)`**: Pops current frame or terminates.

## 3. Human-in-the-Loop (HITL) Implementation: The Decorator

We wrap sensitive tools with an **Approval Decorator** (`@requires_approval`).
This decorator intercepts the tool's `_run` method, asks for user confirmation via `InteractionHandler`, and either proceeds or returns a rejection message.

## 4. Agent Construction: The Builder Pattern

To simplify the complex configuration of Agents (Roles + Skills + Prompts), we introduce `XenoAgentBuilder`.

### 4.1 `XenoAgentBuilder`

```python
class XenoAgentBuilder:
    def __init__(self, role_name: str):
        self._role = role_name
        self._goal = ""
        self._backstory = ""
        self._skills: List[str] = []
        self._llm = None
        self._allow_delegation = False
        
    def with_goal(self, goal: str) -> 'XenoAgentBuilder':
        self._goal = goal
        return self
        
    def with_backstory(self, backstory: str) -> 'XenoAgentBuilder':
        self._backstory = backstory
        return self
        
    def with_skill(self, skill_name: str) -> 'XenoAgentBuilder':
        self._skills.append(skill_name)
        return self
        
    def from_yaml(self, yaml_path: str) -> 'XenoAgentBuilder':
        # Hydrate from YAML definition
        pass
        
    def build(self) -> Agent:
        """
        Constructs the CrewAI Agent.
        1. Fetches Tools from SkillRegistry based on self._skills.
        2. Fetches Instructions from SkillRegistry.
        3. Compiles Backstory + Skill Instructions.
        4. Returns initialized Agent.
        """
        tools = []
        instructions = []
        
        for skill in self._skills:
            tool, instr = SkillRegistry.get(skill)
            tools.append(tool)
            instructions.append(f"## {skill}\n{instr}")
            
        full_backstory = f"{self._backstory}\n\n" + "\n".join(instructions)
        
        return Agent(
            role=self._role,
            goal=self._goal,
            backstory=full_backstory,
            tools=tools,
            # ...
        )
```

## 5. Implementation Details

### 5.1 Directory Structure

```text
packages/xeno-agent/src/xeno_agent/
├── __init__.py
├── core/
│   ├── flow.py              # XenoSimulationFlow (The Kernel)
│   ├── state.py             # SimulationState, TaskFrame
│   ├── signals.py           # Signal definitions
│   └── hitl.py              # InteractionHandler & Decorators
├── agents/                  # Agent Definitions (Roles)
│   ├── builder.py           # XenoAgentBuilder (NEW)
│   └── registry.py          # Role definitions loader
├── skills/                  # Skills & Tools
│   ├── builtin/             # switch_mode, new_task implementations
│   └── registry.py          # Skill injector
└── utils/
    └── prompt_utils.py      # Prompt composition helpers
```

## 6. Development Plan

1.  **Core Scaffolding**: Create `state.py`, `signals.py`, `hitl.py`.
2.  **Meta Tools**: Implement builtin skills using the HITL decorator.
3.  **Agent Builder**: Implement `XenoAgentBuilder` and `SkillRegistry`.
4.  **Flow**: Implement `XenoSimulationFlow`.
5.  **Simulation Loop**: Wire it all together.
