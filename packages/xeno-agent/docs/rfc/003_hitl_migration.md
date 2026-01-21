# RFC-003: 迁移到 CrewAI 官方 Human-in-the-Loop 机制

| Status | Proposed |
| :--- | :--- |
| **Author** | Antigravity (Sisyphus) |
| **Date** | 2026-01-19 |
| **Scope** | HITL Migration, CrewAI Integration |
| **Related RFCs** | 001, 002 |

---

## 1. 执行摘要

### 1.1 目标

将 xeno-agent 的自定义 Human-in-the-Loop (HITL) 系统迁移到 CrewAI 官方的 `@human_feedback` 机制，实现基础迁移并弃用现有的交互扩展。

### 1.2 动机

**当前问题**:
- ❌ `InteractionHandler` 单例手动实现，维护负担重
- ❌ `@requires_approval` 装饰器需要手动实现审批逻辑
- ❌ `AskFollowupSignal` 异常机制与 CrewAI Flow 不一致
- ❌ 无异步支持（Slack/Email 等场景）
- ❌ 无企业级 Webhook 集成

**迁移价值**:
- ✅ 利用 CrewAI 内置的状态持久化和异步支持
- ✅ 简化代码维护，减少自定义基础设施
- ✅ 获得框架级优化和 bug 修复
- ✅ 为未来 Webhook 集成奠定基础
- ✅ 统一异常处理和错误恢复机制

### 1.3 范围

**包含**:
- 迁移基础 HITL 交互机制到 `@human_feedback` 装饰器
- 弃用 `AskFollowupSignal`、`AskFollowupTool`、`@requires_approval`
- 弃用 `InteractionHandler` 单例
- 更新现有工具和角色定义以使用新机制
- 更新测试以覆盖新机制

**不包含**:
- 异步 Provider 实现（Slack/Email/Webhook）
- 企业级 Webhook 集成
- 高级功能（反馈历史审计、LLM 自动分类等）

---

## 2. 当前实现分析

### 2.1 自定义 HITL 架构

```python
# 核心组件
class InteractionHandler:
    """人类交互单例处理器"""
    _auto_approve: bool = False
    _input_provider: Callable | None = None

    @classmethod
    def ask_approval(cls, message: str) -> bool:
        """请求工具执行审批"""
        if cls._auto_approve:
            return True
        response = cls._input_provider(input(f"[APPROVAL REQUIRED] {message} (y/n): "))
        return response.lower() in ["y", "yes"]

    @classmethod
    def get_input(cls, prompt: str) -> str:
        """获取自由文本输入"""
        return cls._input_provider(input(f"{prompt}: "))

def requires_approval(method):
    """需要审批的工具方法装饰器"""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if InteractionHandler.ask_approval(f"Tool '{self.name}' called with {kwargs}"):
            return method(self, *args, **kwargs)
        return f"ACTION DENIED: User rejected '{self.name}'."
    return wrapper

class AskFollowupSignal(SimulationSignal):
    """向用户提问的信号"""
    def __init__(self, question: str, options: list[str] | None = None):
        super().__init__(question, options)
        self.question = question
        self.options = options
```

### 2.2 Flow 集成

```python
# flow.py - 处理 AskFollowupSignal
@listen("execute_agent")
def execute_agent_step(self):
    try:
        crew = Crew(agents=[agent], tasks=[task])
        result = crew.kickoff()
    except AskFollowupSignal as e:
        # 拦截信号，获取用户输入
        answer = InteractionHandler.get_input(e.question)
        self.state.conversation_history.append({"role": "assistant", "content": e.question})
        self.state.conversation_history.append({"role": "user", "content": answer})
        return "execute_agent"
```

### 2.3 工具使用

```python
# meta_tools.py - 元工具使用装饰器
class SwitchModeTool(BaseTool):
    name: str = "switch_mode"
    description: str = "【切换角色/模式】..."

    @requires_approval  # HITL 装饰器
    def _run(self, mode_slug: str, reason: str):
        raise SwitchModeSignal(target_mode=mode_slug, reason=reason)

class AskFollowupTool(BaseTool):
    name: str = "ask_followup_question"
    description: str = "【询问用户】..."

    def _run(self, question: str, options: list[str] | None = None):
        # 无需装饰器，直接触发信号
        raise AskFollowupSignal(question=question, options=options)
```

