# RFC 002: Xeno-Agent 1:1 RFC 1:1 复现任务清单

**Status**: 🚧 In Progress
**Created**: 2025-01-18
**Owner**: Sisyphus
**Related RFCs**: 001, 003

---

## 概述

本 RFC 定义了将 Xeno-Agent 当前实现改造为与 RFC 001/003 完全一致的详细任务清单。

**目标**: 实现能够完整演示 4 角色协作（QA 网关→故障专家→设备专家/资料助手）的故障诊断系统。

---

## 背景与问题

### 当前状态

✅ **已实现**:
- 核心架构：`XenoSimulationFlow`、`SimulationState`、`TaskFrame` 栈模型
- 注册中心：`AgentRegistry`、`SkillRegistry`
- 元工具：`SwitchModeTool`、`NewTaskTool`、`AttemptCompletionTool`、`AskFollowupTool`
- HITL 机制：`InteractionHandler` + `@requires_approval`
- 配置加载：`ConfigLoader` 支持 flow/role/tool 配置

❌ **关键缺失**:
- 4 个 RFC 角色定义（QA Assistant、Fault Expert、Equipment Expert、Material Assistant）
- `XenoAgentBuilder.from_yaml()` 未实现
- 子任务回传机制断路
- "正常完成"路由未定义
- 共享能力协议（Markdown、Citation、Image、Search）未实现

### 影响范围

- 无法演示 RFC 001 定义的协作场景
- CLI 样例使用错误的角色集（通用诊断 vs 4 角色模型）
- 配置加载流程与 RFC 期望不符

---

## 详细任务清单

### Phase 1: 角色定义与配置 (P0 - 阻塞核心场景)

#### Task 1.1: 创建 QA Assistant 角色定义

**File**: `packages/xeno-agent/config/roles/qa_assistant.yaml`

**职责**:
- 意图识别与网关分发
- 根据用户问题简单性决定：
  - 简单问题 → Material Assistant 直接回答
  - 复杂故障 → Switch Mode → Fault Expert

**PROMPT 模板**:
```yaml
name: Q&A Assistant
role: 意图识别与网关分发
goal: 快速识别用户问题类型并路由到合适的专家
backstory: 你是机械故障诊断系统的前台，负责区分简单问答和复杂故障诊断。

thought_process: |
  1. 分析用户输入：
     - 是否包含具体设备/场景？
     - 是否涉及故障现象？
     - 是否需要检索手册/资料？
     - 是否需要图解分析？

  2. 路由决策：
     - 简单问题（仅信息查询）→ new_task(material_assistant, ...)
     - 复杂故障 → switch_mode("fault_expert", ...)

tools:
  - xeno_meta_switch_mode  # 切换到故障专家
  - xeno_meta_new_task       # 委派给资料助手

constraints:
  - 任何复杂诊断场景必须切换到 fault_expert
  - 仅在纯信息查询时使用 new_task 委派

example: |
  用户输入: "机械臂复位失败"
  分析: 包含故障现象、需要诊断 → 切换到 fault_expert

  用户输入: "如何更换伺服电机？"
  分析: 信息查询、需要手册 → new_task(material_assistant)
```

**验证标准**:
- YAML 可通过 `load_agent_from_yaml` 加载
- 可以正确区分简单/复杂问题

---

#### Task 1.2: 创建 Fault Expert 角色定义

**File**: `packages/xeno-agent/config/roles/fault_expert.yaml`

**职责**:
- 故障诊断编排与协调（Orchestrator + Diagnostician）
- 诊断规划
- 识别需要子任务的环节并委派
- 诊断完成后形成报告

