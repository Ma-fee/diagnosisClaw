# Phase Details Reference

Extended implementation guidance for Phases 1, 2, 4, and 5.

**Note**: All templates and output must be in the user's language (detected from their input).

For Phase 3 details, see `phase_3_execution.md`.

---

## Phase 1: Information Collection

**Purpose**: Gather comprehensive fault context through user interaction

**Execution Mode**: INTERACTIVE - Direct user communication only

### Information Requirements

Collect through structured user interaction:

| Category | Information to Collect |
|----------|----------------------|
| **System Identification** | Equipment type, manufacturer, model, specifications |
| **Fault Description** | Symptoms, severity, patterns, onset timing |
| **Operating Conditions** | Ambient environment, workload, parameters |
| **Historical Context** | Maintenance history, recent changes, past issues |

### Collection Approach

1. Start with available information from user's initial report
2. Identify gaps in required information
3. Request specific details interactively from user
4. Validate completeness before concluding phase

### Phase 1 Completion Verification

Verify BEFORE requesting user confirmation:

- [ ] Equipment manufacturer and model documented
- [ ] Primary symptom described with specifics
- [ ] Operating conditions recorded (temp, workload, environment)
- [ ] Maintenance history obtained (last service, recent changes)

**Then ask** (in user's language): "Shall we proceed to the diagnostic planning phase?"

### Phase Completion Template

(Present in user's language):

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

---

## Phase 2: Diagnostic Planning

**Purpose**: Generate comprehensive diagnostic plan based on collected information

**Execution Mode**: BACKGROUND - Multi-dimensional research requiring delegation

### Planning Activities

**REQUIRED**: Delegate the entire planning task. Diagnostic planning requires:
- Multi-dimensional research (equipment specs, failure modes, procedures, cases, standards)
- Structured synthesis of diverse information
- Cross-reference intensive validation across sources

**MANDATORY**: Use delegation (e.g., `new_task`) for comprehensive diagnostic planning.

| Task | Required Approach |
|------|-------------------|
| Retrieve technical standards | Via delegated research |
| Research failure modes | Via delegated research |
| Gather historical cases | Via delegated research |
| Synthesize structured plan | Via delegated research |

### Why Delegation is Required

Diagnostic planning exhibits all characteristics requiring delegation:
- **Multi-dimensional**: Requires 4+ distinct categories of information
- **Structured output**: Organized sections, tables, timelines
- **Cross-reference intensive**: Multiple sources need validation
- **Comprehensive coverage**: Systematic exploration needed

### Delegate with Context

```
Delegate to: [research-capable agent/skill]

Parameters:
- equipment: {collected from Phase 1}
- fault_description: {collected from Phase 1}
- context: {operating conditions, history}

Required output:
- Failure analysis with probability rankings
- Inspection procedures with standard values
- Decision logic and flowcharts
- Information gaps and limitations

Research scope: Technical manuals, failure databases, case studies, standards
```

### Planning Outputs (from delegated task)

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

### Phase Completion Template

(Present in user's language):

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

---

## Phase 4: Root Cause Confirmation

**Purpose**: Formally verify and document root cause with user

**Execution Mode**: INTERACTIVE - Requires user confirmation

### Verification Checklist

Present to user (in their language):

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

Do you confirm this is the correct root cause? Any other concerns?"
```

### Confidence Levels

| Level | Criteria | User Action |
|-------|----------|-------------|
| >95% | Direct evidence, all alternatives excluded | Confident proceed |
| 90-95% | Strong evidence, minor uncertainty | Proceed with note |
| <90% | Insufficient evidence | Recommend additional testing |

### Phase Completion

After root cause confirmation:
- User explicitly confirms root cause
- User has no outstanding questions
- **Next Phase**: Assist with fault resolution (Phase 4.5) if user wants

---

## Phase 4.5: Fault Resolution Assistance

**Purpose**: Guide user through corrective actions and fault elimination

**Execution Mode**: INTERACTIVE - Hands-on guidance with user

### When to Enter

After root cause confirmed and user wants to proceed with repair/fix.

### Resolution Workflow

**1. Identify Required Actions**
   Based on root cause, determine:
   - Replacement parts needed
   - Repair procedures
   - Adjustment requirements
   - Special tools needed

**2. Guide Step-by-Step Resolution**
   For each corrective action:
   - Explain what to do and why
   - Safety precautions
   - Step-by-step procedures
   - Expected outcomes after each step

**3. Verify Resolution**
   After actions completed:
   - Verify symptoms eliminated
   - Test equipment operation
   - Confirm normal parameters
   - Document any deviations

**4. Post-Resolution Advice**
   - Preventive maintenance recommendations
   - Monitoring suggestions
   - Warning signs to watch for

### Example Resolution Guidance

(Present in user's language):

```
"Root cause confirmed as coolant leak at radiator hose connection.

Repair Steps:

Step 1: Prepare tools and parts
- Required: New hose clamp (spec: 32-44mm)
- Required: Coolant (~2 liters)
- Tools: Screwdriver set

Step 2: Replace hose
[Detailed procedure guidance...]

Step 3: Refill coolant
[Detailed procedure guidance...]

Step 4: Verify repair
- Start engine
- Observe pressure gauge
- Check for leaks
- Run normally for 10 minutes

Let me know the results when done, and we'll proceed to case documentation."
```

### Phase Completion

Resolution phase complete when:
- [ ] Corrective actions completed
- [ ] Equipment tested and operational
- [ ] User confirms fault eliminated
- [ ] Ready for case documentation

---

## Phase 5: Case Documentation

**Purpose**: Generate comprehensive case report

**Execution Mode**: CURRENT AGENT - DIALOGUE CONTEXT REQUIRED - MUST NOT DELEGATE

### Critical Requirement: Generate in Current Context

**REQUIRED**: Case documentation MUST be generated by the **current agent** using the complete diagnostic conversation context. Do NOT delegate document generation to subagents or background tasks.

**Why Context Matters**:
- Only the current agent has access to the full diagnostic conversation
- All user responses, measurement values, and decision rationale are in dialogue history
- Subagents lose critical details when receiving summarizations
- Report quality depends on complete contextual information

### Documentation Process

**Step 1**: Load `case-document` skill for templates and formatting guidelines

**Step 2**: Gather data from current conversation context:
- Phase 1: All information collected from user
- Phase 2: Planning report results
- Phase 3: Every inspection step and user response
- Phase 4: Root cause confirmation dialogue
- User's corrective actions and verification results

**Step 3**: Apply `case-document` templates with complete contextual data

**Step 4**: Generate report sections:
1. Executive summary
2. Equipment details
3. Timeline of diagnostic process
4. Evidence and test results table
5. Root cause analysis
6. Corrective actions
7. Lessons learned
8. Technical diagrams (using Mermaid templates from skill)

### Final Presentation

(Present in user's language):

```
"Case documentation completed:

📄 Document Contents
[Present complete case report]

Document can be used for:
- Maintenance record archive
- Training case study
- Knowledge base contribution

Any information you'd like to add or modify?"
```

### Anti-Pattern: Do NOT Do This

❌ **Wrong**: Delegate to subagent or background task for report generation  
❌ **Wrong**: Summarize diagnostic history and pass to another agent  
❌ **Wrong**: `new_task` or subagent delegation for case documentation

✅ **Correct**: Load `case-document` skill as reference, generate report in current agent context  
✅ **Correct**: Use complete dialogue history to fill templates  
✅ **Correct**: Present directly to user from current agent

---

## Error Handling

| Scenario | Response |
|----------|----------|
| User cannot perform recommended test | Offer alternative test or document limitation |
| Result contradicts all hypotheses | Document anomaly, expand hypothesis list |
| User questions diagnosis logic | Explain reasoning, consider additional verification |
| Confidence not improving | Recommend expert consultation |

---

## Safety and Boundaries

### Safety Critical

- Identify and flag safety concerns immediately
- Recommend qualified technician for safety-critical systems
- Never bypass safety procedures

### Scope Limitations

When to escalate or conclude:
- Confidence cannot reach threshold
- Required testing exceeds user capability
- Safety concerns identified
- User requests expert involvement
