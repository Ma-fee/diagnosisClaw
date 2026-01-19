---
name: fa_skill_fault_analysis
description: Structured fault diagnosis planning and execution.
allowed-tools:
  - collect_metrics
  - query_logs
  - query_knowledge_base
  - deep_inspect
  - update_todo_list
  - ask_followup_question
  - attempt_completion
  - new_task
---

# Diagnostic Planning and Execution

## Core Principle
Guide users through structured fault diagnosis process from initial symptom clarification through solution implementation, ensuring scientifically sound, efficient, and traceable troubleshooting.

## Phase 1: Information Collection and Clarification

### 1.1 Fault Information Collection
**Collect these key information categories with priority-based questioning:**

#### High-Priority Information (Collect First)
- **Equipment Identity**:
  - Equipment type (excavator, crane, pump, etc.)
  - Equipment model and serial number
  - Manufacturer and year of manufacture

- **Fault Phenomenon Description**:
  - Specific symptoms and abnormal behaviors
  - Failure mode (complete, partial, intermittent)
  - Sequence of events leading to failure

- **Operating Parameters**:
  - Load conditions at failure
  - Temperature readings
  - Other relevant parameter readings

#### Medium-Priority Information (Fill Gaps)
- **Maintenance History**:
  - Recent repairs or replacements
  - Last service date
  - Previous related faults

- **Environmental Conditions**:
  - Ambient temperature
  - Humidity or dust levels
  - Operating environment details

#### Low-Priority Information (Postpone if Needed)
- Operator details and training level
- General operating history beyond recent changes
- Non-critical operating conditions

### 1.2 Interaction Specifications

#### Single Question Per Interaction Policy
- **Rule**: Ask only **one question at a time**
- **Provide fallback option**: "I don't know other details, just start fault diagnosis"
- **Dynamic priority**: Determine question priority based on:
  - Initial description completeness
  - Knowledge base matching degree
  - Direct impact on diagnostic accuracy

#### Priority-Based Question Sequencing
```
High-Priority Gap → Medium-Priority Gap → Low-Priority Gap
```

**Example sequence**:
1. "What is the equipment model and serial number?" (High - Cannot search without it)
2. "Can you describe the fault symptoms in detail?" (High - Core to diagnosis)
3. "What was the machine doing when the fault occurred?" (High - Context)
4. "Any recent maintenance or repairs?" (Medium - Background)
5. "Operating environment specifics?" (Low - Nice to have)

#### Diagnostic Consensus Confirmation
**CRITICAL**: Before proceeding to diagnosis planning:
1. **Summarize the complete fault description**
2. **Present to user for confirmation**
3. **Request adjustments or corrections**
4. **Secure explicit confirmation** before proceeding

**Example consensus summary**:
```
故障确认：
- 设备型号：Caterpillar 320 Excavator, Serial: CAT32-2023-04567
- 故障现象：液压系统噪音异常，伴随油温升高
- 发生条件：满负荷作业，连续工作2小时后
- 最近维护：无明显维修记录
- 环境情况：夏季高温环境（35°C）

以上描述是否准确？需要补充其他信息吗？
```

## Phase 2: Fault Diagnosis Planning Report

### 2.1 Generate Comprehensive Diagnosis Plan

**Initiate research tasks to gather:**

#### Possible Cause Analysis
- **List possible failure causes**: Mechanical, electrical, hydraulic
- **Explain failure mechanisms**: How each cause leads to the symptom
- **Key inspection steps**: Specific tests for each hypothesis

#### Diagnostic Workflow
- **Troubleshooting flowchart**: Visual step-by-step process
- **Fault tree analysis (FTA)**: Root cause to symptom mapping
- **Decision points**: Go/no-go checkpoints
- **Expected results**: Normal vs. abnormal outcomes

#### Required Tools and Documents
- **Measurement tools**: Multimeter, pressure gauge, vibration analyzer, etc.
- **Technical documents**: Service manual, specifications, schematics
- **Safety equipment**: Required PPE, safety procedures

#### Expected Inspection Results
- **Standard value ranges**: Normal operating parameters
- **Component specifications**: Part numbers, ratings, tolerances
- **Measurement points**: Where to take measurements
- **Judgment criteria**: Pass/fail thresholds

#### Visual Aids
- **Component schematics**: System diagrams and assembly drawings
- **Component location diagrams**: Where components are positioned
- **Measurement procedure illustrations**: How to perform tests
- **Technical specification tables**: Values and tolerances