**PROMPT 模板**:
```yaml
name: Fault Expert
role: 故障诊断编排与协调专家
goal: 系统化分析复杂故障，规划诊断步骤，协调子任务执行
backstory: 你是资深的机械故障诊断专家，擅长系统化思维和协作调度。

thought_process: |
  1. 接收用户故障描述，初步分析：
     - 故障设备类型
     - 故障现象与症状
     - 可能的影响范围

  2. 制定诊断计划：
     - 识别信息缺口（需要查找手册/型号/规格）
     - 识别技术难点（需要图解分析/专业原理）
     - 识别诊断路径（可能性穷举、排除法深入）

  3. 子任务委派策略：
     - 需要查找资料 → new_task(material_assistant, "检索 X expected_output: ...")
     - 需要分析图解 → new_task(equipment_expert, "分析图纸 expected_output: 诊断结论")
     - 需要物理操作指导 → switch_mode("equipment_expert", "完全接管交互")

  4. 综合与决策：
     - 收集所有子任务的 result
     - 形成诊断结论或进一步行动
     - 完成诊断或请求用户继续

tools:
  - xeno_meta_switch_mode      # 切换到设备专家（接管）
  - xeno_meta_new_task          # 委派子任务（资料/图解分析）
  - xeno_meta_attempt_completion # 提交诊断报告

capabilities:
  - fault_analysis          # 可扩展为专业技能
  - diagnostics_planning
  - task_orchestration

constraints:
  - 必须优先识别信息缺口并委派 material_assistant
  - 必须收齐所有子任务结果后再决策
  - 完成后必须使用 attempt_completion 提交结构化报告

example: |
  用户输入: "数控机床 X轴跳动"
  思考: 需要机械结构图纸 + 可能部件型号
  执行:
    1. new_task(material_assistant, "查找该机床 X 轴传动结构图 expected_output: 结构描述")
    2. new_task(material_assistant, "查找进给电机型号规格 expected_output: 电机参数")
    3. 等待结果，分析可能故障点
    4. 如仍需进一步排查：
         - new_task(equipment_expert, "分析结构图诊断潜在故障原因 expected_output: 诊断结论")
    5. 形成报告，attempt_completion(result="...")
```

**验证标准**:
- YAML 可加载
- 可以规划复杂诊断流程并委派子任务
- 综合子任务结果并完成报告

---

#### Task 1.3: 创建 Equipment Expert 角色定义

**File**: `packages/xeno-agent/config/roles/equipment_expert.yaml`

**职责**:
- 图解分析专家
- 物理操作指导（完全接管时）
- 双模式：Worker (分析) + Active (接管/指导)

**PROMPT 模板**:
```yaml
name: Equipment Expert
role: 设备结构与操作专家
goal: 分析技术图纸，指导物理操作诊断
backstory: 你是资深的设备工程师，精通机械结构、工作原理和现场诊断方法。你现在处于 {{ MODE }} 模式。

thought_process: |
  ## 模式区分

  ### 模式 A: 分析模式 (Worker)
  - 执行特定技术任务：
    - 图解结构分析
    - 原理匹配
    - 可能性排序

  - 输出：
    - 新增可能原因或结论
    - 建议下一步排查方向

  - 行为：
    - 完成任务
    - NOT switch_mode (保持原角色继续)

  ### 模式 B: 操作指导模式 (Active)
  - 从故障专家完全接管用户交互
  - 提供循序渐进的操作指导
  - 在完成或无法继续时返回/完成

  - 行为：
    - 可以 switch_mode 返回 fault_expert
    - 可以 attempt_completion 提交最终结论

  ## 图解分析任务执行

  当收到图解分析需求时：
  1. 分析结构图/电气图/液压图
  2. 识别关键部件/管路/电路
  3. 匹配故障症状与结构特征
  4. 形成诊断结论或建议

  ## 操作指导任务执行

  当被切换为 Active 模式时：
  1. 确认当前状态和可用工具
  2. 提供逐步操作指导
  3. 在需要时请求更多信息/图片
  4. 完成诊断或建议返回故障专家

tools:
  - xeno_meta_switch_mode      # 返回故障专家 (仅 Active 模式）
  - xeno_meta_new_task          # 若再次需要资料分析，仍可委派
  - xeno_meta_attempt_completion # 提交指导结果 (Active 模式）

capabilities:
  - diagram_analysis             # 图纸分析
  - operational_diagnosis      # 操作诊断
  - mechanical_expertise       # 机械专业知识

constraints:
  - Worker 模式：完成单个分析任务，不切换角色
  - Active 模式：指导操作，可返回 fault_expert 或完成
  - 任何分析任务必须引用来源 (手册批次号、图纸编号）

example_worker: |
  用户/故障专家: "请分析该伺服驱动器接线图"
  思考: 需要识别接线规范与故障点
  执行: 分析图纸，识别可能短路/开路点
  输出: "根据连接图，接触器线路可能存在故障..."

example_active: |
  故障专家: switch_mode("equipment_expert", "需要现场指导排查机械臂故障")
  你: (Active 模式) "好的，我将接管。请按以下步骤操作..."
  (后提供逐步指导，或在无法继续时返回)

```

