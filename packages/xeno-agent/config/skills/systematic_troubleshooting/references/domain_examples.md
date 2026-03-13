# Domain-Specific Diagnostic Examples

This document provides examples of how to use the systematic-troubleshooting skill for specific equipment types.

## Example: Hydraulic Excavator Engine Overheating

This example demonstrates a complete diagnostic workflow for a common excavator fault.

---

### Scenario

User reports: "My Sy215c excavator engine is overheating after 30 minutes of operation. Temperature gauge is in the red zone."

### Phase 1: Information Collection

**Initial context from user**:
- Equipment: Sany Sy215c crawler excavator
- Symptom: Engine overheating (temperature gauge red)
- Pattern: Occurs after 30 minutes operation
- No other symptoms mentioned

**Delegate to information-gathering skill** with:
```
Equipment type: Sany Sy215c crawler excavator
Fault: Engine overheating after 30 minutes
Known symptoms: Temperature gauge in red zone
Request: Collect complete diagnostic context
```

**Receive structured context**:
```yaml
equipment:
  model: Sany Sy215c
  type: Crawler excavator
  engine: Cummins QSB6.7
  hours: 4500
symptoms:
  primary: Engine overheating
  observations:
    - Temperature gauge enters red zone after ~30 min
    - Problem is consistent/repeatable
    - No alarm codes reported
operating_conditions:
  ambient_temp: "35°C (hot summer day)"
  workload: "Heavy digging, continuous operation"
  coolant_level: "User unsure, will check"
maintenance_history:
  last_service: 500 hours ago
  recent_changes: None reported
information_completeness: sufficient
```

**Decision**: Information sufficient → Proceed to Phase 2

---

### Phase 2: Diagnostic Planning

**Delegate to diagnosis-planning skill** with:
```
Equipment: Sany Sy215c, Cummins QSB6.7 engine
Fault: Engine overheating after sustained operation
Context: [structured context from Phase 1]
Request: Generate comprehensive diagnostic plan
```

**Key elements from planning report**:

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

**Guide**: "First, let's check the coolant level. This is the most common cause of overheating. Please:

1. Allow engine to cool completely (at least 30 minutes)
2. Open the radiator cap (carefully - check no pressure)
3. Check coolant level - should be visible at filler neck
4. Check overflow reservoir - should be between MIN and MAX marks

What do you observe?"

**Options provided**:
- "Coolant level is normal in both radiator and reservoir"
- "Coolant is low in radiator but reservoir is OK"
- "Coolant is low in both"
- "Cannot check safely (engine still hot)"

**User response**: "Coolant level is low in both radiator and reservoir"

**Interpretation**: 
- Confirms hypothesis "Low coolant level" (High probability)
- Need to identify leak source
- Update confidence: Low coolant cause 80% → 90%

**Update todo**:
```
[x] Step 1: Check coolant level - ABNORMAL (low)
[ ] Step 1b: Identify coolant leak source
[ ] Step 2: Inspect radiator
...
```

**Step 1b execution**:

**Guide**: "Low coolant explains the overheating. Now we need to find where it's leaking. Common leak points on excavators:

1. **Radiator**: Look for wet spots, white residue, or visible drips
2. **Hoses**: Check upper/lower radiator hoses and heater hoses
3. **Water pump**: Look for weep hole leakage
4. **Heater core**: Check cabin floor for wetness
5. **Head gasket**: Check for milky oil or bubbling in radiator

Visual inspection results?"

**User response**: "I see white crusty residue on the top tank of the radiator, near a hose connection"

**Interpretation**:
- Identified leak source: radiator tank seam or hose connection
- Root cause is likely radiator leak + low coolant
- Confidence: 95%

**Update todo**:
```
[x] Step 1: Check coolant level - ABNORMAL (low)
[x] Step 1b: Identify leak source - FOUND (radiator hose connection)
[ ] Step 2: Inspect radiator condition
```

**Step 2 execution**:

**Guide**: "Good find. Now let's assess the radiator condition to determine if this is repairable or needs replacement:

1. Check for additional leak points (pinholes, seam cracks)
2. Inspect radiator fins - should be clean and straight
3. Check for physical damage (bent fins, dents)
4. Look for oil contamination in coolant (possible oil cooler leak)

Radiator condition?"

**User response**: "Fins look OK, just dirty. The leak seems to be just at the hose connection"

**Decision**: Root cause identified with 95% confidence

---

### Phase 4: Root Cause Confirmation

**Verification checklist**:

- [x] All symptoms explained: Overheating caused by low coolant from radiator leak
- [x] Alternatives excluded: Thermostat, pump, belt issues not tested but primary cause identified
- [x] Evidence supports: Visual confirmation of leak location
- [x] Confidence: 95%

**Present to user**:

"**Root Cause Identified (95% confidence)**

**Primary Cause**: Coolant leak at radiator hose connection leading to low coolant level

**Evidence**:
1. Coolant level low in both radiator and reservoir
2. Visual confirmation of leak at hose connection (white residue)
3. Timeline matches: Leak gradual, caused overheating after 30min operation

**Recommended Actions**:
1. **Immediate**: Add coolant to reach proper level
2. **Repair**: Replace radiator hose and clamp at connection point
3. **Verification**: Monitor coolant level and temperature after repair

Do you want to proceed with documentation?"

**User confirmation**: Yes

---

### Phase 5: Case Documentation

**Delegate to case-document skill** with:

```yaml
case_summary:
  equipment: Sany Sy215c
  fault: Engine overheating
  root_cause: Coolant leak at radiator hose connection
  confidence: 95%
  
diagnostic_history:
  phase1: [context collection details]
  phase2: [planning report reference]
  phase3:
    - step1: Coolant check - ABNORMAL (low)
    - step1b: Leak source identification - FOUND at hose connection
    - step2: Radiator inspection - minor dirt, otherwise OK
  phase4: Root cause confirmed
  
repair_actions:
  - Added coolant to proper level
  - Replaced upper radiator hose and clamp
  - Pressure tested system (passed)
  
verification:
  - Monitored for 2 hours operation
  - Temperature normal (85-90°C)
  - No coolant loss observed
  
lessons_learned:
  - Routine coolant level checks prevent overheating
  - White residue is early indicator of small leaks
```

**Receive case report** (structured document with sections, tables, Mermaid diagrams)

---

### Key Takeaways from This Example

1. **Information gathering** identified a clean, repeatable fault pattern
2. **Diagnostic planning** provided hypothesis prioritization and standard values
3. **Interactive execution** followed the plan but adjusted when root cause was found early
4. **Confidence tracking** allowed early termination when 95% reached
5. **Documentation** captured lessons for knowledge base

This demonstrates how systematic-troubleshooting orchestrates all phases while leveraging specialized skills for information gathering, planning, and documentation.
