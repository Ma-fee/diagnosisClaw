---
name: fa_skill_maintenance
description: Interactive execution monitoring and operational guidance.
allowed-tools:
  - update_todo_list
  - ask_followup_question
  - attempt_completion
  - search_engine
  - collect_metrics
  - deep_inspect
---

# Maintenance Operation Guidance

## Core Principle
Guide users through multiple rounds of dialogue to complete specific equipment inspection, testing, and maintenance operations, ensuring safety-first, data-driven, step-by-step operational guidance.

## Phase 1: Task Decomposition and Planning

### 1.1 Precise Intent Recognition

#### Core Requirement Extraction
- **Define specific operational goal**: What needs to be accomplished?
  - Examples: "Check if hydraulic pump is functioning properly"
  - Examples: "Replace the main bearing in swing motor"
  - Examples: "Perform 1000-hour maintenance inspection"

#### Complete Key Maintenance Information
Extract "maintenance object + fault phenomenon + implicit demands" from user input:

| Information Category | What to Extract | Example |
|-------------------|----------------|----------|
| Maintenance Object | Component or system being maintained | "hydraulic pump", "swing motor bearing" |
| Fault Phenomenon | Current state or symptoms | "abnormal vibration", "pressure drop" |
| Implicit Demands | Safety, efficiency, quality requirements | "ISO-compliant inspection", "minimize downtime" |

#### Resource Requirements Analysis
Match resources based on task complexity:

**Tools Required**:
- Measuring tools (multimeter, pressure gauge, vibration analyzer)
- Hand tools (wrenches, sockets, screwdrivers)
- Specialized tools (bearing pullers, torque wrenches)

**Technical Documents**:
- Equipment specifications and manuals
- Schematics (electrical, hydraulic, mechanical)
- SOPs and maintenance procedures

**Safety Equipment**:
- PPE requirements (gloves, glasses, respirators)
- Lockout/tagout procedures
- Environmental controls

### 1.2 Dynamic Autonomous Planning

#### Create Comprehensive Plan
Based on user requirements and current task context, break down into **3-5 clear, executable steps** covering the entire process: **"safety → measurement → judgment → adjustment"**

#### Checklist: Plan Completeness Verification
Each step MUST cover at least:

1. ✅ **Safety First**: Explicit safety precautions and preventive measures before operation
2. ✅ **Measurement Standards**: Specific measurement methods, tool requirements, standard value ranges
3. ✅ **Result Judgment**: Clear expected results and abnormal judgment criteria
4. ✅ **Dynamic Adjustment**: Real-time optimization based on feedback

#### Create Todo List with `update_todo_list`
```python
# Example todo list for bearing inspection:
{
    "todos": [
        {
            "id": "step_001",
            "content": "Preparation: Gather safety equipment and tools",
            "status": "pending",
            "safety": "Lockout/tagout power source, wear safety gloves and glasses",
            "tools": ["Safety glasses", "Insulated gloves", "Lockout/Tagout kit"]
        },
        {
            "id": "step_002",
            "content": "Check hydraulic system and isolate power",
            "status": "pending",
            "safety": "Verify zero energy state before proceeding",
            "measurement": "Confirm pressure = 0 MPa, voltage = 0 V"
        },
        {
            "id": "step_003",
            "content": "Inspect bearing condition and measure clearance",
            "status": "pending",
            "standard": "Clearance < 0.15 mm normal, >0.25 mm replace",
            "tools": ["Dial indicator", "Feeler gauge"]
        },
        {
            "id": "step_004",
            "content": "Test rotation and check for abnormal vibration",
            "status": "pending",
            "standard": "Vibration < 4.5 mm/s per ISO 10816",
            "tools": ["Vibration analyzer"]
        }
    ]
}
```

#### Dynamic Update Mechanism
As new information is collected or discovered:
- **Update todo list** to reflect current understanding
- **Add new tasks** as needed
- **Remove completed tasks** to avoid confusion
- **Reorder tasks** if priorities change

#### User Approval Process
Before executing plan:
1. **Present entire plan** to user
2. **Solicit feedback**: "Are you satisfied with this plan? Any adjustments needed?"
3. **Refine through discussion**: Brainstorm details and iterate on plan
4. **Secure confirmation** before execution

## Phase 2: Technical Data Retrieval Integration

### 2.1 Real-Time RAG Retrieval
According to specific operation tasks, **immediately retrieve** relevant technical materials:

#### Equipment Specification Parameters
- **Standard operating values**: Voltage, current, pressure, temperature ranges
- **Tolerance specifications**: Acceptable deviation limits
- **Performance ratings**: Maximum capacity, efficiency curves
- **Replacement intervals**: Recommended service hours or cycles

#### Diagram Interpretation
- **Electrical schematic diagrams**: Circuit paths, component connections, voltage drops
- **Hydraulic system diagrams**: Flow paths, pressure points, valve functions
- **Mechanical structure diagrams**: Assembly orders, component relationships, fits

#### Sensor Data Reading Methods
- **Measurement point locations**: Where to connect probes or sensors
- **Reading interpretation**: What the values indicate
- **Calibration procedures**: How to verify measurement accuracy
- **Data logging formats**: How to record measurements properly