**验证标准**:
- YAML 可加载
- Worker 模式下可执行分析任务
- Active 模式下可指导操作并可能返回
- 分析结果必须包含引用

---

#### Task 1.4: 创建 Material Assistant 角色定义

**File**: `packages/xeno-agent/config/roles/material_assistant.yaml`

**职责**:
- 深层检索与文档摘要
- 提供引用规范输出
- 纯 Worker 模式（主动关联）

**PROMPT 模板**:
```yaml
name: Material Assistant
role: 文献/资料检索与摘要专家
goal: 快速检索技术手册、论文、标准，提供引用规范的摘要
backstory: 你是资深的资料研究员，擅长在庞大的知识库中定位信息并提炼要点。

thought_process: |
  1. 理解检索需求：
     - 目标设备/型号
     - 技术领域（机械/电气/液压）
     - 关键信息类型（尺寸/参数/结构/原理）
     - 预期输出格式（摘要/表格/步骤列表）

  2. 检索策略：
     - 选择合适的搜索接口（糊搜索/Copilot/图灵机器人）
     - 设计检索词（型号 + 关键术语）
     - 若失败，扩展/调整检索词

  3. 信息验证与引用：
     - 验证信息来源（是否为最新、是否权威）
     - 摘要关键信息
     - 保留批次号/页码/图纸编号等引用信息

  4. 输出格式化：
     - 遵循 Markdown 协议
     - 使用规范的引用格式
     - 清晰呈现关键信息

capabilities:
  - deep_search           # 深层检索
  - document_summary      # 文档摘要
  - citation_quality      # 引用规范

constraints:
  - 必须为所有关键信息提供引用（即使间接）
  - 引用必须包含文档标识（批次号/图纸编号/页码）
  - 对存在冲突的信息必须注明
  - 对缺失的信息必须明确说明

example: |
  用户/故障专家: "查找机械臂伺服电机 Panasonic MSMA042S1 的技术规格"
  检索: 使用搜索接口检索 "Panasonic MSMA042S1 spec"
  验证: 确认来源为官方技术手册
  输出: |
    **Panasonic MSMA042S1 伺服电机技术规格** [手册批次号: PM-2023-042]

    | 参数 | 数值 |
    |---|---|
    | 额定功率 | 200W |
    | 额定转速 | 3000 rpm |
    | 扭矩 | 0.64 N·m |

    来源: Panasonic A6 系列伺服电机技术手册第 24 页
```

**验证标准**:
- YAML 可加载
- 检索结果包含完整引用
- 使用 Markdown 格式输出

---

### Phase 2: 核心功能补全 (P0 - 阻塞核心场景)

#### Task 2.1: 实现 XenoAgentBuilder.from_yaml()

**File**: `packages/xeno-agent/src/xeno_agent/agents/builder.py`

**当前状态**:
```python
def from_yaml(self, yaml_path: str) -> "XenoAgentBuilder":
    # Hydrate from YAML definition
    pass  # ← 未实现
```

