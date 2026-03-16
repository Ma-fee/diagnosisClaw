# Phase 3: Interactive Diagnostic Execution - Extended Guide

Extended implementation details for interactive diagnostic execution.

**Execution Mode**: INTERACTIVE - Extensive user communication required

---

## Entry Requirements

### Device-Specific Skill Loading

**MUST load at Phase 3 entry.**

**Why**: Interactive execution requires device-specific diagnostic procedures, component information, and troubleshooting patterns. The diagnosis-planning report provides structure, but device-specific skills provide detailed guidance.

### Loading Logic

```
ON Phase 3 entry:
    IF device_type in [挖掘机, Excavator, 挖机, 挖土机]:
        LOAD skill: excavator-diagnostic-guide
    ELSE IF device_type in [装载机, Loader, 铲车]:
        LOAD skill: loader-diagnostic-guide  
    ELSE IF device_type in [液压泵, Hydraulic Pump]
        LOAD skill: hydraulic-diagnostic-guide
    ELSE IF device_type in [发动机, Engine, 柴油机, 汽油机]:
        LOAD skill: engine-diagnostic-guide
    ELSE IF device_type in [电机, Motor, 电动机]:
        LOAD skill: motor-diagnostic-guide
    ELSE IF device_type in [压路机, Roller]:
        LOAD skill: roller-diagnostic-guide
    ELSE:
        USE: diagnosis-planning report only
        NOTE: "No device-specific skill available, using planning report"
```

**Usage Pattern**:
- Diagnosis-planning report: Overall structure, hypothesis ranking, standard values
- Device-specific skill: Step-by-step procedures, component locations, practical guidance

---

## Setup

**Step 1**: Load device-specific skill (see Loading Logic above)

**Step 2**: Create diagnostic todo list:

```
[ ] Step 1: [Inspection item from planning report]
       Standard value: [from planning report]
       Tools: [from planning report]
       Guidance: [from loaded skill]
[ ] Step 2: ...
```

---

## Progress Tracking Protocol

**MANDATORY**: Maintain explicit progress state throughout Phase 3 execution.

### Progress Tracking Method

**PREFERRED**: If plan-type tools available (e.g., `update_todo_list`), USE TOOL for progress tracking.

**FALLBACK**: If no plan tools available, use text-based progress tracking.

### With Plan Tool

```
INITIALIZE_PROGRESS_TRACKING(
    method: "tool",
    todos: [list all inspection steps as items],
    metadata: {
        total_steps: count,
        hypotheses: initial_ranking
    }
)

ON user_completes_inspection:
    UPDATE_TODO(
        mark_done: current_step_id,
        record_result: user_observation,
        note: hypothesis_impact
    )
```

### Without Plan Tool (Text-based)

```
INITIALIZE_PROGRESS_TRACKING(
    method: "text",
    total_steps: count(inspection_procedures),
    current_step: 0,
    status: "in_progress"
)

ON user_completes_inspection:
    UPDATE_TEXT_PROGRESS(
        mark_completed: current_step,
        record_result: user_observation
    )
    PRESENT_PROGRESS_SUMMARY()
```

### Update Triggers (Pseudocode)

```
ON user_completes_inspection:
    IF plan_tool_available:
        UPDATE_TODO(mark_done, result, note)
    ELSE:
        UPDATE_TEXT_PROGRESS(completed, result)
    PRESENT_PROGRESS_SUMMARY()

ON hypothesis_confidence_changes:
    UPDATE_PROGRESS_STATE(
        adjust_priority: hypothesis_ranking,
        skip_if_irrelevant: low_probability_steps
    )

ON user_requests_status:
    PRESENT_PROGRESS_SUMMARY()
    SHOW: completed_steps / total_steps
    SHOW: current_hypothesis_ranking
    SHOW: next_steps_preview
```

### Progress State to Track

- Completed steps with results and timestamps
- Current active step with user pending status
- Skipped/deferred items with reasons
- Hypothesis confidence evolution
- Evidence collected per hypothesis
- Any deviations from original plan

### Progress Presentation Format

