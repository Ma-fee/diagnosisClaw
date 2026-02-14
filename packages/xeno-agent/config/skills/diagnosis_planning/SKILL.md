---
name: diagnosis-planning
description: Generate comprehensive diagnostic planning reports for equipment failures. Use when the user has provided initial fault information and needs a structured diagnostic plan including possible causes, inspection steps, required tools, standard values, and troubleshooting flowcharts. This skill creates actionable diagnostic roadmaps before actual troubleshooting begins.
---

# Diagnosis Planning Skill

## Overview

Generate comprehensive diagnostic planning reports that serve as roadmaps for systematic equipment fault diagnosis.

## When to Use

- User has described equipment fault symptoms
- Need to create structured diagnostic approach before troubleshooting
- Planning inspection steps and resource requirements
- Preparing troubleshooting flowcharts or FTA diagrams

## Core Workflow

### Step 1: Information Collection

Collect and verify essential fault information:

**Required Information Categories**:

1. **Equipment Identity**
   - Equipment type and model
   - Serial numbers or asset tags
   - Installation location

2. **Fault Phenomena**
   - Symptom description (sounds, smells, visual cues)
   - Alarm codes or error messages
   - Abnormal behavior patterns
   - Time of occurrence and frequency

3. **Operating Parameters**
   - Current load conditions
   - Temperature readings
   - Pressure values
   - Vibration levels
   - Power consumption

4. **Maintenance History**
   - Recent repairs or replacements
   - Preventive maintenance schedule
   - Known recurring issues

5. **Environmental Conditions**
   - Ambient temperature and humidity
   - Dust or contamination levels
   - Operating environment characteristics

**Collection Strategy**:
- Ask one question at a time
- Prioritize based on initial description completeness
- Offer option: "I don't have more details, proceed with diagnosis planning"
- Confirm final fault description before generating plan

### Step 2: Generate Diagnostic Planning Report

Create comprehensive report with the following structure:

#### Section 1: Executive Summary

Brief overview of:
- Equipment and fault description
- Diagnostic approach summary
- Expected timeline and resources

#### Section 2: Possible Failure Causes

List potential causes with:
- **Cause Description**: What could be wrong
- **Probability**: High/Medium/Low based on symptoms
- **Supporting Evidence**: Why this cause is suspected
- **Quick Check**: Simple test to validate/invalidate

#### Section 3: Inspection Steps and Priorities

Ordered checklist with:
- **Step Number**: Sequential identifier
- **Inspection Item**: What to check
- **Priority**: Critical/High/Medium/Low
- **Method**: How to perform the check
- **Standard Value**: Expected normal range
- **Tools Required**: Equipment needed
- **Estimated Time**: Duration estimate

#### Section 4: Required Tools and Documents

**Tools**:
- Measurement instruments (multimeter, vibration analyzer, etc.)
- Hand tools (wrenches, screwdrivers, etc.)
- Safety equipment (PPE, lockout/tagout)

**Documents**:
- Equipment manuals
- Schematics and diagrams
- Maintenance records
- Previous case reports

#### Section 5: Standard Values Reference

Tabular reference of:
- Parameter names
- Normal operating ranges
- Warning thresholds
- Critical limits
- Units of measurement

#### Section 6: Troubleshooting Flowchart

Mermaid diagram showing:
- Decision points based on symptoms
- Inspection sequence
- Branching logic for different findings
- Termination conditions (root cause found)

**Mermaid Syntax Rules**:
- Quote all string values with double quotes
- Use descriptive node labels
- Include edge labels for decision branches
- Structure: graph TD for top-down flow

### Step 3: Present Plan and Offer Next Steps

After presenting the diagnostic plan:
- Ask if user wants to proceed with multi-round interactive troubleshooting
- Offer to adjust priorities based on user's constraints
- Provide option to start with highest probability cause

## Output Format

Use structured markdown with:
- Clear section headers
- Tables for tabular data
- Mermaid diagrams for flowcharts
- Bullet points for lists
- Bold text for emphasis

## Examples

See `examples/` directory for sample diagnostic planning reports:
- `pump_overheating.md`: Centrifugal pump overheating diagnosis
- `motor_vibration.md`: Electric motor excessive vibration diagnosis
- `valve_leakage.md`: Control valve leakage diagnosis