**目标**:
```python
def from_yaml(self, yaml_path: str) -> "XenoAgentBuilder":
    """
    从 YAML 配置文件水化构建器。

    Args:
        yaml_path: 角色 YAML 文件路径 (config/roles/*.yaml)

    Returns:
        水化后的 XenoAgentBuilder 实例
    """
    config = self._load_role_config(yaml_path)  # 复用 ConfigLoader

    # 设置各属性
    self.role_name = config.name
    self.role_type = config.role_type  # "Worker"/"Active"/"Orchestrator"
    self.prompt = config.prompt  # thought_process 作为 prompt

    # 处理 capabilities
    self.capabilities = config.capabilities

    # 处理 tools
    # 1. 工具字符串（元工具）：通过 SkillRegistry 查找
    #    self.tools.append(skill_registry.get_tool(tool_name))
    # 2. 技能标识（capabilities）：标记为专业技能
    #    self.add_capability(capability_id)

    return self
```

**依赖**:
- `ConfigLoader` 已实现 `load_role_config(yaml_path)` → 返回 `RoleConfig` 数据类
- `SkillRegistry` 已有 `get_tool(name)` 方法

**验证**:
```python
# 在 CLI 中使用
builder = XenoAgentBuilder()
builder.from_yaml("config/roles/qa_assistant.yaml")
agent = builder.build(agent_registry, skill_registry, llm)
assert agent.role_name == "Q&A Assistant"
```

---

#### Task 2.2: 修复子任务回传机制

**File**: `packages/xeno-agent/src/xeno_agent/core/flow.py`

**问题定位** (Line 82-94):
```python
# NOTE: Should track this result back to caller if needed
# Current implementation stacks child independently
```

**预期行为**:
1. 子任务调用 `NewTaskSignal(..., result="...")` 完成
2. `NewTaskFlowStep` 解析 `last_signal`
3. **将 result 注入父任务的 conversation_history**
4. 父任务在下一轮对话中可使用该结果

**修改方案**:
```python
@listen("new_task")
def new_task(self):
    """Handle NEW_TASK signal from agent."""
    signal = self.state.last_signal

    # ... 现有代码 ...

    # 【新增】将子任务结果注入到父上下文
    if signal.result:
        # 添加到当前 conversation_history，使父任务可见
        self.state.conversation_history.append({
            "role": "assistant",
            "content": f"[子任务结果] {signal.result}",
            "metadata": {
                "source": "new_task",
                "child_agent": signal.agent_name,
                "task_id": signal.task_id
            }
        })

    # ... 继续 ...
```

**验证**:
```python
# 父任务委派子任务
父: new_task("material_assistant", "查找电机型号", expected_output="技术规格")

# 子任务完成
子: attempt_completion(result="Panasonic MSMA042S1, 200W, 3000rpm")

# 父任务在下一轮应能看到：
User: "请查找电机规格"
Assistant: "[子任务结果] Panasonic MSMA042S1, 200W, 3000rpm"
# ↑ 父任务现在可以使用此信息
```

---

#### Task 2.3: 定义"正常完成"路由语义

**File**: `packages/xeno-agent/src/xeno_agent/core/flow.py`

**问题定位** (Line 105-118):
```python
elif self.state.current_agent_step.is_last_step():
    # Agent completed its steps
    if self.state.stack[-1].is_isolated:
        # This was a NewTask/Isolated subtask, return
        self.state.pop_completion()
        return RouteNextStep.RETURN_TO_SOURCE
    else:
        # Primary agent, not isolated
        # Should we terminate? Should we continue?
        # This is where routing logic for normal completions goes
        pass  # ← 未定义
```

**RFC 期望行为**:
1. **Agent 正常完成**（非 attempt_completion/switch_mode/new_task)
2. **继续同一模式对话**（适合交互式诊断场景）
3. **不退出**（除非显式 `attempt_completion`）

**修改方案**:
```python
elif self.state.current_agent_step.is_last_step():
    if self.state.stack[-1].is_isolated:
        self.state.pop_completion()
        return RouteNextStep.RETURN_TO_SOURCE
    else:
        # 【修改】正常完成 = 继续对话（不终止）
        # 除非显式调用 attempt_completion，否则不退出
        logger.info(
            f"Agent {current_mode.name} completed normally (no signal). "
            f"Continuing conversation in same mode."
        )
        # 重新推入同一个agent继续对话
        return RouteNextStep.CONTINUE_CURRENT_MODE  # 继续当前模式
```