#### Tool Usage Guidance
- **Measurement tool selection**: Right tool for the measurement
- **Operating procedures**: Correct use of measuring instruments
- **Accuracy requirements**: How precise measurements must be
- **Calibration checks**: Tool verification before use

#### Component Identification and Function
- **Component names and part numbers**: For ordering replacements
- **Component function**: What the component does in the system
- **Interconnections**: How it relates to other components
- **Criticality**: Failure modes and effects

### 2.2 Data Validity Verification
- **Match retrieved data to current device model**: Ensure compatibility
- **Check version or year**: Confirm specifications apply
- **Verify applicability**: Confirm data matches the task context
- **Cross-reference**: Validate with multiple sources if possible

### 2.3 Key Information Extraction
For each retrieved document, extract:
- **Values**: Numerical data, measurements, ratings
- **Tolerances**: Acceptable ranges and limits
- **Methods**: Procedures for operations or measurements
- **Warnings**: Safety alerts or critical notes
- **References**: Page numbers, section identifiers

### 2.4 Instant Search Response
**Upon user raising technical questions**:
- **Immediately initiate search** in relevant material
- **Retrieve focused results** on the specific question
- **Present summarized findings** with citations
- **Offer to elaborate** if more detail needed

### 2.5 Visualization Support
Generate visual aids as needed:
- **Schematics**: System diagrams or flowcharts
- **Diagrams**: Component layouts or assembly drawings
- **Operational flowcharts**: Step-by-step procedure visualization
- **Comparison tables**: Specification vs. actual measurements

## Phase 3: Interactive Execution Monitoring

### 3.1 Single-Step Confirmation Mechanism

#### Before Proceeding to Next Step
After each operation step is completed:
- **Call `ask_followup_question` to confirm result**
- **Provide specific status options** for user to report
- **Document measurements and observations**
- **Accept actual results even if unexpected**

**Example interaction at step completion**:
```
您已完成步骤2：检查液压油温。
您的测量结果是多少？

a) 正常 (50-70°C) - 继续步骤3
b) 高温 (70-85°C) - 检查冷却系统
c) 临界 (>85°C) - 立即停止并诊断高温原因
d) 在输入框输入具体测量值
```

### 3.2 Exception Handling Process

#### When User Reports an Exception
1. **Analyze possible causes** based on exception description
2. **Provide diagnostic options** to identify root cause
3. **Offer remediation steps** to address the exception
4. **Adjust the plan** if exception changes the task scope

**Example exception handling**:
```
❓ 用户报告：测量时压力表无法归零

可能原因：
1. 压力表故障 - 更换压力表
2. 系统有残留压力 - 需要泄压
3. 测量方法不当 - 重新培训操作

建议行动计划：
- 检查压力表是否损坏
- 确认系统已完全泄压
- 提供正确的测量步骤

您希望如何处理？
```

### 3.3 Progress Status Tracking

#### Record for Each Step
- **Execution status**: Completed, in-progress, pending
- **Measurement results**: Actual values with units
- **Observation details**: Visual, auditory, tactile observations
- **Time stamps**: When measurements were taken
- **Environmental conditions**: Temperature, load state, etc.

#### Update Todo List Dynamically
After each step:
- **Mark completed steps** as done
- **Update measurement data** in todo items
- **Adjust pending tasks** if plan changes
- **Skip unnecessary steps** if outcome determined early

## Phase 4: Image Analysis

### 4.1 Image Parsing Trigger Mechanism

**When users upload or provide device-related images**, automatically trigger multimodal image understanding:

#### Trigger Scenarios
- ✅ User uploads real photo of equipment components
- ✅ User shares fault phenomenon diagram
- ✅ User provides maintenance operation process image
- ✅ User asks about schematic, structure, or drawing
- ✅ User shares sensor data display interface or instrument reading

### 4.2 Core Capabilities via Multimodal Tools

#### Deep Image Understanding
- **Component recognition**: Identify parts, assemblies, and systems
- **Symbol interpretation**: Read schematic symbols and labels
- **Measurement reading**: Extract values from gauges and displays
- **Fault pattern recognition**: Identify signs of wear, damage, failure
- **Procedure step identification**: Match visual steps to SOPs

#### Image Content Type Recognition
1. **Real photos of equipment components**: Fault phenomena, wear indicators, damage
2. **Maintenance operation process diagrams**: Step-by-step procedures, tool usage
3. **Schematic/structure diagrams**: Electrical circuits, hydraulic systems, mechanical assemblies
4. **Sensor data display interfaces**: Gauges, HMI screens, instrument readings

### 4.3 Content Integration with Response Logic

**By integrating image understanding with maintenance scenario knowledge**:

1. **Analyze image content deeply**: Identify key elements, symbols, values
2. **Match to maintenance task**: Relate image elements to current procedure steps
3. **Extract actionable information**: Part numbers, measurements, conditions
4. **Provide contextual response**: Answer user's specific question based on image
5. **Generate follow-up guidance**: Suggest next steps or additional checks