### 2.4 CLI 配置

```python
# main.py - 支持 --auto-approve
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()

    if args.auto_approve:
        InteractionHandler.set_auto_approve(True)

    # 启动 Flow
    flow.kickoff()
```

### 2.5 优势与劣势

**优势**:
- ✅ 与信号系统深度集成
- ✅ 支持自动批准模式（用于测试）
- ✅ 支持自定义输入提供者（程序化控制）
- ✅ 完整的测试覆盖

**劣势**:
- ❌ 需要维护自定义基础设施
- ❌ 无异步支持
- ❌ 无 Webhook 集成
- ❌ 异常机制与 CrewAI Flow 不一致
- ❌ 手动实现审批逻辑

---

## 3. CrewAI 官方 HITL 机制

### 3.1 架构概览

CrewAI 提供三种 HITL 实现方式，按复杂度递增：

| 层次 | API | 复杂度 | 适用场景 |
|------|-----|--------|----------|
| **基础** | `human_input=True` | ⭐ | 快速原型，简单输入 |
| **流程级** | `@human_feedback` | ⭐⭐ | 审批工作流，路由控制 |
| **异步/生产** | Custom Provider + Webhook API | ⭐⭐⭐ | Slack/Email/Webhook 集成 |

### 3.2 核心特性

#### 3.2.1 装饰器式 HITL

```python
from crewai.flow import Flow, start, listen
from crewai.flow.human_feedback import human_feedback

class ReviewFlow(Flow):
    @start()
    @human_feedback(message="请审核此内容:")
    def generate_content(self):
        return "AI 生成的内容"

    @listen(generate_content)
    def process_feedback(self, result):
        # result 是 HumanFeedbackResult 对象
        print(f"反馈: {result.feedback}")
```

**特性**:
- ✅ 自动状态持久化（暂停/恢复）
- ✅ 异常处理和错误恢复
- ✅ 简洁的装饰器 API
- ✅ 与 Flow 生命周期无缝集成

#### 3.2.2 带路由的 HITL

```python
@start()
@human_feedback(
    message="批准此内容发布?",
    emit=["approved", "rejected", "needs_revision"],
    llm="gpt-4o-mini",
    default_outcome="needs_revision",
)
def review_content(self):
    return "草稿内容"

@listen("approved")
def publish(self, result):
    print(f"发布: {result.output}")

@listen("rejected")
def discard(self, result):
    print(f"拒绝: {result.feedback}")

@listen("needs_revision")
def revise(self, result):
    print(f"修订: {result.feedback}")
```

**`emit` 参数**:
- 使用 LLM 将非结构化反馈自动分类到指定结果
- 简化下游处理（`@listen` 按结果触发）
- 必须提供 `default_outcome` 处理边缘情况

#### 3.2.3 HumanFeedbackResult 结构

```python
@dataclass
class HumanFeedbackResult:
    output: Any              # 原始方法输出
    feedback: str            # 人类反馈文本
    outcome: str | None      # 分类结果（如果指定了 emit）
    timestamp: datetime      # 反馈时间
    method_name: str         # 装饰方法名称
    metadata: dict           # 附加元数据
```

### 3.3 内置支持

- ✅ **自动持久化**: Flow 状态自动保存，支持暂停/恢复
- ✅ **异步支持**: 通过 `HumanFeedbackProvider` 协议
- ✅ **错误恢复**: 内置异常处理和重试机制
- ✅ **Webhook 集成**: 企业级异步工作流支持
- ✅ **反馈历史**: `self.human_feedback_history` 访问所有交互

---

## 4. 迁移策略：基础迁移

### 4.1 核心决策

**保留**（非 HITL 相关）:
- ✅ `SwitchModeSignal` - GOTO 流程控制
- ✅ `NewTaskSignal` - GOSUB 子任务委派
- ✅ `CompletionSignal` - RETURN 任务完成
- ✅ `UpdateTodoListSignal` - Todo 列表更新
- ✅ 堆栈状态管理（`SimulationState`）
- ✅ 信号路由逻辑（`@router`）

**弃用**（HITL 专用）:
- ❌ `AskFollowupSignal` - 用户提问信号
- ❌ `AskFollowupTool` - 用户提问工具
- ❌ `@requires_approval` - 审批装饰器
- ❌ `InteractionHandler` - 交互单例处理器