(Displayed in user's language)

```
Diagnostic Progress (3/7 steps completed)
========================
[✓] Step 1: Check coolant level - Result: Below standard
[✓] Step 2: Inspect radiator hose - Result: Crack found
[→] Step 3: Check thermostat operation - In progress...
[ ] Steps 4-7: Pending

Current hypothesis confidence:
• Coolant leak ............... 85% ↑ (Step 2 new evidence)
• Thermostat failure ......... 30%
• Water pump failure ......... 15%

Estimated remaining time: 15-20 minutes
```

### Completion Check (Before Phase 4)

```
VERIFY(
    CONDITION_1: all_critical_inspections_completed OR
    CONDITION_2: root_cause_confidence >= 90% OR
    CONDITION_3: user_requests_early_conclusion
)
IF NOT satisfied:
    PRESENT_GAP_ANALYSIS()
    REQUEST_USER_DECISION(continue_or_conclude)
```

---

## Execution Loop (Per Step)

### Step Structure

**1. Present Purpose**
   - Explain why this check is being performed
   - Reference which hypothesis this tests
   - Show how this connects to overall plan

**2. Guide Action**
   - Provide clear, step-by-step procedures
   - State safety precautions
   - Give expected normal values/ranges

**3. Collect Result**
   - Request user's observation or measurement
   - Provide clear response options

**4. Interpret Together**
   - Compare result to standard values
   - Explain what the result means
   - Update hypothesis confidence
   - Decide next step with user awareness

### Information Presentation Requirements

**When presenting each step, MUST include**:

#### Visual Aids (If Available)

**Images from knowledge base**:
```
When showing component locations or inspection methods:
- Display image (using knowledge base returned image URL)
- Mark inspection point locations
- Explain measurement methods

Example:
"Radiator hose connection inspection (see red circle in image):
[image]"
```

**Mermaid Diagrams** (for system flows):
```
For complex systems, use Mermaid diagrams:
- Hydraulic system flow
- Electrical connections
- Fault propagation paths
```

#### Source Attribution (MANDATORY)

**Every technical value MUST cite source**:

```
Format:
"Normal pressure range: 31.4-34.3 MPa[^1]"
"[^1]: [Sany SY215C Hydraulic System Specifications](manual:///...)"

Include sources for:
- Standard values / normal ranges
- Component specifications
- Fault case data
- Industry standard requirements

Sources:
- diagnosis-planning report (which has citations)
- device-specific skill references
- Knowledge base queries
```

**Reference**: Include `citation` and `image` capabilities for rich output.

---

## Dynamic Adjustment

Adjust plan in real-time based on findings:

| Finding | Adjustment |
|---------|-----------|
| Root cause confirmed (>90%) | Skip remaining routine checks |
| Unexpected abnormal result | Branch to associated investigation |
| Result contradicts hypothesis | Eliminate, re-prioritize remaining |
| User cannot perform step | Offer alternative or mark limitation |

### Dynamic Examples

**Early Termination**:
```
User completes Step 2 and finds crack, confidence reaches 95%
→ Skip Steps 3-6 routine checks
→ Proceed directly to Phase 4 confirmation
```

**Branching**:
```
Step 3 finds abnormal value, related to unconsidered fault mode
→ Add new hypothesis
→ Insert targeted inspection step
→ Update all hypothesis probabilities
```

---

## Phase 3 Completion Criteria

- [ ] All relevant hypotheses tested
- [ ] Root cause identified with >90% confidence
- [ ] User agrees with findings
- [ ] Ready for formal confirmation

---

## User Response Patterns

### Presenting Options

Always provide clear, mutually exclusive options:

```
"Inspection result:
A) Normal / within specification
B) Below normal
C) Above normal
D) Cannot inspect (please explain why)"
```

### Handling Unclear Responses

If user response is ambiguous:

```
"Thank you for the feedback. To ensure I understand correctly:
- You observed: [paraphrased]
- This means: [interpretation]

Is this correct? Or can you provide more details?"
```

---

## Safety Reminders

Before each potentially hazardous step:

```
"⚠️ Safety Reminder:
[Specific safety precaution for this step]

Confirm safety before continuing."
```

Common excavator safety points:
- Allow hot engines/equipment to cool before inspection
- Secure equipment before working underneath
- Use proper PPE (gloves, eye protection)
- Never bypass safety interlocks
