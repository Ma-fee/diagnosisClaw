# Diagnostic Information Retrieval Strategy

This document provides detailed guidance for conducting effective information retrieval during diagnostic planning.

## Table of Contents

1. [Search Query Construction](#search-query-construction)
2. [Information Categories](#information-categories)
3. [Source Prioritization](#source-prioritization)
4. [Result Integration](#result-integration)

---

## Search Query Construction

### Equipment-Specific Queries

#### For Standard Values
```
{Equipment Model} + "technical manual" + {parameter}
{Equipment Type} + "operating specifications" + {parameter}
{Manufacturer} + {Model} + "maintenance manual" + tolerances
```

**Examples**:
- "CP-2000 pump technical manual bearing temperature"
- "Sany SY215C excavator hydraulic pressure specifications"
- "ABB motor M2BAX operating temperature range"

#### For Fault Analysis
```
{Equipment Type} + {Fault Symptom} + "causes" + "troubleshooting"
{Model} + {Fault Pattern} + "common failure" + "case study"
{Manufacturer} + {Fault Code} + diagnostic procedure
```

**Examples**:
- "centrifugal pump overheating causes troubleshooting"
- "excavator black smoke engine fault case study"
- "ABB ACS880 fault code 2330 diagnostic procedure"

#### For Inspection Procedures
```
{Equipment Type} + "inspection" + "procedure" + {inspection item}
{Component} + "measurement method" + standard
{Equipment Type} + "preventive maintenance" + checklist
```

**Examples**:
- "pump bearing inspection procedure vibration analysis"
- "motor alignment measurement method dial indicator"
- "hydraulic system preventive maintenance checklist"

### Multi-Aspect Research Template

For comprehensive diagnostic research, delegate multiple parallel searches:

```
Delegate Research Tasks to Material Assistant:

Task 1: Equipment Specifications
Query: {Equipment Model} specifications operating parameters
Expected: Temperature ranges, pressure limits, tolerances

Task 2: Failure Mode Analysis
Query: {Equipment Type} {Fault Symptom} failure modes root causes
Expected: Common causes, failure mechanisms, frequency data

Task 3: Troubleshooting Procedures
Query: {Manufacturer} {Model} troubleshooting guide {fault type}
Expected: Step-by-step procedures, decision trees

Task 4: Historical Cases
Query: {Equipment Model} {Fault} case study resolution
Expected: Similar incidents, diagnosis steps, solutions
```

---

## Information Categories

### Category 1: Standard Operating Parameters

**What to Retrieve**:
- Normal operating ranges for temperature, pressure, speed
- Warning and critical thresholds
- Manufacturer specification limits
- Industry standard tolerances

**Application in Diagnosis**:
- Validate if current readings are abnormal
- Set thresholds for inspection steps
- Determine severity levels
- Establish go/no-go criteria

### Category 2: Failure Mode and Effects

**What to Retrieve**:
- List of possible failure modes for observed symptoms
- Failure mechanism descriptions
- Probability/frequency data from historical cases
- Symptom-cause correlations

**Application in Diagnosis**:
- Generate prioritized hypothesis list
- Understand underlying mechanisms
- Estimate likelihood of each cause
- Guide inspection priority

### Category 3: Inspection Procedures

**What to Retrieve**:
- Manufacturer-recommended inspection sequences
- Standard measurement techniques
- Required tools and equipment
- Safety precautions and lockout procedures

**Application in Diagnosis**:
- Design effective inspection steps
- Ensure safety compliance
- Specify proper tools
- Follow best practice sequences

### Category 4: Troubleshooting Guides

**What to Retrieve**:
- Decision trees and flowcharts
- Elimination criteria for causes
- Test procedures and expected results
- Escalation procedures

**Application in Diagnosis**:
- Build diagnostic flowcharts
- Design logical inspection sequences
- Define decision points
- Optimize troubleshooting efficiency

### Category 5: Parts and Tool Information

**What to Retrieve**:
- Component specifications and part numbers
- Special tool requirements
- Consumables needed (gaskets, seals, etc.)
- Availability and lead times

**Application in Diagnosis**:
- Plan resource requirements
- Estimate repair time
- Prepare parts in advance
- Schedule maintenance windows

---

## Source Prioritization

### Primary Sources (Highest Confidence)

1. **Manufacturer Technical Manuals**
   - Equipment operation manuals
   - Service manuals
   - Maintenance bulletins
   - Technical specifications sheets

2. **Original Equipment Manufacturer (OEM) Documentation**
   - Component datasheets
   - Engineering specifications
   - Factory test reports

### Secondary Sources (High Confidence)

1. **Authorized Service Documentation**
   - Dealer service guides
   - Certified technician resources
   - Warranty service procedures

2. **Industry Standards**
   - ISO standards for equipment class
   - National standards (GB, DIN, etc.)
   - Industry association guidelines

### Tertiary Sources (Reference Only)

1. **Technical Textbooks**
   - Engineering references
   - Maintenance handbooks
   - Diagnostic methodology guides

2. **Historical Case Databases**
   - CMMS maintenance records
   - Field service reports
   - Knowledge base articles

### Source Verification Rules

- Always cross-reference critical values with primary sources
- Use secondary sources to supplement primary information
- Note discrepancies between sources and prioritize primary
- Document source limitations (e.g., "Based on similar model data")

---

## Result Integration

### Synthesis Framework

When integrating retrieved information into the diagnostic plan:

#### Step 1: Validate Against Context
- Does the information apply to this specific equipment model?
- Are there version/configuration differences to consider?
- Is the operating environment consistent with retrieved data?

#### Step 2: Resolve Conflicts
- When sources disagree, prioritize primary over secondary
- Note conflicting information and reasoning for choice
- Document assumptions when definitive data is unavailable

#### Step 3: Update Probability Estimates
- Weight possible causes based on:
  - Historical frequency from case studies
  - Symptom match specificity
  - Equipment age and maintenance history
  - Operating condition relevance

#### Step 4: Structure Evidence
For each element in the diagnostic plan, include:
- **Claim**: The technical statement/assertion
- **Evidence**: Retrieved data supporting the claim
- **Source**: Citation to enable verification
- **Confidence**: High/Medium/Low based on source quality

### Documentation Template

```markdown
### Evidence-Based Finding

**Finding**: [Claim about failure cause, standard value, etc.]

**Supporting Evidence**:
- [Source 1]: [Specific information retrieved]
- [Source 2]: [Corroborating information]

**Application to Current Case**:
[Explanation of how this applies to the specific equipment/fault]

**Confidence Level**: High/Medium/Low
[Rationale for confidence assessment]
```

---

## Retrieval Workflow Integration

### When Researching for Diagnostic Planning

```
1. Analyze User Input
   ↓
2. Identify Information Gaps
   ↓
3. Construct Search Queries
   ↓
4. Delegate to Material Assistant (parallel searches)
   ↓
5. Receive & Evaluate Results
   ↓
6. Synthesize with Expert Knowledge
   ↓
7. Generate Evidence-Based Plan
   ↓
8. Cite Sources in Output
```

### Parallel Research Strategy

For efficient diagnostic planning, conduct parallel searches for:
- Equipment specifications
- Failure mode database
- Troubleshooting procedures
- Historical case studies

Delegate each as separate `new_task` calls to `material_assistant` for concurrent execution.

### Handling Research Gaps

When expected information is not found:

1. **Document the Gap**: Note what information was sought but not found
2. **Use Inference**: Based on similar equipment or industry standards
3. **Flag for User**: Highlight assumptions that need user verification
4. **Suggest Alternatives**: Propose alternative diagnostic approaches

---

## Quality Assurance Checklist

Before finalizing the diagnostic plan:

- [ ] All critical standard values have source citations
- [ ] Failure causes are prioritized based on evidence
- [ ] Inspection steps follow manufacturer guidelines where available
- [ ] Required tools are specified with model/type references
- [ ] Safety procedures align with industry standards
- [ ] Conflicting information has been resolved with rationale
- [ ] Gaps in available information are documented
- [ ] Confidence levels are assigned to key findings
