---
name: systematic-troubleshooting
description: Execute systematic interactive troubleshooting for complex system faults through structured user collaboration. Guides diagnostic workflows across five phases with mandatory user confirmation at each transition. Requires interactive user communication for information collection, test execution, and decision-making. Use when a user reports a fault that requires hands-on diagnostic involvement, guided inspection procedures, and collaborative root cause confirmation.
---

# Systematic Troubleshooting Skill

## Overview

Guides systematic fault diagnosis through collaborative user interaction. This skill provides the diagnostic logic and structure while relying on direct user engagement for information gathering, test execution, and decision confirmation.

## Critical Operating Requirements

### User Interaction Requirement

**This skill REQUIRES interactive user communication**. All phases involving user input must be conducted through direct conversation, not background delegation or automated data collection.

| Phase Activity | How to Execute |
|---------------|----------------|
| Information Collection | Interactive questioning with user |
| Test Guidance | Step-by-step user instructions |
| Result Collection | Direct user response |
| Phase Confirmation | Explicit user approval |

### Phase Transition Protocol

**MANDATORY USER CONFIRMATION** required before advancing to any new phase:

```
Phase N Complete
    ↓
Summarize outcomes to user
    ↓
Explain next phase activities
    ↓
Ask explicit confirmation
    ↓
[User approves] → Load appropriate resources, proceed to Phase N+1
[User declines] → Stay in current phase or conclude
```

## Diagnostic Workflow

```
Phase 1: Information Collection
    ↓ (interactive with user)
    [User confirms completion]
    ↓
Phase 2: Diagnostic Planning  
    ↓ (background research)
    [User confirms planning results]
    ↓
Phase 3: Interactive Execution
    ↓ (interactive with user)
    [User confirms root cause findings]
    ↓
Phase 4: Root Cause Confirmation
    ↓ (interactive with user)
    [User confirms documentation]
    ↓
Phase 5: Case Documentation
    ↓ (background generation)
    Complete
```

## Phase 1: Information Collection

**Purpose**: Gather comprehensive fault context through user interaction

**Execution Mode**: **INTERACTIVE** - Direct user communication only

### Information Requirements

Collect the following through structured user interaction:

| Category | Information to Collect |
|----------|----------------------|
| **System Identification** | Equipment type, manufacturer, model, specifications |
| **Fault Description** | Symptoms, severity, patterns, onset timing |
| **Operating Conditions** | Ambient environment, workload, parameters |
| **Historical Context** | Maintenance history, recent changes, past issues |

### Collection Approach

1. **Start with available information** from user's initial report
2. **Identify gaps** in required information
3. **Request specific details interactively** from user
4. **Validate completeness** before concluding phase

### Phase Completion Criteria

- [ ] Equipment model identified
- [ ] Primary symptom clearly described
- [ ] Operating conditions documented
- [ ] User confirms information is complete

### Phase Transition

**Before advancing to Phase 2, present summary to user:**

```
"我现在已收集到以下信息：

📋 **设备信息**
- 型号：[manufacturer] [model]

📋 **故障描述**  
- 症状：[description]
- 发生条件：[conditions]

📋 **下一步**
我将基于这些信息检索技术资料并制定诊断计划，包括可能的故障原因和检查步骤。

是否进入诊断规划阶段？"
```

## Phase 2: Diagnostic Planning

**Purpose**: Generate comprehensive diagnostic plan based on collected information

**Execution Mode**: **BACKGROUND** - Multi-dimensional research requiring delegation

### Planning Activities

**REQUIRED**: Delegate the entire planning task. Diagnostic planning requires:
- Multi-dimensional research (equipment specs, failure modes, procedures, cases, standards)
- Structured synthesis of diverse information
- Cross-reference intensive validation across sources

**MANDATORY**: Use delegation (e.g., `new_task`) for comprehensive diagnostic planning. This is NOT a direct query task.

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

Research scope: Technical manuals, failure databases, case studies, industry standards
```

### Planning Outputs (from delegated task)

Produce a diagnostic plan containing:

1. **Possible Causes**
   - List with probability rankings
   - Failure mechanisms for each
   - Key indicators to check

2. **Inspection Procedures**
   - Step-by-step sequence
   - Standard values and tolerances
   - Required tools

3. **Decision Logic**
   - Flowchart for branching decisions
   - Criteria for eliminating hypotheses

### Phase Completion Present to User

```
"诊断计划已制定完成：

