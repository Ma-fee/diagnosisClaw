---
name: systematic-troubleshooting
description: Execute systematic interactive troubleshooting for complex system faults through structured user collaboration. Use this skill IMMEDIATELY when a user reports ANY equipment fault, system malfunction, or diagnostic need - including engine problems, hydraulic failures, electrical issues, overheating, leaks, abnormal noises, or performance degradation. Always prefer this skill for guided fault diagnosis requiring step-by-step user interaction, evidence-based root cause confirmation, and collaborative decision-making across diagnostic phases.
---

# Systematic Troubleshooting

Structured fault diagnosis through five collaborative phases with mandatory user confirmations.

## Critical Requirements

**Language Requirement**: ALL output MUST be in the user's language (the language they use to communicate with you). Detect their language from their input and respond entirely in that language. Do not default to English if the user communicates in Chinese, Spanish, or other languages.

**Interactive-First**: All phases involving user input require direct conversation. Never bypass user in decision-making.

**Phase Gates**: No automatic advancement. Each phase requires explicit user confirmation.

**Execution Modes**:
- **INTERACTIVE**: Information collection, test execution, result interpretation (direct with user)
- **BACKGROUND**: Multi-dimensional research and document generation (delegated)

## Diagnostic Phases

```
Phase 1: Information Collection → INTERACTIVE
    ↓ [User confirms completion]
Phase 2: Diagnostic Planning → BACKGROUND
    ↓ [User confirms planning results]
Phase 3: Interactive Execution → INTERACTIVE
    ↓ [User confirms root cause findings]
Phase 4: Root Cause Confirmation → INTERACTIVE
    ↓ [User confirms documentation]
Phase 5: Case Documentation → CURRENT AGENT (not delegated)
    Complete
```

## Phase Details

All five phases are documented below. Extended guidance available in `references/` if file reading is supported.

## Quick Reference

### Phase Transition Protocol

```
Phase Complete → Summarize outcomes → Explain next phase → Ask confirmation
[User approves] → Load resources → Proceed
[User declines] → Stay or conclude
```

### Phase 3: When to Load equipment-operation-assistant

**Default**: Provide concise check information, user performs independently

**Delegate when user asks:**
- "xxx 在哪里？"/"Where is xxx?"
- "如何检查 xxx？"/"How to check xxx?"
- "怎么操作/拆卸 xxx？"/"How do I...?"
- "找不到 xxx"/"Cannot locate xxx"

**Delegation**: `load_skills=['equipment-operation-assistant']` with specific operation details

### Integration with Other Skills

| Trigger | Skill | Path |
|---------|-------|------|
| Comprehensive planning needed | diagnosis-planning | ../diagnosis-planning |
| Information gathering framework | information-gathering | ../information-gathering |
| Case documentation | case-document | ../case-document |

### Progress Tracking

**IF** `update_todo_list` tool available → USE IT
**ELSE** → Use text-based format (see phase_3_execution.md)

### Safety & Boundaries

- Flag safety concerns immediately
- Recommend qualified technician for safety-critical systems
- Escalate if: confidence <90%, exceeds user capability, or safety concerns

## Phase 1-5 Synopses

### Phase 1: Information Collection

**Purpose**: Gather comprehensive fault context through user interaction

**Mode**: INTERACTIVE

**Information to Collect**:

| Category | Details |
|----------|---------|
| **System Identification** | Equipment type, manufacturer, model, specifications |
| **Fault Description** | Symptoms, severity, patterns, onset timing |
| **Operating Conditions** | Ambient environment, workload, parameters |
| **Historical Context** | Maintenance history, recent changes, past issues |

**Completion Verification** (check before asking user to proceed):
- [ ] Equipment manufacturer and model documented
- [ ] Primary symptom described with specifics
- [ ] Operating conditions recorded
- [ ] Maintenance history obtained

