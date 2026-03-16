# Domain-Specific Diagnostic Examples

Complete workflow examples for the systematic troubleshooting skill.

---

## Example: Hydraulic Excavator Engine Overheating

### Scenario

User reports: "My Sy215c excavator engine is overheating after 30 minutes of operation. Temperature gauge is in the red zone."

---

### Phase 1: Information Collection

**Initial context from user**:
- Equipment: Sany Sy215c crawler excavator
- Symptom: Engine overheating (temperature gauge red)
- Pattern: Occurs after 30 minutes operation
- No other symptoms mentioned

**Interactive collection** (skill guides user):

```
 Skill: "To help diagnose this properly, I need to collect some information:

 1. What's the exact model of your excavator? (You mentioned Sy215c - is it the standard or Pro version?)
 2. How many operating hours does it have?
 3. What's the ambient temperature today?
 4. What type of work were you doing when it overheated?
 5. When was the last maintenance service?"

 User provides:
 - Model: Sany Sy215c standard, confirmed
 - Hours: 4500 hours
 - Ambient: 35°C (95°F), hot summer day
 - Work: Heavy digging, continuous operation
 - Last service: 500 hours ago
```

**Decision**: Information sufficient → Proceed to Phase 2

---

### Phase 2: Diagnostic Planning

**Delegation to research agent**:

```
Delegate with:
- Equipment: Sany Sy215c, Cummins QSB6.7 engine
- Fault: Engine overheating after sustained operation
- Context: 4500 hours, 35°C ambient, heavy digging work
- Request: Generate comprehensive diagnostic plan
```

**Key planning outputs**:

| Possible Cause | Probability | Key Inspection |
|---------------|-------------|----------------|
| Low coolant level | High | Check radiator and reservoir |
| Clogged radiator | High | Visual inspection, temperature differential |
| Faulty thermostat | Medium | Temperature at hoses |
| Water pump failure | Medium | Coolant flow inspection |
| Fan belt issues | Medium | Belt tension and condition |
| Head gasket leak | Low | Combustion gas in coolant test |

**Standard values from report**:
- Normal operating temperature: 82-93°C
- Coolant capacity: 25L
- Thermostat opening: 82°C
- Radiator fin clearance: >5mm between fins