📋 **可能原因**（按概率排序）
1. [Cause A] - [概率] - [关键检查点]
2. [Cause B] - [概率] - [关键检查点]
...

📋 **检查计划**
共 [N] 个检查步骤，预计需要 [时间估算]

是否开始进行交互式故障排查？在每个步骤中，我会指导您执行检查并解释结果。"
```

## Phase 3: Interactive Diagnostic Execution

**Purpose**: Execute the diagnostic plan through guided user interaction

**Execution Mode**: **INTERACTIVE** - Extensive user communication required

### Phase 3 Skill Loading (MANDATORY ENTRY ACTION)

**REQUIRED**: Load device-specific diagnostic skill at Phase 3 entry.

**Why**: Interactive execution requires device-specific diagnostic procedures, component information, and troubleshooting patterns. The diagnosis-planning report provides the structure, but device-specific skills provide the detailed guidance.

**Loading Logic**:
```
ON Phase 3 entry:
    IF device_type in [挖掘机, Excavator, 挖机]:
        LOAD skill: excavator-diagnostic-guide
    ELSE IF device_type in [装载机, Loader]:
        LOAD skill: loader-diagnostic-guide  
    ELSE IF device_type in [液压泵, Hydraulic Pump]:
        LOAD skill: hydraulic-diagnostic-guide
    ELSE IF device_type in [发动机, Engine, 电机]:
        LOAD skill: engine-diagnostic-guide
    ELSE:
        USE: diagnosis-planning report only
        NOTE: "No device-specific skill available, using planning report"
```

**Usage Pattern**:
- Diagnosis-planning report: Overall structure, hypothesis ranking, standard values
- Device-specific skill: Step-by-step procedures, component locations, practical guidance

### Setup

**Step 1**: Load device-specific skill (see above)

**Step 2**: Create diagnostic todo list based on planning report + skill guidance:
```
[ ] Step 1: [Inspection item from planning report]
       正常值: [Standard value from planning report]
       工具: [Tools from planning report]
       操作指导: [Specific guidance from loaded skill]
[ ] Step 2: ...
```

### Progress Tracking Protocol

**MANDATORY**: Maintain explicit progress state throughout Phase 3 execution.

**Initialization** (After todo list creation):
```
INITIALIZE_PROGRESS_TRACKING(
    total_steps: count(inspection_procedures),
    current_step: 0,
    status: "in_progress",
    completed_findings: [],
    hypotheses_confidence: initial_ranking_from_plan
)
```

**Update Triggers** (Pseudocode):
```
ON user_completes_inspection:
    UPDATE_PROGRESS(
        mark_completed: current_step,
        record_result: user_observation,
        update_confidence: hypothesis_impact,
        suggest_next: calculated_priority_step
    )
    PRESENT_PROGRESS_SUMMARY()

ON hypothesis_confidence_changes:
    UPDATE_PROGRESS(
        adjust_priority: hypothesis_ranking,
        skip_if_irrelevant: low_probability_steps,
        add_emergency: new_critical_checks
    )

ON user_requests_status:
    PRESENT_PROGRESS_SUMMARY()
    SHOW: completed_steps / total_steps
    SHOW: current_hypothesis_ranking
    SHOW: next_steps_preview
```

**Progress State to Track**:
- Completed steps with results and timestamps
- Current active step with user pending status
- Skipped/deferred items with reasons
- Hypothesis confidence evolution
- Evidence collected per hypothesis
- Any deviations from original plan

**Progress Presentation Format**:
```
诊断进度 (3/7 步骤完成)
========================
[✓] Step 1: 检查冷却液液位 - 结果：低于标准
[✓] Step 2: 检查散热器软管 - 结果：发现裂纹
[→] Step 3: 检查节温器工作状态 - 进行中...
[ ] Steps 4-7: 待执行

当前假设置信度:
• 冷却液泄漏 ............... 85% ↑ (Step 2 新证据支持)
• 节温器故障 ............... 30%
• 水泵故障 ................. 15%