**说明**:
- `RouteNextStep.CONTINUE_CURRENT_MODE`: 新常量，表示继续当前模式
- 或者直接调用 `execute_modal_agent_step(current_mode)`

---

### Phase 3: 共享能力协议 (P1 - 提升质量)

#### Task 3.1: 实现输出验证层

**File**: `packages/xeno-agent/src/xeno_agent/core/validators.py` (新建)

**职责**:
- 验证 Agent 输出是否符合 Markdown 协议
- 验证是否包含引用

**接口设计**:
```python
from typing import Optional
import re

class OutputValidator:
    """Agent 输出验证器"""

    @staticmethod
    def validate_markdown(content: str) -> tuple[bool, list[str]]:
        """
        验证 Markdown 格式。

        Returns:
            (is_valid, errors)
        """
        errors = []

        # 基本格式检查（标题、列表、表格）
        # ...

        return len(errors) == 0, errors

    @staticmethod
    def validate_citation(content: str) -> tuple[bool, list[str]]:
        """
        验证引用格式。

        要求:
        - Material Assistant: 必须引用
        - 其它专家: 建议引用

        格式: [来源描述/标识]

        Returns:
            (requires_citation, errors)
        """
        errors = []
        citations = re.findall(r'\[([^\]]+)\]', content)

        if not citations:
            errors.append("输出缺少引用，请添加 [来源描述]")

        return len(errors) == 0, errors
```

**集成**:
```python
# 在 flow.py 的 execute_agent_step 后调用
if agent_step.output:
    is_valid, errors = OutputValidator.validate_markdown(agent_step.output)
    if not is_valid:
        logger.warning(f"Agent output Markdown validation failed: {errors}")

    # 角色特定约束
    if current_mode.name == "Material Assistant":
        has_citation, errors = OutputValidator.validate_citation(agent_step.output)
        if not has_citation:
            logger.warning(f"Material Assistant output missing citations: {errors}")
```

---

#### Task 3.2: 明确元工具调用说明

**File**: `packages/xeno-agent/src/xeno_agent/skills/builtin/meta_tools.py`

**当前问题**:
- 工具描述过于简要
- 未说明何时使用哪个工具

**修改方案**:
```python
SwitchModeTool = Tool(
    name="xeno_meta_switch_mode",
    description="""
    【切换角色/模式】
    使用场景：
    1. QA Assistant → Fault Expert: 检测到复杂故障诊断场景
    2. Fault Expert → Equipment Expert: 需要物理操作/现场指导
    3. Equipment Expert → Fault Expert: Active 模式下返回编排
    """,
    func=switch_mode,
    # ...
)

NewTaskTool = Tool(
    name="xeno_meta_new_task",
    description="""
    【委派子任务】
    使用场景：
    1. QA Assistant → Material Assistant: 简单信息查询
    2. Fault Expert → Material Assistant: 查找资料/规格/图纸
    3. Fault Expert → Equipment Expert (Worker): 分析图纸/诊断

    务作：临时切换角色执行任务，返回后继续原流程
    """,
    func=new_task,
    # ...
)
```

---

### Phase 4: 样例重写 (P2 - 演示复现在)

#### Task 4.1: 重写 CLI 样例 1 - 4 角色协作

**File**: `packages/xeno-agent/examples/rfc_compliant_example.py`

**场景**:
```
用户: "数控机床 X 轴重复定位精度差，检查无异常"
    ↓
Q&A Assistant: "检测到复杂故障，切换故障专家"
    ↓ switch_mode("fault_expert")
Fault Expert: "需要机床结构图 + 传动系统规格"
    ↓ new_task(material_assistant, "查找该机床 X 轴传动结构图")
    ↓ new_task(material_assistant, "查找进给电机型号")
Fault Expert: "根据结构图分析，需要排查丝杠副磨损情况"
    ↓ new_task(equipment_expert, "分析结构图，诊断潜在故障点")
Equipment Expert: "可能是丝杠反向间隙过大"
Fault Expert: "建议现场排查丝杠预紧力，需要操作指导"
    ↓ switch_mode("equipment_expert", "需要现场操作指导")
Equipment Expert: (Active 模式) "好的，请按以下步骤排查..."
    ↓ 提供逐步指导
Equipment Expert: "如果问题仍存在，可能需要更换"
    ↓ switch_mode("fault_expert")
Fault Expert: attempt_completion(result="诊断报告...")
```