**新增**:
- 🆕 使用 `@human_feedback` 装饰器实现 HITL
- 🆕 Flow 方法直接使用 CrewAI HITL 机制

### 4.2 架构变更对比

#### 迁移前

```
用户交互
  ↓
InteractionHandler.get_input()
  ↓
工具调用 @requires_approval
  ↓
审批逻辑（手动实现）
  ↓
ask_followup_question
  ↓
AskFollowupSignal
  ↓
Flow 拦截信号
  ↓
返回 Agent 继续执行
```

#### 迁移后

```
Flow 方法 @human_feedback
  ↓
CrewAI 拦截并暂停执行
  ↓
自动状态持久化
  ↓
InteractionHandler.get_input() (保留用于输入获取)
  ↓
CrewAI 恢复执行
  ↓
下游 @listen 方法触发
```

### 4.3 代码实现

#### 4.3.1 控制台 Provider（保留 InteractionHandler 作为输入源）

```python
# src/xeno_agent/core/hitl.py
from crewai.flow import HumanFeedbackProvider

class ConsoleFeedbackProvider(HumanFeedbackProvider):
    """控制台反馈提供者 - 保留 InteractionHandler 作为输入源"""

    def request_feedback(self, context, flow):
        """
        从控制台获取反馈。

        Args:
            context: PendingFeedbackContext，包含消息和元数据
            flow: Flow 实例

        Returns:
            反馈文本字符串
        """
        # 保留现有的 InteractionHandler 机制获取输入
        from xeno_agent.core.hitl import InteractionHandler

        prompt = context.message
        if context.method_output:
            prompt += f"\n\n内容:\n{context.method_output}"

        return InteractionHandler.get_input(prompt)
```

#### 4.3.2 修改 Flow 使用 CrewAI HITL

```python
# src/xeno_agent/core/flow.py
from crewai.flow import Flow, start, listen, router
from crewai.flow.human_feedback import human_feedback
from xeno_agent.core.hitl import ConsoleFeedbackProvider

class XenoSimulationFlow(Flow):
    """Xeno 仿真 Flow - 使用 CrewAI HITL 机制"""

    # ... 现有信号路由逻辑保留 ...

    @router("execute_agent")
    def route_after_agent(self):
        """Agent 执行后的路由决策"""
        last_signal = self.state.last_signal

        # 保留信号路由逻辑
        if isinstance(last_signal, SwitchModeSignal):
            # GOTO 逻辑
            return "switch_mode"
        elif isinstance(last_signal, NewTaskSignal):
            # GOSUB 逻辑
            return "new_task"
        elif isinstance(last_signal, CompletionSignal):
            # RETURN 逻辑
            return "completion"

        # 正常完成 - 使用 HITL 获取确认
        return "ask_completion_approval"

    @listen("ask_completion_approval")
    @human_feedback(
        message="Agent 已完成任务，是否继续？",
        emit=["continue", "complete", "restart"],
        llm="gpt-4o-mini",
        default_outcome="continue",
        provider=ConsoleFeedbackProvider(),
    )
    def get_completion_approval(self):
        """获取任务完成后的用户决策"""
        # 返回任意值，实际行为由下游 @listen 决定
        return self.state.stack[-1].mode_slug

    @listen("continue")
    def continue_in_same_mode(self):
        """继续当前模式"""
        # 不做任何操作，重新执行 Agent
        return "execute_agent"

    @listen("complete")
    def finish_current_task(self):
        """完成当前任务"""
        current_frame = self.state.stack.pop()
        if not self.state.stack:
            # 根任务完成
            self.state.final_output = current_frame.task_id
            self.state.is_terminated = True
        return "execute_agent"

    @listen("restart")
    def restart_flow(self):
        """重新开始 Flow"""
        # 重置状态
        self.state.stack = [self.state.stack[0]]  # 保留初始帧
        self.state.conversation_history = []
        self.state.last_signal = None
        return "execute_agent"
```

#### 4.3.3 弃用 AskFollowupTool