预计剩余时间: 15-20 分钟
```

**Completion Check** (Before Phase 4):
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

### Execution Loop (Per Step)

1. **Present Purpose**
   - Explain why this check is being performed
   - Reference which hypothesis this tests
   - Show how this connects to overall plan

2. **Guide Action**
   - Provide clear, step-by-step procedures
   - State safety precautions
   - Give expected normal values/ranges

3. **Collect Result**
   - Request user's observation or measurement
   - Provide clear response options

4. **Interpret Together**
   - Compare result to standard values
   - Explain what the result means
   - Update hypothesis confidence
   - Decide next step with user awareness

### Dynamic Adjustment

Adjust plan in real-time based on findings:

| Finding | Adjustment |
|---------|-----------|
| Root cause confirmed (>90%) | Skip remaining routine checks |
| Unexpected abnormal result | Branch to associated investigation |
| Result contradicts hypothesis | Eliminate, re-prioritize remaining |
| User cannot perform step | Offer alternative or mark limitation |

### Phase Completion Criteria

- [ ] All relevant hypotheses tested
- [ ] Root cause identified with >90% confidence
- [ ] User agrees with findings
- [ ] Ready for formal confirmation

## Phase 4: Root Cause Confirmation

**Purpose**: Formally verify and document root cause with user

**Execution Mode**: **INTERACTIVE** - Requires user confirmation

### Verification Checklist

Present to user:

```
"基于我们的排查，现在进行根因确认：

✅ **症状解释**
所有观察到的症状都可以由此原因解释：
- [Symptom 1] → [Explanation]
- [Symptom 2] → [Explanation]

✅ **替代原因排除**
其他可能原因已通过检查排除：
- [Cause B]: 排除原因 [evidence]
- [Cause C]: 排除原因 [evidence]

✅ **置信度评估**
当前置信度: [90%+]

✅ **建议措施**
[Recommended corrective action]

您确认这是正确的故障原因吗？还有其他疑虑吗？"
```

### Confidence Levels

| Level | Criteria | User Action |
|-------|----------|-------------|
| >95% | Direct evidence, all alternatives excluded | Confident proceed |
| 90-95% | Strong evidence, minor uncertainty | Proceed with note |
| <90% | Insufficient evidence | Recommend additional testing |

### Phase Completion

Only proceed to documentation when:
- User explicitly confirms root cause
- User has no outstanding questions
- User agrees to document the case

## Phase 5: Case Documentation

**Purpose**: Generate comprehensive case report

**Execution Mode**: **CURRENT AGENT - DIALOGUE CONTEXT REQUIRED** - MUST NOT DELEGATE

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

After generating the complete report:

```
"案例文档已生成：

📄 **文档内容**
[呈现完整的案例报告]

文档可以用于：
- 维护记录存档
- 培训案例
- 知识库积累

是否还需要补充任何信息或进行修改？"
```

### Anti-Pattern: Do NOT Do This

❌ **Wrong**: Delegate to subagent or background task for report generation  
❌ **Wrong**: Summarize diagnostic history and pass to another agent  
❌ **Wrong**: `new_task` or subagent delegation for case documentation

✅ **Correct**: Load `case-document` skill as reference, generate report in current agent context  
✅ **Correct**: Use complete dialogue history to fill templates  
✅ **Correct**: Present directly to user from current agent

## Key Principles

### Interactive-First Design

- All user-facing activities are interactive
- Background work is limited to data retrieval and document generation
- User is never bypassed in decision-making

### Phase Gates

- No automatic phase advancement
- Each phase requires explicit user confirmation
- User can pause, modify, or exit at any phase boundary

### Evidence-Driven

- All conclusions supported by test results
- Confidence levels tracked and communicated
- Uncertainties acknowledged transparently

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

## Integration with Other Skills

### When to Load Other Skills

| Trigger | Skill to Load |
|---------|--------------|
| Need comprehensive planning with diagrams | diagnosis-planning |
| Information gathering framework needed | information-gathering |
| Formal report generation required | case-document |

### Coordination Protocol

1. Explain to user what external skill will provide
2. Load skill and execute (background for planning, interactive for guidance)
3. Integrate results into current phase
4. Continue with user confirmation

## Error Handling

| Scenario | Response |
|----------|----------|
| User cannot perform recommended test | Offer alternative test or document limitation |
| Result contradicts all hypotheses | Document anomaly, expand hypothesis list |
| User questions diagnosis logic | Explain reasoning, consider additional verification |
| Confidence not improving | Recommend expert consultation |

## Example Workflow

See `references/domain_examples.md` for a complete excavator diagnostic example demonstrating the interactive workflow with phase confirmations.
