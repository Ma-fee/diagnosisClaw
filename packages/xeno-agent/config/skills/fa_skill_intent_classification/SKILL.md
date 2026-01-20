---
name: fa_skill_intent_classification
description: Identify user intent and route to appropriate expert.
allowed-tools:
  - switch_mode
  - new_task
  - attempt_completion
---

# Intent Classification and Routing

## Core Principle
Analyze user input to determine the specific intent and route the request to the most suitable specialist agent (Fault Expert, Equipment Expert, or Material Assistant).

## Intent Categories

### 1. Fault Diagnosis (Fault Expert)
**Triggers**:
- User reports equipment failure or abnormality
- "Something is broken", "Error code X", "Not working"
- User asks for troubleshooting steps
- Symptoms described (noise, leak, smoke, stopped)

**Action**:
- Switch to `fault_expert`
- Pass the full context of the fault report

### 2. Physical Operation Guidance (Equipment Expert)
**Triggers**:
- User asks HOW to perform a specific physical task
- "How do I replace X?", "Show me how to inspect Y"
- Needs step-by-step guidance for maintenance or repair
- Asks about tool usage or safety procedures for a task

**Action**:
- Switch to `equipment_expert`

### 3. Material/Document Search (Material Assistant)
**Triggers**:
- User asks for specifications, manuals, or diagrams
- "What is the torque spec?", "Find the schematic for X"
- "Do you have the manual for Y?"
- Lookups for part numbers or fluid types

**Action**:
- Delegate to `material_assistant` (via `new_task` if simple query, or switch if complex research)

### 4. General Q&A (Handle Directly)
**Triggers**:
- Greetings
- Capabilities questions ("What can you do?")
- Simple clarifications not requiring deep expertise

**Action**:
- Answer directly

## Routing Logic

### Priority Order
1. **Safety/Emergency**: If user reports danger -> Equipment Expert (for safety procedures) or Fault Expert (for shutdown)
2. **Diagnosis**: If root cause unknown -> Fault Expert
3. **Execution**: If root cause known, need how-to -> Equipment Expert
4. **Information**: If just need data/docs -> Material Assistant

### Ambiguity Handling
- If intent is unclear, ask ONE clarifying question.
- Do not guess.

## Example Scenarios

**User**: "The hydraulic pump is making a weird noise."
**Intent**: Fault Diagnosis
**Route**: `switch_mode(target="fault_expert", reason="User reporting abnormal noise in hydraulic pump")`

**User**: "I need to change the hydraulic filter. How do I do that?"
**Intent**: Physical Operation Guidance
**Route**: `switch_mode(target="equipment_expert", reason="User requesting maintenance procedure for filter change")`

**User**: "What is the part number for the main pump seal?"
**Intent**: Material Search
**Route**: `new_task(target="material_assistant", task="Find part number for main pump seal", expected_output="Part number")`