```python
# src/xeno_agent/skills/builtin/meta_tools.py

# ⚠️ DEPRECATED: 此工具将被弃用
# 请使用 Flow 的 @human_feedback 装饰器替代
class AskFollowupTool(BaseTool):
    name: str = "ask_followup_question"
    description: str = "【询问用户】⚠️ 已弃用，请使用 Flow 级 HITL"

    def _run(self, question: str, options: list[str] | None = None):
        # 弃用警告
        logger.warning(
            "ask_followup_question 已弃用。"
            "请使用 Flow 的 @human_feedback 装饰器。"
        )
        # 保留行为以确保向后兼容
        raise AskFollowupSignal(question=question, options=options)
```

#### 4.3.4 修改元工具（可选：保留 @requires_approval 用于工具级审批）

```python
# 选项 1: 完全移除 @requires_approval
class SwitchModeTool(BaseTool):
    name: str = "switch_mode"
    description: str = "【切换角色/模式】..."

    def _run(self, mode_slug: str, reason: str):
        raise SwitchModeSignal(target_mode=mode_slug, reason=reason)

# 选项 2: 保留 @requires_approval 但更新为警告模式
@requires_approval  # 保留但标记为已弃用
def _run(self, mode_slug: str, reason: str):
    logger.warning(
        f"Tool 'switch_mode' 使用了已弃用的 @requires_approval。"
        f"建议使用 Flow 的 @human_feedback 进行审批。"
    )
    raise SwitchModeSignal(target_mode=mode_slug, reason=reason)
```

**推荐**: 选项 1（完全移除），因为 Flow 级 `@human_feedback` 更符合 CrewAI 设计哲学。

### 4.4 交互模式支持

```python
# src/xeno_agent/core/hitl.py
from crewai.flow.human_feedback import human_feedback
from xeno_agent.core.hitl import InteractionHandler

class AutoApproveProvider(HumanFeedbackProvider):
    """自动批准提供者 - 用于测试"""

    def request_feedback(self, context, flow):
        # 直接返回批准消息
        return "approved"

def create_hitl_flow(auto_approve: bool = False):
    """创建带 HITL 配置的 Flow"""

    provider = AutoApproveProvider() if auto_approve else ConsoleFeedbackProvider()

    flow = XenoSimulationFlow(
        agent_registry=agent_registry,
        state=initial_state,
        hitl_provider=provider,  # 新增参数
    )

    return flow
```

### 4.5 CLI 配置更新

```python
# src/xeno_agent/main.py
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-approve", action="store_true",
                   help="自动批准所有 HITL 请求（测试模式）")
    parser.add_argument("--disable-hitl", action="store_true",
                   help="完全禁用 HITL（所有交互自动批准）")
    args = parser.parse_args()

    # 配置 HITL
    if args.disable_hitl:
        InteractionHandler.set_auto_approve(True)
        logger.warning("HITL 已禁用，所有交互将自动批准")
    elif args.auto_approve:
        logger.info("启用自动批准模式")

    # 创建 Flow
    flow = create_hitl_flow(auto_approve=args.auto_approve)
    flow.kickoff()
```

---

## 5. 实施计划

### Phase 1: 基础迁移（P0 - 1天）

#### Task 1.1: 创建 ConsoleFeedbackProvider
**File**: `src/xeno_agent/core/hitl.py`

**任务**:
- [ ] 新增 `ConsoleFeedbackProvider` 类实现 `HumanFeedbackProvider` 协议
- [ ] 保留 `InteractionHandler` 作为输入源
- [ ] 添加日志记录 HITL 交互

**验证**:
```python
provider = ConsoleFeedbackProvider()
assert hasattr(provider, "request_feedback")
```

#### Task 1.2: 修改 XenoSimulationFlow 使用 @human_feedback
**File**: `src/xeno_agent/core/flow.py`

**任务**:
- [ ] 新增 `get_completion_approval` 方法使用 `@human_feedback`
- [ ] 新增下游 `@listen` 方法处理 `["continue", "complete", "restart"]`
- [ ] 更新 `route_after_agent` 返回 `"ask_completion_approval"`
- [ ] 保留现有信号路由逻辑（`SwitchModeSignal` 等）

**验证**:
```python
# Flow 应能暂停并获取输入
flow = XenoSimulationFlow(...)
flow.kickoff()
# 应能响应控制台输入并继续
```

#### Task 1.3: 弃用 AskFollowupSignal 和 AskFollowupTool
**Files**:
- `src/xeno_agent/core/signals.py`
- `src/xeno_agent/skills/builtin/meta_tools.py`