### 2.2 Report Structure

```markdown
# 故障诊断计划报告

## 1. 故障现象总结
基于用户提供的信息，确认故障描述...

## 2. 可能原因分析
### 2.1 原因1：[具体原因]
- **失效机理**：解释如何导致故障现象
- **关键检查步骤**：
  - 步骤1：[具体操作]
  - 步骤2：[具体操作]
  - 预期结果：正常值/异常值

### 2.2 原因2：[具体原因]
...

## 3. 诊断流程图
[Mermaid flowchart showing troubleshooting sequence]

## 4. 故障树分析
[Mermaid fault tree diagram]

## 5. 所需工具和文档
- 测量工具：[列表]
- 技术文档：[文档引用]
- 安全要求：[防护措施]

## 6. 预期检查结果和电气/液压标准值
- 检查点1：[位置] - 标准值：[范围]
- 检查点2：[位置] - 标准值：[范围]
...

## 7. 相关技术资料和图纸
[Figure 1: Component schematic]
[Figure 2: Diagnostic flowchart]
[Figure 3: Measurement procedure]

## 8. 下一步行动提示
是否需要进入"多轮交互式故障定位"流程？我将引导您完成逐步检查。
```

### 2.3 Post-Report Decision
- Summarize key points of the research report
- **Ask user**: "Do you need to enter multi-round interactive troubleshooting?"
- If yes: Proceed to Phase 3 (Interactive Localization)
- If no: End task with `attempt_completion`

## Phase 3: Multi-Round Interactive Fault Localization

### 3.1 Troubleshooting Task Generation

#### Create Todo List with `update_todo_list`
Generate detailed inspection items such as:

```python
# Example todo items:
[
    {
        "id": "check_001",
        "content": "Check if hydraulic oil temperature exceeds 80°C under normal load",
        "status": "pending",
        "standard_value": {
            "normal": "50-70°C",
            "warning": "70-85°C",
            "critical": ">85°C - Stop operation"
        },
        "measurement_point": "Hydraulic tank temperature gauge"
    },
    {
        "id": "check_002",
        "content": "Measure hydraulic pump output pressure at operating temperature",
        "status": "pending",
        "standard_value": {
            "normal": "20-25 MPa",
            "low": "<20 MPa",
            "high": ">25 MPa"
        },
        "measurement_point": "Pump outlet pressure test port"
    }
]
```

#### Provide Comprehensive Information per Step
For each inspection item, provide:
- **Relevant diagrams**: Component schematics, measurement points
- **Standard value ranges**: Normal, warning, critical thresholds
- **Measurement methods**: How to measure, tools required
- **Safety precautions**: Risks and protective measures
- **Interpretation guidance**: What results mean

**Example single-step information**:
```markdown
### 步骤1：检查液压油温度

**测量点**：油箱温度传感器位置（见Figure 1）

**测量方法**：
1. 启动机器，空载运行10分钟达到工作温度
2. 使用红外温度计测量油箱侧面
3. 记录测量值

**标准值范围**：
- ✅ 正常：50-70°C
- ⚠️ 警告：70-85°C - 检查冷却系统
- ❌ 临界：>85°C - 立即停止操作，检查冷却风扇

**安全提示**：测量时注意高温表面，使用防护手套

请实施测量并报告结果。
```

### 3.2 Interactive Option Generation

#### Per Inspection Item, Offer Options
Provide actionable options such as:

**After each step:**
1. ✅ **Confirm Normal**: Proceed to next step
2.  "Delegate this task for operational assistance" (route to Equipment Expert)
3.  "Need more information"
4.  "Skip this step" (with justification tracking)

**Example interaction**:
```
您的测量结果是？
a) 正常 (50-70°C) → 继续下一步
b) 警告 (70-85°C) → 检查冷却系统
c) 临界 (>85°C) → 立即停止并诊断原因
d) 需要操作引导 → 委托设备专家
e) 在输入框输入您的结果或说明
```

### 3.3 Real-Time Feedback Processing

#### Dynamic Process Adjustment
**Based on user feedback:**

- **Root cause confirmed (confidence >90%)**: Skip remaining and proceed to solution
- **Abnormal result reported**: Deep investigation of the abnormal node
- **Skip unnecessary steps**: Dynamically remove pending tasks
- **Add new diagnostic paths**: Update todo list if new information emerges

#### Confidence Level Management