**User presentation** (in user's language):

```
"Diagnostic plan completed:

📋 Possible Causes (ranked):
1. Low coolant level - High probability - Check radiator and reservoir
2. Clogged radiator fins - High probability - Visual inspection needed
3. Faulty thermostat - Medium probability - Check hose temperatures
4. Water pump failure - Medium probability - Check coolant flow
5. Fan belt problems - Medium probability - Inspect condition
6. Head gasket leak - Low probability - Test if other checks fail

📋 Inspection Plan:
- 6 diagnostic steps
- Estimated time: 30-45 minutes
- Safety note: Let engine cool before opening radiator

Shall we begin the interactive diagnosis?"
```

---

### Phase 3: Interactive Execution

**Setup todo list**:
```
[ ] Step 1: Check coolant level in radiator and reservoir
[ ] Step 2: Inspect radiator for clogging/damage
[ ] Step 3: Check thermostat operation
[ ] Step 4: Verify water pump operation
[ ] Step 5: Inspect fan belt condition and tension
[ ] Step 6: Pressure test cooling system (if needed)
```

**Step 1 execution**:

```
 Skill: "First, let's check coolant level - most common cause of overheating.

⚠️ SAFETY: Allow engine to cool completely (30+ minutes) before opening radiator.

Procedure:
1. Open radiator cap carefully - check no pressure by pressing down slightly first
2. Check coolant level - should be visible at filler neck
3. Check overflow reservoir - should be between MIN and MAX marks

What do you observe?

A) Coolant level normal in both radiator and reservoir
B) Coolant low in radiator but reservoir OK
C) Coolant low in both radiator and reservoir
D) Cannot check safely right now"

 User: "C) Coolant is low in both radiator and reservoir"
```

**Interpretation**: Low coolant confirmed, updates confidence:
- Coolant leak: 40% → 80%
- Other causes deferred

**Update progress**:
```
Diagnostic Progress (1/6 steps completed)
========================
[✓] Step 1: Check coolant level - ABNORMAL (low in both)
[→] Step 2: Identify leak source - Current step
[ ] Steps 3-6: Pending (may skip if leak found)

Current hypothesis confidence:
• Coolant leak ............... 80% ↑ (major finding)
• Clogged radiator ........... 40%
• Thermostat failure ......... 15%
```

**Step 2: Find leak source**:

```
 Skill: "Low coolant explains the overheating. Now let's find where it's leaking.

Common leak points on excavators:
1. Radiator - Look for wet spots, white residue, visible drips
2. Hoses - Check upper/lower radiator hoses
3. Water pump - Check weep hole for leakage
4. Heater core - Check cabin floor for wetness
5. Head gasket - Check for milky oil or bubbling

Visual inspection results?"

 User: "I see white crusty residue on the top tank of the radiator, near a hose connection"
```

**Interpretation**: Leak source identified - radiator hose connection
- Root cause confidence: 95%
- Can skip remaining routine checks

**Update progress**:
```
Diagnostic Progress (2/6 steps completed)
========================
[✓] Step 1: Check coolant level - ABNORMAL (low)
[✓] Step 2: Identify leak source - FOUND (radiator hose connection)
[✓] Root cause confidence: 95% - Ready for confirmation

Root cause identified early - proceeding to Phase 4
```

---

### Phase 4: Root Cause Confirmation

```
 Skill: "Based on our investigation, let's confirm the root cause:

✅ Symptom Explanation
Engine overheating is explained by low coolant from the radiator leak:
- Temperature rises after 30 min (time to deplete remaining coolant)
- Gauge enters red zone (insufficient cooling capacity)

✅ Alternative Causes Excluded
While we didn't test all alternatives, the leak provides direct evidence:
- Clogged radiator: Not ruled out but secondary to leak
- Thermostat/water pump: Normal behavior expected once coolant restored
- Head gasket: No signs (no white smoke, no milky oil)

✅ Confidence Assessment
Current confidence: 95%

✅ Recommended Actions
1. Immediate: Add coolant to proper level for safe operation
2. Repair: Replace upper radiator hose and clamp at connection
3. Verification: Monitor coolant level and temperature after repair

Do you confirm this is the correct root cause?"

 User: "Yes, that makes sense"
```

---

### Phase 5: Case Documentation

**Generate in current context** (do not delegate):

```markdown
# Diagnostic Case Report

## Executive Summary
- **Equipment**: Sany Sy215c crawler excavator
- **Fault**: Engine overheating
- **Root Cause**: Coolant leak at radiator hose connection
- **Confidence**: 95%
- **Resolution**: Replaced hose and clamp

## Equipment Details
- Model: Sany Sy215c
- Engine: Cummins QSB6.7
- Operating Hours: 4500
- Date: [Current date]

## Diagnostic Timeline

### Phase 1: Information Collection (5 minutes)
- Equipment identified: Sany Sy215c, 4500 hours
- Operating conditions: 35°C ambient, heavy digging
- Last service: 500 hours ago

### Phase 2: Diagnostic Planning (delegated)
- Received comprehensive plan with 6 possible causes
- Prioritized by probability: coolant issues, radiator, thermostat

### Phase 3: Interactive Execution (20 minutes)
- Step 1: Coolant level check - ABNORMAL (low in both)
- Step 2: Leak identification - FOUND at upper hose connection
- Root cause identified with 95% confidence
- Skipped steps 3-6 (unnecessary after root cause found)

### Phase 4: Root Cause Confirmation
- User confirmed: Coolant leak at radiator hose connection
- All symptoms explained by this cause
- Confidence: 95%

## Evidence Summary

| Check | Result | Implication |
|-------|--------|-------------|
| Coolant level | Low in radiator and reservoir | Leak exists |
| Visual inspection | White residue at hose connection | Leak location identified |
| Symptom timeline | Overheating after 30 min operation | Gradual coolant loss pattern |

## Corrective Actions
1. **Immediate**: Added coolant to proper level
2. **Repair**: Replaced upper radiator hose and clamp
3. **Verification**: Pressure tested system (passed)

## Post-Repair Verification
- Monitored for 2 hours operation
- Temperature normal: 85-90°C
- No coolant loss observed
- Equipment returned to service

## Lessons Learned
1. **Preventive**: Routine coolant level checks can prevent overheating
2. **Early detection**: White residue is an early indicator of small leaks
3. **Efficiency**: Interactive diagnosis identified root cause in 2 steps

## Root Cause Analysis
The coolant leak at the radiator hose connection was caused by:
- Age/wear of hose clamp at 4500 operating hours
- Heat cycling stress from heavy digging operations
- Gradual loosening of connection

The leak was slow enough that coolant level dropped over ~30 minutes of operation, explaining the delayed overheating symptom.
```

**Present to user**:

```
"Case documentation completed:

📄 Document includes:
- Executive summary with root cause and confidence
- Complete diagnostic timeline with all steps
- Evidence table with findings
- Corrective actions taken
- Lessons learned for future prevention

This document is ready for:
- Maintenance record archive
- Training case study
- Knowledge base contribution

Any information you'd like to add or modify?"
```

---

## Key Takeaways from This Example

1. **Information gathering** captured specific operating conditions that helped focus diagnosis
2. **Planning phase** provided prioritized hypotheses to guide efficient investigation
3. **Interactive execution** quickly identified root cause in 2 steps
4. **Early termination** of routine checks when confidence threshold reached (95%)
5. **Complete documentation** captured all details for future reference

The example demonstrates how systematic-troubleshooting orchestrates all phases while leveraging:
- Delegated research for planning
- Interactive guidance for execution
- Current context for documentation
- User confirmation at each phase gate