**任务**:
- [ ] 标记 `AskFollowupSignal` 为 `@deprecated`
- [ ] 标记 `AskFollowupTool` 为 `@deprecated`
- [ ] 添加弃用警告日志
- [ ] 更新所有使用 `ask_followup_question` 的工具描述

**验证**:
```python
# 应显示弃用警告
import warnings
with warnings.catch_warnings(record=True) as w:
    from xeno_agent.core.signals import AskFollowupSignal
    assert len(w) == 1
    assert issubclass(w[0].category, DeprecationWarning)
```

#### Task 1.4: 更新 CLI 支持 --auto-approve
**File**: `src/xeno_agent/main.py`

**任务**:
- [ ] 保留 `--auto-approve` 标志（向后兼容）
- [ ] 添加 `--disable-hitl` 标志（新功能）
- [ ] 更新 `InteractionHandler` 配置逻辑
- [ ] 添加日志提示用户当前 HITL 模式

**验证**:
```bash
# 测试自动批准
uv run python -m xeno_agent --auto-approve

# 测试禁用 HITL
uv run python -m xeno_agent --disable-hitl
```

#### Task 1.5: 更新测试
**File**: `tests/test_hitl.py`

**任务**:
- [ ] 新增 `test_console_feedback_provider` 测试
- [ ] 更新 `test_interaction_handler` 测试
- [ ] 新增 `test_human_feedback_flow` 测试
- [ ] 确保 `@requires_approval` 弃用警告被测试

**验证**:
```bash
uv run pytest tests/test_hitl.py -v
```

### Phase 2: 清理和优化（P1 - 0.5天）

#### Task 2.1: 移除 @requires_approval 装饰器
**File**: `src/xeno_agent/core/hitl.py`

**任务**:
- [ ] 标记 `@requires_approval` 为 `@deprecated`
- [ ] 添加文档说明使用 `@human_feedback` 替代
- [ ] 保留函数体以确保向后兼容

**验证**:
```python
# 应显示弃用警告
@requires_approval
def dummy_tool():
    pass
# 调用时应警告
```

#### Task 2.2: 更新所有元工具移除装饰器
**File**: `src/xeno_agent/skills/builtin/meta_tools.py`

**任务**:
- [ ] 移除所有 `@requires_approval` 装饰器
- [ ] 更新工具描述，说明不再需要手动审批
- [ ] 确保行为一致（直接触发信号）

**验证**:
```bash
# 测试工具调用
uv run pytest tests/test_meta_tools.py -v
```

#### Task 2.3: 更新角色定义文档
**Files**: `config/roles/*.yaml`

**任务**:
- [ ] 移除所有 `ask_followup_question` 工具引用
- [ ] 添加说明使用 Flow 级 HITL 进行交互
- [ ] 更新 `thought_process` 说明新交互模式

**验证**:
```python
# 角色配置应不包含弃用工具
config = ConfigLoader().load_role_config("fault_expert")
assert "ask_followup_question" not in config.tools
```

#### Task 2.4: 更新文档
**Files**:
- `使用说明.md`
- `docs/诊断系统模拟指南.md`
- `AGENTS.md`

**任务**:
- [ ] 更新 HITL 相关章节
- [ ] 移除 `ask_followup_question` 示例
- [ ] 添加 `@human_feedback` 使用示例
- [ ] 更新 CLI 参数说明

**验证**:
```bash
# 检查文档一致性
grep -r "ask_followup_question" docs/
# 应返回 0 或仅弃用说明
```

### Phase 3: 验证和发布（P1 - 0.5天）

#### Task 3.1: 完整回归测试
**任务**:
- [ ] 运行所有现有测试
- [ ] 确保 RFC 002 四角色协作场景正常
- [ ] 测试 --auto-approve 模式
- [ ] 测试交互式模式

**验证**:
```bash
uv run pytest tests/ -v --cov=xeno_agent
```

#### Task 3.2: 性能测试
**任务**:
- [ ] 对比迁移前后的执行时间
- [ ] 检查内存使用
- [ ] 验证状态持久化性能

**验证**:
```bash
# 使用诊断场景进行性能测试
time uv run python examples/diagnosis_scenario.py
```

#### Task 3.3: 发布准备
**任务**:
- [ ] 更新 `CHANGELOG.md`
- [ ] 标记版本（如 `v1.1.0`）
- [ ] 创建 GitHub Release Note
- [ ] 更新依赖版本（如有需要）