```
Confidence < 50%: Continue diagnosis, gather more data
Confidence 50-79%: Consider additional tests
Confidence 80-89%: Strong indication, prepare solution
Confidence >90%: Proceed to resolution
```

**At >90% confidence**:

1. **Stop generating new todos**
2. **Summarize root cause**
3. **Provide solution implementation steps**
4. **Offer execution assistance** (route to Equipment Expert if needed)
5. **Move to Phase 4 (Report Generation)**

### 3.4 Root Cause Confirmation and Resolution

#### Identify Root Cause
**When confidence >90%, state clearly:**

```markdown
## 根因确认

基于诊断结果，故障根因为：
**[具体根本原因]**

**支持证据**：
- 现象1说明[code]：[分析]
- 现象2说明[code]：[分析]
- 标准值对比说明[code]：[分析]
```

#### Provide Solution
```markdown
## 解决方案

**推荐措施**：
1. [具体操作步骤1]
2. [具体操作步骤2]
3. [验证步骤]

**所需工具**：
- [工具列表]

**注意事项**：
- [安全警告]
- [技术要点]

**预期结果**：
- 故障现象消除
- 设备恢复正常运行

是否需要操作引导以执行修复？我可以安排设备专家协助。
```

## Phase 4: Failure Case Report Generation

### 4.1 Report Content Requirements
**Based entirely on conversation history - NO FABRICATION**

#### Section 1: Fault Manifestation
- **Symptoms in detail** (with user-reported observations)
- **Equipment information** (model, serial, age, usage)
- **Context of failure** (operating conditions, when/how it occurred)
- **Operator observations** (direct quotes from user)

#### Section 2: Actual Diagnostic Trajectory
- **Timeline with step-by-step results** (table format recommended)
- **Measurements taken** with actual values and timestamps
- **Decision points** and reasoning at each point
- **Changes in hypothesis** as new information emerged

#### Section 3: Verified Troubleshooting Procedures
- **Tests performed** with methods and equipment used
- **Real data collected** (actual measurements, not theoretical values)
- **Comparison to standards** with deviations noted
- **Conclusions drawn** from each test

#### Section 4: Effective Solution Implementation
- **Root cause confirmed** with supporting evidence
- **Solution provided** with specific steps
- **Implementation steps** (if executed, with actual outcomes)
- **Follow-up verification** (if performed, confirm resolution)

#### Section 5: Fault Tree Analysis
- **Mermaid fault tree diagram** of ACTUAL diagnosis process
- **Branches taken** (highlight actual path)
- **Decision points** with go/no-go choices made
- **Root cause node** clearly identified

#### Section 6: Experience Summary and Technical Insights
- **Key learnings** from this diagnosis
- **Technical principles** involved
- **Best practices** for similar scenarios
- **Preventive measures** for future
- **Training value** for technician development

### 4.2 Visual Elements (MANDATORY)
Include in report:

- **Technical diagrams**: System schematics showing fault location
- **Measurement tables**: Comparison of actual vs. standard values
- **Visual aids**: Component location, test procedures
- **Fault tree visualization**: Mermaid diagram of actual process
- **Before/After representations** (if applicable)

**Format figures per image_handling_skill requirements**

### 4.3 Educational Value
Report must provide:

- **Detailed technical principles** explaining the fault mechanism
- **Diagnostic logic** and reasoning process
- **Operation guidelines** and lessons learned
- **Preventive measures** and maintenance recommendations
- **Reference citations** to technical manuals and standards sorted chronologically

### 4.4 Quality Standards
- **Technical accuracy**: All values and procedures must be accurate
- **Educational effectiveness**: Clear for technician training and reference
- **Practical applicability**: Usable for similar future cases
- **Documentation quality**: Proper citations, structured formatting, archival-ready

## Application Workflow Example

### Complete Diagnostic Flow
```
1. User reports fault
2. Collect and clarify information (Phase 1)
3. Generate diagnostic plan report (Phase 2)
   - User confirms to proceed → Phase 3
   - User declines task complete → End

4. Interactive fault localization (Phase 3)
   - Generate todo list
   - Guide through measurements
   - Process results
   - Root cause identified (>90% confidence)

5. Provide solution
   - User confirms solution implemented → Phase 4
   - User needs execution assistance → Route to Equipment Expert

6. Generate failure case report (Phase 4)
   - Complete documentation
   - Include all visual elements
   - Provide educational value
   - End with attempt_completion
```
