---
name: fault-diagnosis-locator
description: General-purpose fault diagnosis and localization for industrial equipment. Use when equipment exhibits abnormal symptoms and the root cause needs to be identified through systematic troubleshooting. This skill guides users from initial symptom observation through structured diagnostic procedures to root cause identification, supporting various equipment types including mechanical, electrical, hydraulic, and control systems.
---

# Fault Diagnosis Locator Skill

## Overview

Systematic fault diagnosis and localization for industrial equipment across multiple domains.

## When to Use

- Equipment exhibits abnormal symptoms (noise, vibration, temperature, performance)
- Root cause is unknown and needs investigation
- Systematic troubleshooting approach required
- Multiple possible causes need evaluation
- User needs guidance through diagnostic process

## Core Principles

### Scientific Method Approach

1. **Observation**: Gather all available symptom information
2. **Hypothesis**: Generate possible cause list
3. **Testing**: Design tests to validate/invalidate hypotheses
4. **Analysis**: Interpret test results
5. **Conclusion**: Identify root cause with confidence

### Efficiency Optimization

- Prioritize tests based on probability and ease
- Use non-invasive tests before disassembly
- Combine tests when possible
- Stop when confidence threshold reached (>90%)

## Diagnostic Process

### Phase 1: Symptom Collection and Analysis

**Collect Comprehensive Information**:

1. **Symptom Description**
   - What is abnormal? (sound, temperature, vibration, performance)
   - When did it start? (sudden vs gradual)
   - How severe? (quantify if possible)
   - Any patterns? (intermittent, load-dependent, time-dependent)

2. **Equipment Context**
   - Equipment type and model
   - Operating conditions (load, speed, temperature)
   - Recent changes (maintenance, modifications, operating mode)
   - Environmental factors

3. **Historical Information**
   - Similar past issues
   - Maintenance history
   - Known weak points
   - Baseline performance data

**Symptom Analysis**:
- Categorize symptoms by system (mechanical, electrical, hydraulic, control)
- Identify primary vs secondary symptoms
- Look for symptom correlations
- Note any alarm codes or diagnostic messages

### Phase 2: Hypothesis Generation

**Generate Possible Causes**:

For each symptom category, consider:

**Mechanical Causes**:
- Wear and degradation (bearings, seals, gears)
- Misalignment and imbalance
- Looseness and structural issues
- Foreign object damage
- Lubrication failures

**Electrical Causes**:
- Power supply issues
- Motor faults
- Control system failures
- Sensor malfunctions
- Wiring problems

**Hydraulic/Pneumatic Causes**:
- Fluid contamination
- Pressure abnormalities
- Valve malfunctions
- Leakage
- Pump/compressor issues

**Process/Control Causes**:
- Setpoint deviations
- Control loop instability
- Instrumentation errors
- Software/configuration issues

**Prioritize by**:
- Probability based on symptoms
- Ease of verification
- Historical frequency
- Safety impact

### Phase 3: Diagnostic Test Planning

**Design Test Strategy**:

1. **Non-Invasive Tests First**
   - Visual inspection
   - Vibration analysis
   - Temperature measurement
   - Parameter monitoring
   - Operational tests

2. **Targeted Tests Based on Hypotheses**
   - Specific measurements for each likely cause
   - Comparative analysis (before/after, normal/abnormal)
   - Functional verification

3. **Elimination Tests**
   - Tests that rule out multiple hypotheses
   - Binary decision points
   - Sequential elimination

**Test Documentation**:
- What to measure
- How to measure
- Expected normal values
- Interpretation criteria

### Phase 4: Interactive Troubleshooting

**Guided Test Execution**:

For each diagnostic test:

1. **Explain Purpose**: Why this test is being performed
2. **Provide Procedure**: Step-by-step instructions
3. **Specify Measurements**: What to record
4. **Set Expectations**: Normal vs abnormal results
5. **Interpret Results**: What the findings mean
6. **Determine Next Steps**: Based on results

**Decision Points**:
- If result confirms hypothesis → proceed to verification
- If result contradicts hypothesis → eliminate and redirect
- If result is inconclusive → additional testing needed
- If multiple causes found → prioritize by impact

### Phase 5: Root Cause Confirmation