**验证**:
```bash
# 检查 CHANGELOG
head -n 50 CHANGELOG.md
```

---

## 6. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|-------|------|----------|
| **CrewAI API 行为不一致** | 中 | 高 | 使用稳定版本 (0.80.0+)，关注 release notes |
| **向后兼容性破坏** | 中 | 中 | 保留弃用警告，提供迁移指南 |
| **测试覆盖不足** | 低 | 中 | 全面回归测试，确保现有场景通过 |
| **用户学习曲线** | 低 | 低 | 更新文档，提供迁移示例 |
| **性能回归** | 低 | 低 | 性能测试，对比迁移前后指标 |
| **HITL 配置错误** | 中 | 低 | 提供清晰的 CLI 提示和日志 |

---

## 7. 向后兼容性

### 7.1 保留的弃用组件

| 组件 | 弃用版本 | 完全移除版本 | 替代方案 |
|------|----------|------------|----------|
| `AskFollowupSignal` | v1.1.0 | v2.0.0 | Flow `@human_feedback` |
| `AskFollowupTool` | v1.1.0 | v2.0.0 | Flow `@human_feedback` |
| `@requires_approval` | v1.1.0 | v2.0.0 | Flow `@human_feedback` |
| `InteractionHandler` | v1.1.0 | v2.0.0 | CrewAI `HumanFeedbackProvider` |

### 7.2 兼容性策略

#### v1.1.0（本版本）
- ✅ 保留所有弃用组件
- ✅ 弃用警告日志
- ✅ 新功能优先使用 CrewAI HITL
- ✅ 向后兼容性完全保证

#### v1.2.0（未来）
- ⚠️ 部分弃用组件移除
- ⚠️ 强制迁移到新机制
- ⚠️ 更新文档和示例

#### v2.0.0（最终）
- ❌ 完全移除弃用组件
- ❌ 仅支持 CrewAI HITL
- ❌ 清理所有向后兼容代码

---

## 8. 迁移示例

### 8.1 迁移前（旧方式）

```python
# config/roles/fault_expert.yaml
tools:
  - switch_mode
  - new_task
  - ask_followup_question  # ❌ 旧方式

thought_process: |
  1. 分析故障
  2. 需要信息时使用 ask_followup_question
  3. 完成诊断

# 使用场景
fault_expert: "需要更多信息，请提供..."
ask_followup_question(question="请提供设备型号", options=None)
```

### 8.2 迁移后（新方式）

```python
# config/roles/fault_expert.yaml
tools:
  - switch_mode
  - new_task
  # ✅ 移除 ask_followup_question

thought_process: |
  1. 分析故障
  2. 需要信息时等待 Flow HITL 交互
  3. 完成诊断或继续询问

# 使用场景
fault_expert: "完成初步分析，需要用户确认"
# Flow 自动调用 @human_feedback
@human_feedback(message="是否继续？", emit=["continue", "complete"])
# 用户选择后继续
```

### 8.3 Flow 代码示例

```python
# examples/migration_example.py
from xeno_agent import XenoSimulationFlow, SimulationState, TaskFrame

class MigratedFlow(XenoSimulationFlow):
    @router("execute_agent")
    def route_decision(self):
        """Agent 执行后的路由决策"""
        # 保留信号路由
        if isinstance(self.state.last_signal, SwitchModeSignal):
            return "switch_mode"
        elif isinstance(self.state.last_signal, CompletionSignal):
            return "completion"

        # 正常完成 - 使用 CrewAI HITL
        return "ask_user_feedback"

    @listen("ask_user_feedback")
    @human_feedback(
        message="Agent 已完成当前任务，下一步操作？",
        emit=["continue_same", "switch_expert", "complete"],
        llm="gpt-4o-mini",
        default_outcome="continue_same",
    )
    def get_user_decision(self):
        """获取用户决策"""
        # 返回当前模式名称（任意值）
        return self.state.stack[-1].mode_slug

    @listen("continue_same")
    def continue_mode(self):
        """继续当前模式"""
        return "execute_agent"

    @listen("switch_expert")
    def switch_to_expert(self):
        """切换到故障专家"""
        # 创建新信号
        self.state.last_signal = SwitchModeSignal(
            target_mode="fault_expert",
            reason="用户请求专家介入"
        )
        return "switch_mode"

    @listen("complete")
    def complete_flow(self):
        """完成 Flow"""
        self.state.is_terminated = True
        return "finish"

# 使用示例
flow = MigratedFlow(agent_registry=registry, state=state)
flow.kickoff()
```

