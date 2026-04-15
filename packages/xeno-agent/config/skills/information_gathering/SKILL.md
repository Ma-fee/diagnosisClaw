---
name: information-gathering
description: Conduct structured information collection for fault diagnosis, technical support, and troubleshooting scenarios. Guides users through dynamic, priority-based questioning to efficiently gather critical context including equipment details, fault descriptions, operating conditions, and maintenance history. Use when starting any diagnostic or technical assistance task where comprehensive context is needed but incomplete. Prioritizes information gaps by diagnostic impact rather than forcing complete collection.
---

# Information Gathering Skill

## Overview

Structured information collection for diagnostic and technical support contexts. Uses dynamic, priority-based questioning to efficiently gather critical details while respecting user constraints.

## When to Use

Use at the beginning of any diagnostic, troubleshooting, or technical support workflow:

- Initial fault report is vague or incomplete
- Need to establish baseline context for diagnosis
- User describes symptoms but lacks technical details
- Transitioning from general inquiry to specific investigation
- Current information insufficient for diagnostic planning

## Output

Produces a structured context document containing:
- Equipment/system identification
- Fault/symptom description
- Operating conditions
- Historical context
- Information completeness assessment

## Information Categories

### 1. System Identification

**Priority**: Critical (blocks further diagnosis if unknown)

| Field | Description | Example |
|-------|-------------|---------|
| equipment_type | General category | Excavator, Generator, Server |
| manufacturer | Brand/OEM | Caterpillar, Cummins, Dell |
| model | Specific model | 320D, QSB6.7, PowerEdge R740 |
| serial_number | Unique identifier (if available) | XXX12345 |
| specifications | Key technical specs | Capacity, power rating, voltage |

### 2. Fault Description

**Priority**: Critical

| Field | Description | Collection Approach |
|-------|-------------|---------------------|
| primary_symptom | Main observable issue | What exactly is wrong? |
| symptom_details | Specifics (quantify where possible) | How severe? How often? |
| onset_pattern | When/how did it start? | Sudden vs gradual? |
| operating_state | Conditions when fault occurs | Under load? At startup? |
| warnings_alarms | Any indicators triggered | Codes, lights, messages |

### 3. Operating Conditions

**Priority**: High (aids hypothesis generation)

| Field | Relevance |
|-------|-----------|
| ambient_environment | Temperature, humidity, dust |
| workload_intensity | Load factor, duty cycle |
| operating_parameters | Pressure, temperature, speed readings |
| duration_of_operation | Hours at fault occurrence |
| maintenance_status | Recent service, fluid levels |

### 4. Historical Context

**Priority**: Medium (pattern recognition)

| Field | Value |
|-------|-------|
| recent_changes | Modifications, repairs, relocations |
| previous_similar_issues | Past occurrences, resolutions |
| maintenance_history | Service intervals, known weak points |
| age_usage | Operating hours, installation date |

## Collection Strategy

### Priority-Based Questioning

Not all information has equal diagnostic value. Adjust priorities dynamically:

#### Critical Priority (Always ask first)

1. **Equipment identification**
   - Without model/manufacturer, cannot retrieve specifications
   - Blocks all subsequent planning

2. **Primary fault description**
   - Must understand what is wrong
   - Quantify severity when possible

#### High Priority (Ask if time permits)

3. **Operating conditions at fault occurrence**
   - Contextualizes the symptom
   - Often reveals contributing factors

4. **Maintenance status**
   - Recent service often correlates with new faults
   - Fluid levels are quick checks with high yield

#### Medium Priority (Ask selectively)

5. **Historical context**
   - Relevant for intermittent/recurring issues
   - May be skipped for obvious acute failures

6. **Detailed specifications**
   - Can often be retrieved once model is known

### Question Design Guidelines

#### One Question at a Time

Present single, focused questions with clear options:

```
❌ "What is the equipment model, when did the fault start, and what are the symptoms?"

✓ "What is the equipment model and manufacturer?"
   Options:
   - [Provide model]
   - "I don't know the exact model"
   - "I don't have other details, just start diagnosis"
```

#### Provide Escape Options

Always include:
- "I don't know" option for each question
- "Skip remaining questions" option
- "That's all the information I have" option

#### Adaptive Follow-up

Based on responses, adjust subsequent questions:

```
User: "The pump is making a loud grinding noise"

↓

Next question adapts:
"When does the grinding noise occur?"
- Only at startup
- Continuous during operation
- Under heavy load only
- Intermittently

↓

If "Under heavy load":
Next question: "What is the pump operating pressure when the noise occurs?"
```

## Collection Workflow

### Step 1: Initial Assessment

Analyze initial user description:

```
Input: "My excavator engine is overheating"

Analysis:
- equipment_type: Excavator ✓
- manufacturer: Unknown ✗ (CRITICAL)
- model: Unknown ✗ (CRITICAL)
- primary_symptom: Engine overheating ✓
- symptom_details: Unknown (HIGH)
- onset_pattern: Unknown (MEDIUM)
- operating_conditions: Unknown (MEDIUM)
```

### Step 2: Dynamic Questioning

Generate questions based on gaps, ordered by priority:

```
1. [CRITICAL] "What is the excavator manufacturer and model?"
2. [CRITICAL] "Can you describe the overheating symptom in more detail?"
   - Temperature gauge reading?
   - How quickly does it overheat?
3. [HIGH] "What was the excavator doing when it started overheating?"
   - Idle / Light work / Heavy digging
4. [HIGH] "When did you last check coolant level?"
5. [MEDIUM] "Has this happened before?"
6. [MEDIUM] "Any recent maintenance or repairs?"
```

### Step 3: Sufficiency Assessment

Determine if collected information is sufficient:

**Sufficient when**:
- Equipment is identified (type + manufacturer + model)
- Primary fault is clearly described
- At least 2-3 high-priority context items collected

**Insufficient when**:
- Critical equipment details missing
- Fault description too vague to form hypotheses
- User cannot provide minimum viable context

### Step 4: Structured Output

Format collected information:

```yaml
information_gathering_report:
  timestamp: "2024-01-15T10:30:00Z"
  
  equipment:
    type: "Crawler excavator"
    manufacturer: "Sany"
    model: "Sy215c"
    engine: "Cummins QSB6.7"  # Retrieved if model known
    
  fault_description:
    primary: "Engine overheating"
    details:
      - "Temperature gauge enters red zone"
      - "Occurs after approximately 30 minutes operation"
      - "Problem is consistent and repeatable"
    severity: "High - equipment must stop"
    onset: "Gradual - develops over 30 min"
    
  operating_conditions:
    ambient_temperature: "35°C"
    workload: "Heavy digging, continuous"
    hours_at_fault: "~4500 total machine hours"
    
  historical_context:
    last_service: "500 hours ago"
    recent_changes: "None reported"
    similar_history: "Unknown"
    
  information_completeness:
    status: "sufficient"
    critical_gaps: []
    recommended_additions:
      - "Coolant level check"
      - "Maintenance log review"
```

## Decision Outputs

### Sufficient Information

```
Status: sufficient
Proceed: To diagnostic planning
Confidence: High
Gaps: Minor, non-blocking
```

### Partial Information

```
Status: partial
Proceed: To diagnostic planning with caveats
Confidence: Medium
Gaps: Some context items unknown, but core identification complete
```

### Insufficient Information

```
Status: insufficient
Proceed: Continue information gathering or recommend on-site inspection
Confidence: Low
Gaps: Critical equipment or fault details missing
```

## Special Handling Scenarios

### User Cannot Identify Equipment

If user cannot provide manufacturer/model:

1. Ask for any visible labels, nameplates, or documentation
2. Request photos if visual inspection possible
3. Gather descriptive details (size, color, features)
4. If still unknown: Note in report, mark as limitation

### Vague Symptom Description

If user describes issue unclearly:

1. Ask for specific observable behaviors
2. Request quantification ("loud" → "how loud compared to normal?")
3. Provide comparison options:
   - "Is it like [example A] or [example B]?"
4. If user cannot clarify: Document as "subjective symptom"

### Emergency Situations

If user indicates safety concern:

1. Prioritize safety guidance
2. Recommend immediate qualified technician
3. Note safety context in report
4. Proceed with information gathering only if safe to do so

## Integration with Diagnostic Workflow

### Next Steps After This Skill

For **sufficient** information:
```
→ Delegate to diagnosis-planning with structured context
```

For **partial** information:
```
→ Delegate to diagnosis-planning with uncertainty notes
→ Planning skill should retrieve missing specifications
```

For **insufficient** information:
```
→ Report to parent skill (systematic-troubleshooting)
→ Recommend: On-site technician inspection
→ Or: Request user to gather documentation and return
```

## Conversation Management

### Tracking State

Maintain current collection state:

```yaml
collection_state:
  collected:
    equipment: {manufacturer: "Sany", model: "Sy215c"}
    fault: {primary: "Engine overheating", details: [...]}
  pending_questions:
    - operating_conditions
    - historical_context
  completeness: "partial"
  last_question: "What was the ambient temperature?"
```

### Handling Interruptions

If user provides information out of order:
- Accept and integrate
- Acknowledge receipt
- Resume with next appropriate question

If user asks questions during collection:
- Answer briefly if simple
- Defer complex answers: "Good question - let's finish collecting information, then I'll explain"
- Note question for later follow-up

## Report Template

```markdown
## Information Gathering Report

### Equipment Identification
- Type: [equipment_type]
- Manufacturer: [manufacturer]
- Model: [model]
- Key Specifications: [specs or "to be retrieved"]

### Fault Description
- Primary Symptom: [description]
- Details: [quantified observations]
- Severity: [assessment]
- Pattern: [onset, frequency, conditions]

### Operating Context
- Environment: [ambient conditions]
- Workload: [operating intensity]
- Parameters: [measured values if known]
- Maintenance Status: [recent service, fluid levels]

### Historical Information
- Recent Changes: [modifications, repairs]
- Previous Issues: [similar faults, resolutions]
- Service History: [maintenance record summary]

### Completeness Assessment
- Status: [sufficient|partial|insufficient]
- Accuracy: [user-provided|estimated|unknown]
- Critical Gaps: [list or "none"]
- Recommended Actions: [additional data to collect]

---
Generated: [timestamp]
Confidence: [high|medium|low]
```

## Key Principles

1. **Efficiency over completeness**: Gather enough to proceed, not everything
2. **User-friendly**: One question at a time, clear options
3. **Adaptive**: Adjust priorities based on what matters for this fault
4. **Transparent**: Report what is known and unknown
5. **Respectful**: Provide escape options, don't force answers