**Transition Template** (respond in user's language):
```
"I have collected the following information:

📋 Equipment Information
- Model: [manufacturer] [model]

📋 Fault Description  
- Symptom: [description]
- Conditions: [conditions]

📋 Next Step
I will research technical materials and develop a diagnostic plan.

Shall we proceed to the diagnostic planning phase?"
```

### Phase 2: Diagnostic Planning

**Purpose**: Generate diagnostic plan with hypotheses, procedures, standard values

**Mode**: BACKGROUND (delegate)

**Why Delegation**: Planning requires multi-dimensional research across 4+ information categories (specs, failure modes, procedures, cases, standards), structured synthesis, and cross-reference validation.

**How to Delegate** (MUST include load_skills):
```
Delegate to: task agent with load_skills=['diagnosis-planning']
Parameters:
- category: deep (or appropriate category for research)
- load_skills: ['diagnosis-planning']  ← CRITICAL: Must include this
- prompt: Include
  - equipment: {from Phase 1}
  - fault_description: {from Phase 1}
  - context: {operating conditions, history}

Required output:
- Failure analysis with probability rankings
- Inspection procedures with standard values
- Decision logic and flowcharts
- Information gaps and limitations

Research scope: Technical manuals, failure databases, case studies, standards
```

**Expected Planning Outputs**:

**1. Possible Causes**
   - List with probability rankings
   - Failure mechanisms for each
   - Key indicators to check

**2. Inspection Procedures**
   - Step-by-step sequence
   - Standard values and tolerances
   - Required tools

**3. Decision Logic**
   - Flowchart for branching decisions
   - Criteria for eliminating hypotheses

**Transition Template** (in user's language):
```
"Diagnostic plan completed:

📋 Possible Causes (ranked by probability)
1. [Cause A] - [probability] - [key check point]
2. [Cause B] - [probability] - [key check point]
...

📋 Inspection Plan
Total [N] inspection steps, estimated time [time estimate]

Shall we begin interactive troubleshooting? I'll guide you through each step."
```

### Phase 3: Interactive Diagnostic Execution

**Purpose**: Execute diagnostic plan step-by-step with user

**Mode**: INTERACTIVE

**Default Approach**: Provide concise inspection information only

For each diagnostic step:
1. **Present what to check** - Component location, normal values, key indicators
2. **Ask user to perform check** - "请检查 xxx 的读数"
3. **Collect result** - User reports back measurements/observations

**When to Delegate to equipment-operation-assistant**:

ONLY when user needs step-by-step guidance. Trigger phrases:
- "xxx 在哪里？"/ "Where is xxx?"
- "如何检查 xxx？"/ "How to check xxx?"
- "怎么操作？"/ "怎么拆？"/ "How do I...?"
- "找不到 xxx"/ "Cannot locate xxx"
- "不会操作 xxx"/ "Don't know how to operate xxx"

**Delegation parameters**:
```
load_skills: ['equipment-operation-assistant']
prompt: "Guide user through [specific operation]
  - Equipment: [type]
  - Task: [what user needs to do]
  - Current situation: [context from ongoing diagnosis]"
```

**Setup**:
1. Create diagnostic todo list
2. Set up progress tracking (tool-based or text-based)

**Progress Tracking Options**:
- **IF** `update_todo_list` tool available → USE IT
- **ELSE** → Use text-based format showing completed steps, current step, hypothesis confidence

**Execution Loop (per step)**:
1. **Present Check Info** - What to inspect, expected values, significance
2. **Wait for User Result** - User performs check independently
3. **IF user asks for guidance** → Delegate to equipment-operation-assistant
4. **Interpret Together** - Compare to standards, update confidence, decide next step

**Dynamic Adjustments**:
- Root cause >90% → Skip remaining routine checks
- Unexpected result → Branch investigation
- Result contradicts hypothesis → Eliminate and re-prioritize
- User cannot perform → Delegate to equipment-operation-assistant

**Completion Criteria**: All relevant hypotheses tested AND root cause >90% confidence AND user agrees

### Phase 4: Root Cause Confirmation

**Purpose**: Formally verify root cause with user

**Mode**: INTERACTIVE

**Verification Checklist** (present in user's language):

```
"Based on our investigation, let's confirm the root cause:

✅ Symptom Explanation
All observed symptoms can be explained by this cause:
- [Symptom 1] → [Explanation]
- [Symptom 2] → [Explanation]

✅ Alternative Causes Excluded
Other possible causes have been ruled out:
- [Cause B]: Excluded because [evidence]
- [Cause C]: Excluded because [evidence]

✅ Confidence Assessment
Current confidence: [90%+]

✅ Recommended Actions
[Recommended corrective action]

Do you confirm this is the correct root cause?"
```

**Confidence Levels**:

| Level | Criteria | Action |
|-------|----------|--------|
| >95% | Direct evidence, all excluded | Confident proceed |
| 90-95% | Strong evidence, minor uncertainty | Proceed with note |
| <90% | Insufficient evidence | Recommend more testing |

---

### Optional Phase 4.5: Fault Resolution

**Purpose**: Guide user through corrective actions

**Mode**: INTERACTIVE

**When**: After root cause confirmed, user wants to proceed with repair

**Activities**:
1. Identify parts/procedures needed
2. Guide step-by-step resolution with safety precautions
3. Verify resolution after completion
4. Provide post-resolution advice (preventive maintenance, monitoring)

### Phase 5: Case Documentation

**Purpose**: Generate comprehensive case report

**Mode**: CURRENT AGENT ONLY - MUST NOT DELEGATE

**Critical**: Generate in current context using complete conversation history. Subagents lose critical details.

**Process**:
1. Load `case-document` skill for templates
2. Gather from conversation context: Phase 1-4 data, all user responses, measurements
3. Apply templates with complete context
4. Generate report sections:
   - Executive summary
   - Equipment details
   - Timeline of diagnostic process
   - Evidence and test results table
   - Root cause analysis
   - Corrective actions
   - Lessons learned
   - Technical diagrams

**Anti-Pattern**:
- ❌ Delegate to subagent for report generation
- ❌ Summarize and pass to another agent
- ✅ Generate in current agent with full context

## Additional Resources

For extended details (if file reading is available):
- `references/phase_3_execution.md` - Detailed interactive execution guidance
- `references/domain_examples.md` - Complete excavator diagnostic example

## Key Principles

1. **Evidence-Driven**: All conclusions supported by test results, confidence tracked
2. **User-Centric**: Never bypass user; explain reasoning transparently
3. **Adaptive**: Adjust plan based on findings; skip irrelevant steps
4. **Safety First**: Flag hazards immediately; recommend experts when needed