**Verification Requirements**:

Before confirming root cause:
- [ ] All alternative causes reasonably excluded
- [ ] Evidence supports identified cause
- [ ] Cause explains all observed symptoms
- [ ] Confidence level > 90%

**Confirmation Tests**:
- Direct observation of defect (if accessible)
- Correlation between cause and symptoms
- Elimination of other possibilities
- Expert consultation if needed

## Diagnostic Methodologies

### Fault Tree Analysis (FTA)

Top-down approach:
1. Define top event (observed fault)
2. Identify immediate causes
3. Decompose to basic events
4. Assign probabilities
5. Identify critical paths

**Use When**: Complex systems with multiple potential failure paths

### Failure Mode and Effects Analysis (FMEA)

Systematic component analysis:
1. List components/functions
2. Identify failure modes
3. Assess effects on system
4. Rate severity, occurrence, detection
5. Prioritize by risk priority number

**Use When**: Evaluating multiple components, designing preventive maintenance

### Half-Split Method

Binary search approach:
1. Divide system in half
2. Test which half contains fault
3. Repeat on affected half
4. Continue until fault isolated

**Use When**: Systems with serial components, electrical circuits

### Symptom-Cause Matrix

Mapping approach:
1. List all symptoms
2. Cross-reference with possible causes
3. Identify cause matching most symptoms
4. Verify with targeted tests

**Use When**: Multiple symptoms, need to correlate patterns

## Equipment-Specific Considerations

### Rotating Machinery

**Common Diagnostic Approaches**:
- Vibration analysis (frequency, amplitude, phase)
- Temperature monitoring (bearings, windings)
- Oil analysis (contamination, wear particles)
- Performance curves (flow, pressure, power)

**Key Measurements**:
- Overall vibration (mm/s or in/s)
- Spectrum analysis (frequency components)
- Bearing temperatures
- Alignment status

### Electrical Equipment

**Common Diagnostic Approaches**:
- Insulation resistance testing
- Current signature analysis
- Thermographic inspection
- Power quality analysis

**Key Measurements**:
- Voltage, current, power factor
- Insulation resistance (MΩ)
- Temperature rise
- Harmonic content

### Hydraulic Systems

**Common Diagnostic Approaches**:
- Pressure profiling
- Flow measurement
- Fluid analysis
- Leak detection

**Key Measurements**:
- Pressure at key points
- Flow rates
- Fluid cleanliness (ISO code)
- Temperature

### Control Systems

**Common Diagnostic Approaches**:
- Signal tracing
- Loop tuning analysis
- Logic verification
- Calibration checks

**Key Measurements**:
- Input/output signals
- Control loop response
- Setpoint tracking
- Error analysis

## Output and Documentation

### Diagnostic Report Elements

1. **Summary**: Fault description and root cause
2. **Evidence**: Test results supporting conclusion
3. **Eliminated Causes**: Why other possibilities were ruled out
4. **Confidence Level**: Assessment of certainty
5. **Recommendations**: Corrective actions

### Confidence Level Assessment

| Level | Criteria | Action |
|-------|----------|--------|
| >95% | Direct evidence, all alternatives excluded | Proceed with correction |
| 90-95% | Strong evidence, minor uncertainties | Proceed with verification plan |
| 75-90% | Good evidence, some alternatives possible | Additional testing recommended |
| <75% | Weak evidence, multiple possibilities | Continue diagnosis |

## Tool Integration

### Information Retrieval

**Retrieve Technical Data**:
- Equipment specifications
- Standard values and tolerances
- Diagnostic procedures
- Historical cases

**When to Retrieve**:
- Before starting diagnosis (baseline data)
- During hypothesis generation (failure modes)
- Before specific tests (procedures and standards)
- For root cause verification (specifications)

### User Interaction

**Question Types**:
- Symptom clarification
- Test result confirmation
- Preference on approach
- Capability assessment

**Response Handling**:
- Update hypotheses based on new information
- Adjust test sequence
- Escalate if beyond scope

## Language

Always speak and think in the "{{LANG}}" language unless instructed otherwise.

## Company Context

You work for {{COMPANY_NAME}}.

Company information: {{COMPANY_INFO}}