---

## 9. 验收标准

### 9.1 功能验收

- ✅ `ConsoleFeedbackProvider` 正常工作
- ✅ `XenoSimulationFlow` 使用 `@human_feedback` 装饰器
- ✅ 所有测试通过（包括 HITL 相关测试）
- ✅ CLI 支持 `--auto-approve` 和 `--disable-hitl`
- ✅ 弃用警告正确显示
- ✅ RFC 002 四角色协作场景正常工作
- ✅ 状态持久化和恢复功能正常

### 9.2 代码质量验收

- ✅ 代码通过 Ruff 检查
- ✅ 代码有完整类型注解
- ✅ 测试覆盖率 > 80%
- ✅ 所有弃用组件有 `@deprecated` 标记
- ✅ 日志输出清晰，包含调试信息

### 9.3 文档验收

- ✅ 更新所有 HITL 相关文档
- ✅ 提供迁移指南
- ✅ CLI 帮助信息更新
- ✅ 代码注释更新

### 9.4 性能验收

- ✅ Flow 执行时间无显著增加（< 10%）
- ✅ 内存使用无明显增长（< 20%）
- ✅ 状态持久化时间 < 1s

---

## 10. 附录

### 10.1 文件变更清单

```
packages/xeno-agent/
├── src/xeno_agent/
│   ├── core/
│   │   ├── flow.py                      # 修改（新增 @human_feedback）
│   │   ├── hitl.py                      # 修改（新增 ConsoleFeedbackProvider）
│   │   └── signals.py                   # 修改（标记弃用）
│   └── skills/builtin/
│       └── meta_tools.py                # 修改（移除 @requires_approval）
├── config/roles/
│   ├── fault_expert.yaml              # 修改（移除 ask_followup_question）
│   ├── equipment_expert.yaml          # 修改（移除 ask_followup_question）
│   ├── material_assistant.yaml         # 修改（移除 ask_followup_question）
│   └── qa_assistant.yaml              # 修改（移除 ask_followup_question）
├── tests/
│   └── test_hitl.py                    # 修改（新增 HITL 测试）
├── 使用说明.md                           # 修改
├── docs/诊断系统模拟指南.md                  # 修改
└── examples/
    ├── migration_example.py              # 新增（迁移示例）
    └── diagnosis_scenario.py           # 修改（使用新机制）
```

### 10.2 Timeline 预估

| Phase | 任务 | 预估 |
|-------|------|------|
| 1.1 | 创建 ConsoleFeedbackProvider | 2h |
| 1.2 | 修改 XenoSimulationFlow | 3h |
| 1.3 | 弃用 AskFollowupSignal/Tool | 1.5h |
| 1.4 | 更新 CLI 支持 | 1h |
| 1.5 | 更新测试 | 2.5h |
| 2.1 | 移除 @requires_approval | 1h |
| 2.2 | 更新元工具 | 1h |
| 2.3 | 更新角色定义 | 1.5h |
| 2.4 | 更新文档 | 2h |
| 3.1 | 完整回归测试 | 2h |
| 3.2 | 性能测试 | 1.5h |
| 3.3 | 发布准备 | 1.5h |

**总计**: ~21.5 小时（~3 个工作日）

### 10.3 决策记录

**2026-01-19**: RFC-003 草案创建
**状态**: 🚧 Proposed
**下一步**: 等待团队评审和批准

### 10.4 参考资料

- [CrewAI HITL Documentation](https://docs.crewai.com/en/learn/human-in-the-loop)
- [CrewAI Flow Documentation](https://docs.crewai.com/en/learn/human-feedback-in-flows)
- [CrewAI GitHub Repository](https://github.com/crewAIInc/crewAI)
- [RFC-001: Offline Agent System Design](./001_agent_system_design/003_crewai_detailed_design.md)
- [RFC-002: 复现任务清单](./002_reproduction_tasks.md)

---

## 11. 决策

**状态**: ⏳ 待批准

**批准后开始**: Phase 1 Task 1.1