## Phase 5: Comprehensive Analysis of Operation Results

### 5.1 Data Summary and Organization

#### Collect All Data
- **Measurement data**: All values collected during operation
- **Observation results**: Visual, auditory, tactile observations
- **Time stamps**: When each measurement was taken
- **Step completion status**: Which steps were completed and how

#### Data Organization
**Present in reference table format:**

```markdown
## 测量结果汇总表

| 检查项目 | 标准值 | 实际测量值 | 结果 | 备注 |
|---------|--------|----------|------|------|
| 液压油温 | 50-70°C | 68°C | ✅ 符合 | 机器达到工作温度 |
| 系统压力 | 20-25 MPa | 18.5 MPa | ⚠️ 偏低 | 检查泵和管路 |
| 振动水平 | <4.5 mm/s | 3.8 mm/s | ✅ 符合 | ISO 10816合规 |
| 轴承间隙 | <0.15 mm | 0.18 mm | ⚠️ 超标 | 需要更换轴承 |
```

### 5.2 Standard Value Comparison

#### Analyze Measured Results vs. Standards
For each measurement:
- **Identify normal range**: What is acceptable?
- **Compare actual value**: Is it within range?
- **Assess deviation**: How far outside normal? (minor, moderate, severe)
- **Determine implications**: What does the deviation mean for equipment health?

### 5.3 Comprehensive Status Judgment

#### Equipment Status Determination
Based on ALL data collected:

**Categories:**
1. **Equipment Normal** 🟢
   - All measurements within standard ranges
   - No abnormal observations
   - No concerns requiring immediate attention

2. **Equipment Caution Required** 🟡
   - Some measurements at warning thresholds
   - Minor observations requiring monitoring
   - No critical failures, but schedule planned maintenance

3. **Equipment Requires Immediate Action** 🔴
   - One or more measurements at critical/destructive levels
   - Obvious faults or damage observed
   - Immediate remediation required before continued operation

### 5.4 Abnormal Cause Analysis

#### When Abnormality is Detected
For each abnormal finding, analyze possible root causes:

**Analysis structure**:
```markdown
### 异常分析：轴承间隙超标

**测量数据**：
- 实际间隙：0.18 mm
- 标准限值：0.15 mm
- 超标幅度：+0.03 mm (+20%)

**可能原因评估**：

1. **正常磨损** (可能性：高)
   - 根因：长期使用导致轴承自然磨损
   - 确认方法：检查设备总工时 (已知：2,850小时)
   - 依据：Caterpillar设计寿命为2,000-2,500小时

2. **润滑不足** (可能性：中)
   - 根因：润滑油老化或补充不及时
   - 确认方法：检查油液分析和最后更换日期
   - 依据：ISO 4406标准要求定期更换

3. **过载操作** (可能性：低)
   - 根因：长期超负荷使用
   - 确认方法：询问操作员使用习惯
   - 依据：Caterpillar操作手册标明额定载荷

**推荐推荐**：
更换轴承作为预防性维护，同时建立油液分析计划。
```

## Phase 6: Task Confirmation

### 6.1 Result Summary Report

#### Generate Comprehensive Summary Including:

**All Operation Steps Executed**:
- Step descriptions in order of completion
- Time stamps for each step
- Methods or procedures used
- Tools required and used

**Key Measurement Data vs. Standard Values**:
- Reference table showing all measurements
- Standard values with citations
- Actual measured values
- Percent deviation from normal

**Final Judgment of Equipment Status**:
- Overall status determination (Normal/Caution/Critical)
- Detailed analysis per component or system
- Identified issues and abnormalities
- Severity assessment for each issue

**Problems Discovered and Suggestions**:
- List of detected problems
- Recommended actions for each problem
- Priority of remediation (immediate vs. scheduled)
- Monitoring requirements if condition is cautionary

### 6.2 User Confirmation Mechanism

#### Use `ask_followup_question` for Final Confirmation

**Confirmation options**:
```markdown
您对以上结果和评估有何确认？

a) ✅ 确认完成，结束任务
b) 📋 需要维修操作引导 (转设备专家)
c) 📷 需要上传更多现场照片分析
d) ❓ 有其他问题需要澄清
e) 在输入框输入您的反馈
```

## Phase 7: Task Delivery and Record

### 7.1 Complete Report Generation

**Call `attempt_completion`** to deliver full operation report with:

- **Complete operation steps executed** (chronological order)
- **Measurement data comparing to standard values** (tabular format)
- **Result judgment** (equipment status determination)
- **Problems discovered and suggestions** (prioritized action items)
- **Technical references and citations**
- **Visual elements** (diagrams, measurement charts if applicable)

### 7.2 Operation Record Preservation

For future reference and training:

**Save**:
- Complete operation process with timeline
- Measurement data and environmental conditions
- All observations and user feedback
- Equipment status determination and recommendations
- Any errors or exceptions encountered and resolutions

**Format** for archival:
- Structured report format (see Phase 6.1)
- Proper citations to technical documents
- Visual documentation (photos, diagrams)
- Follow-up tracking requirements
