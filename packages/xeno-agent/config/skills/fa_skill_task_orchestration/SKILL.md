---
name: fa_skill_task_orchestration
description: Decompose complex tasks and delegate to sub-agents.
allowed-tools:
  - new_task
  - switch_mode
  - update_todo_list
---

# Task Orchestration

## Core Principle
Break down complex requests into atomic subtasks and delegate them to specialized agents or tools. Manage the state of these tasks and synthesize results.

## Delegation Strategy

### When to Delegate
- **Information Gap**: Need specific specs or docs -> Delegate to Material Assistant
- **Execution Gap**: Need physical procedure steps -> Delegate to Equipment Expert
- **Analysis Gap**: Need specialized calculation or image analysis -> Use specific tool or expert

### Delegation Methods
1. **`new_task` (Subroutine)**
   - Use when you need a specific answer to continue your own workflow.
   - You remain the "owner" of the parent task.
   - Example: Fault Expert asks Material Assistant for a spec value.

2. **`switch_mode` (Handover)**
   - Use when the nature of the work changes entirely.
   - You transfer ownership to the new agent.
   - Example: Fault Expert determines root cause, hands over to Equipment Expert for repair.

## Orchestration Workflow

1. **Analyze Request**: Identify all requirements.
2. **Breakdown**: Create a plan (Todo List).
3. **Execute/Delegate**:
   - If task is within capability: Execute.
   - If task needs others: Delegate.
4. **Synthesize**: Collect results from delegations.
5. **Review**: Check if original request is satisfied.

## Example: Complex Repair

**Goal**: "Fix the leaking cylinder."

1. **Plan**:
   - Identify cylinder model (Self/User)
   - Get seal kit part number (Delegate: Material Assistant)
   - Get repair procedure (Delegate: Material Assistant/Equipment Expert)
   - Guide user through repair (Switch: Equipment Expert)

2. **Execution**:
   - `new_task(material_assistant, "Find seal kit for Cylinder X")` -> Returns "Part #123"
   - `switch_mode(equipment_expert, "Guide user to install seal kit #123 on Cylinder X")`