---

#### Task 4.2: 重写诊断场景样例

**重写**：
- 使用 4 角色协作
- 展示 `switch_mode`/`new_task` 调用
- 展示子任务结果回传使用

---

#### Task 4.3: 创建测试用例

**场景覆盖**:
1. QA Assistant 简单查询 → Material Assistant
2. 复杂故障 → Fault Expert → Material Assistant → Equipment Expert
3. 子任务结果回传验证
4. 正常完成继续对话

---

## 验收标准

### 功能验收

- ✅ 4 角色可从 `config/roles/*.yaml` 加载
- ✅ QA Assistant 可正确区分简单/复杂问题
- ✅ Fault Expert 可规划诊断并委派子任务
- ✅ Equipment Expert 支持双模式（Worker/Active）
- ✅ Material Assistant 输出包含引用
- ✅ `XenoAgentBuilder.from_yaml()` 可正确水化
- ✅ 子任务结果可被父任务访问
- ✅ 正常完成不退出流程
- ✅ CLI 样例 1 演示完整 4 角色协作

### 质量验收

- ✅ 所有 Agent 输出符合 Markdown 规范
- ✅ Material Assistant 100% 包含引用
- ✅ 代码通过 Ruff 检查
- ✅ 代码有类型注解

---

## 风险与依赖

### 风险

- **元工具行为理解**: CrewAI Agent 可能难以理解"何时使用哪个工具"
  - 缓解：强化 Prompt 中的角色/任务/约束描述

- **子任务异步性**: NewTask 可能返回前父任务超时
  - 缓解：同步等待子任务完成（当前已实现）

### 依赖

- CrewAI 框架行为（路由/步骤执行）
- LLM 理解复杂 Prompt 能力
- 接口网络可访问性（糊搜索/Copilot/图灵机器人）

---

## 附录

### A. 配置文件位置

```
packages/xeno-agent/
├── config/
│   ├── roles/
│   │   ├── qa_assistant.yaml           # 新增
│   │   ├── fault_expert.yaml          # 新增
│   │   ├── equipment_expert.yaml      # 新增
│   │   └── material_assistant.yaml    # 新增
│   ├── tools/
│   │   └── ... (现有)
│   └── flows/
│       └── diagnosis_flow.yaml        # 新增 (可选)
├── src/xeno_agent/
│   ├── agents/
│   │   ├── builder.py                # 修改 (from_yaml)
│   │   └── ...
│   ├── core/
│   │   ├── flow.py                   # 修改 (子任务回传 + 正常完成路由)
│   │   ├── state.py
│   │   └── validators.py             # 新增 (输出验证)
│   └── skills/
│       └── builtin/
│           └── meta_tools.py          # 修改 (工具说明优化)
└── examples/
    ├── rfc_compliant_example.py       # 新增
    └── diagnosis_scenario.py         # 修改 (4 角色协作)
```

### B. Timeline 预估

| Phase | 任务 | 预估 |
|-------|------|------|
| 1.1 | QA Assistant 角色定义 | 2h |
| 1.2 | Fault Expert 角色定义 | 2h |
| 1.3 | Equipment Expert 角色定义 | 2h |
| 1.4 | Material Assistant 角色定义 | 1.5h |
| 2.1 | XenoAgentBuilder.from_yaml | 1.5h |
| 2.2 | 子任务回传机制 | 1h |
| 2.3 | 正常完成路由 | 0.5h |
| 3.1 | 输出验证层 | 1.5h |
| 3.2 | 元工具说明优化 | 0.5h |
| 4.1 | CLI 样例重写 | 2h |
| 4.2 | 诊断场景重写 | 1.5h |
| 4.3 | 测试用例 | 2h |

**总计**: ~20 小时

---

## 决策

**状态**: ✅ 已批准

**下一步**: 开始实施 Phase 1 Task 1.1-1.4
