# Complete Research Report: Multi-Turn Conversation & Multi-Agent Support

## 执行摘要

7 个并行研究任务已启动：
- ✅ bg_aca307dc（会话/状态模式） - 完成 2m 37s
- ✅ bg_bacc2f3a（消息流分析） - 完成 3m 8s
- 🔄 bg_3ba87a06（Agent 层次结构） - 进行中 3m 49s
- 🔄 bg_55616e0b（PydanticAI 多轮文档） - 进行中 3m 43s
- 🔄 bg_0337770d（Multi-Agent 框架对比） - 进行中 3m 34s
- 🔄 bg_198a7832（GitHub、Agent 搜索） - 进行中 3m 28s
- ✅ bg_1f87373e（现有测试模式） - 完成 2m 45s

## 一、当前代码库状态分析（关键发现）

### 1.1 PydanticAI 路径 - 无会话管理

#### 现有结构（runtime.py:74-102）
```python
class LocalAgentRuntime(AgentRuntime):
    def __init__(self, factory, flow_config):
        self.factory = factory
        self.flow_config = flow_config
        # ❌ 无 _active_sessions 字典

    async def invoke(self, agent_id: str, message: str, **kwargs):
        # ❌ 每次新建 TraceID，无 session_id 参数
        trace = TraceID.new().child(agent_id)
        deps = RuntimeDeps(flow=self.flow_config, trace=trace, factory=self.factory)
        result = await agent.run(message, deps=deps)
        # ❌ 不传递 message_history，无返回 session_id
        return AgentResult(data=str(result.data), metadata={"trace_id": trace.trace_id})
```

#### TraceID（trace.py:1-29）
```python
@dataclass
class TraceID:
    trace_id: str  # 每次生成新 UUID (无会话续接）
    span_id: str
    parent_id: str | None = None
    path: list[str]

    @classmethod
    def new(cls):  # ❌ 无 root_trace_id 参数
        return cls(trace_id=str(uuid.uuid4()), span_id=str(uuid.uuid4()), ...)
```

#### RuntimeDeps（runtime.py:22-32）
```python
@dataclass
class RuntimeDeps:
    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol

    def child(self, target):
        return RuntimeDeps(flow=self.flow, trace=self.trace.child(target), factory=self.factory)
        # ❌ 无 message_history, session_id 字段
```

### 1.2 CrewAI 路径 - 部分会话管理

#### SimulationState（crewai/core/state.py:17-30）
```python
class SimulationState(BaseModel):
    id: str = "xeno_simulation_state"
    stack: list[TaskFrame] = Field(default_factory=list)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)  # ✅ 历史列表
    final_output: str | None = None
    is_terminated: bool = False
    auto_approve: bool = False
    last_signal: Any = None

class TaskFrame(BaseModel):
    mode_slug: str
    task_id: str
    trigger_message: str
    caller_mode: str | None = None
    is_isolated: bool = False  # ✅ 支持 history 隔离
    result: str | None = None
```

#### Flow 历史管理（flow.py:73, 152, 171-172, 227, 252-253）
```python
# 构建上下文字符串（从历史）
context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.state.conversation_history])

# 任务构建
task = Task(
    description=current_frame.trigger_message + (f"\n\nContext:\n{context}" if context else ""),
    ...
)

# 添加助手响应
self.state.conversation_history.append({"role": "assistant", "content": last_signal.result})

# 重置时清空历史
self.state.conversation_history = []
```

### 1.3 现有协议 - StatePersistence（未实现）

#### 接口定义（interfaces.py:24-30）
```python
@runtime_checkable
class StatePersistence(Protocol):
    async def save_state(self, session_id: str, state: dict[str, Any]) -> None: ...
    async def load_state(self, session_id: str) -> dict[str, Any] | None: ...
```

#### 发现
- ✅ 协议已定义
- ❌ **零实现**（无 Redis、文件、内存存储等）
- ❌ pyproject.toml 无 persistence 依赖

## 二、核心问题分析

### 问题 1：状态每次 invoke 都会新建
| 组件 | 当前行为 | 需要 |
|------|---------|------|
| `invoke()` | 新建 TraceID、RuntimeDeps | 支持 session_id 参数 |
| 内存 | 无 _active_sessions 字典 | 维护活跃会话字典 |
| 返回值 | 只返回 trace_id | 返回 session_id |
| 历史管理 | 无 message_history 字段 | 添加并传递历史 |

### 问题 2：无跨 session/turn 的 message_history
| 层次 | 当前状态 | PydanticAI API 支持 |
|------|---------|------------------|
| RuntimeDeps | 无 message_history 字段 | ✅ 支持 `agent.run(message_history=...)` |
| delegate_task | 不传递 message_history | ✅ 支持 |
| invoke() | 不传递 message_history | ✅ 支持 |
| 结果处理 | 不提取 `all_messages()` | ✅ 可用 |

### 问题 3： delegate_task 未正确传递历史
```python
# 当前实现（不正确）
result = await agent.run(task, deps=new_deps, usage=ctx.usage)
# 返回前不更新 message_history，deps 和 new_deps 历史不同步

# 需要的行为
result = await agent.run(task, deps=new_deps, usage=ctx.usage, message_history=new_deps.message_history)
all_messages = result.all_messages()
new_messages = all_messages[len(new_deps.message_history):]
new_deps.message_history.extend(new_messages)
deps.message_history = new_deps.message_history  # 同步回父
```

## 三、PydanticAI Message History API（官方文档摘要）

基于 RFC 005 文档和官方文档研究：

### 1. 基础用法
```python
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessagesTypeAdapter

# 首次调用（无历史）
agent = Agent('openai:gpt-4o')
result1 = await agent.run("Hello")

# 序列化历史（如需持久化）
serialized = ModelMessagesTypeAdapter.dump_json(result1.all_messages())

# 次次调用（传入历史）
history = ModelMessagesTypeAdapter.validate_json(serialized)
result2 = await agent.run(
    "What's your name?",
    message_history=history  # 关键参数
)
```

### 2. result.all_messages() 方法
- 返回：`list[ModelMessage]` （包含传入的历史 + 新生成）
- 类型：PydanticAI 的内部 `ModelMessage` 对象
- 用法：提取全部对话历史

### 3. 追踪新增消息
```python
old_count = len(existing_history)
result = await agent.run(prompt, message_history=existing_history)
all_messages = result.all_messages()
new_messages = all_messages[old_count:]  # 仅新增部分
```

### 4. RuntimeDeps.child() 期望行为
```python
@dataclass
class RuntimeDeps:
    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol
    message_history: list[ModelMessage] = field(default_factory=list)  # 新增
    session_id: str | None = None  # 新增

    def child(self, target: str):
        return RuntimeDeps(
            flow=self.flow,
            trace=self.trace.child(target),  # 新 span，同 trace
            factory=self.factory,
            session_id=self.session_id,  # 同一会话
            message_history=self.message_history,  # 引用同一列表
        )
```

## 四、测试模式分析（test_runtime.py:1-125）

### 4.1 MockDeps（可复用模式）
```python
class MockDeps:
    def __init__(self, flow=None, trace=None, factory=None):
        self.flow = flow or FlowConfig(...)
        self.trace = trace or TraceID.new()
        self.factory = factory

    def child(self, target):
        return MockDeps(flow=self.flow, trace=self.trace.child(target), factory=self.factory)
```

### 4.2 现有测试覆盖
- ✅ 权限拒绝（`test_delegate_task_permission_denied()`）
- ✅ 循环检测（`test_delegate_task_cycle_detection()`）
- ✅ 深度限制（`test_delegate_task_max_depth_exceeded()`）
- ✅ 成功调用（`test_delegate_task_success()`）
- ❌ **未测试**：多轮对话、session 复用、history 累加

### 4.3 Mock Agent 模式
```python
mock_agent = AsyncMock()
result_mock = MagicMock()
result_mock.data = "Success"
mock_agent.run.return_value = result_mock

mock_factory = MagicMock()
mock_factory.create.return_value = mock_agent

# 测试权限
with pytest.raises(PermissionError, match="Delegation from agent_a to agent_c not allowed"):
    await delegate_task(ctx, "agent_c", "task")
```

## 五、外部框架最佳实践对比（初步）

### 5.1 LangGraph Checkpointers
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import AsyncPostgresSaver

# 开发环境
checkpointer = InMemorySaver()

# 生产环境
checkpointer = AsyncPostgresSaver.from_conn_string("postgresql+asyncpg://...")
await checkpointer.setup()

# 编译图
app = workflow.compile(checkpointer=checkpointer)

# 使用 thread_id
config = {"configurable": {"thread_id": "user-123"}}
result1 = await app.ainvoke({"messages": ["Hello"]}, config=config)
result2 = await app.ainvoke({"messages": ["Continue"]}, config=config)
```

**关键点**：
- `thread_id` 作为会话标识
- Checkpointer 自动保存状态每次 invoke
- 同一 thread_id → 历史累加，不同 thread_id → 新会话

### 5.2 LangGraph State 管理
```python
class AgentState(TypedDict):
    messages: list
    user_id: str
    counter: int

# Checkpointer 自动持久化完整 `AgentState` 对象
# 支持跨多次 `ainvoke` 调用的状态坚持
```

**关键点**：
- 完整个对象持久化（不是部分字段）
- 字类型安全
- 支持自定义字段（user_id, counter 等）

### 5.3 对比结论

| 特性 | LangGraph | 当前 PydanticAI 本次改动 |
|------|----------|-------------------------|
| 会话 ID | thread_id（手动传递） | session_id（参数支持） |
| 状态存储 | Checkpointer（自动）| _active_sessions（手动） |
| 历史管理 | State.messages（完整对象）| message_history（ModelMessage 列表） |
| API 风格 | 都有 aync 方法 | Target `message_history` 参数 |
| 序列化 | 自动（通过 Checkpointer）| 手动（需要时） |
| 复杂度 | Checkpointer 抽象 | 简单的字典 |
| 过程 | SQL/Redis/内存 | 仅内存（暂时） |

## 六、推荐实现方案（最小改动）

### 6.1 TraceID.new() 支持 root_trace_id
```python
# trace.py
@dataclass
class TraceID:
    trace_id: str
    span_id: str
    parent_id: Optional[str] = None
    path: list[str] = field(default_factory=list)

    @classmethod
    def new(cls, root_trace_id: Optional[str] = None) -> "TraceID":
        """创建新 trace

        Args:
            root_trace_id:（可选）根 trace_id，用于会话续接
        """
        return cls(
            trace_id=root_trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_id=None,
            path=[]
        )
```

### 6.2 RuntimeDeps 扩展
```python
# runtime.py
from pydantic_ai.messages import ModelMessage
from typing import Optional

@dataclass
class RuntimeDeps:
    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol
    # 新增 1：消息历史列表
    message_history: list[ModelMessage] = field(default_factory=list)
    # 新增 2：会话标识
    session_id: Optional[str] = None

    def child(self, target: str):
        return RuntimeDeps(
            flow=self.flow,
            trace=self.trace.child(target),
            factory=self.factory,
            session_id=self.session_id,  # 同一会话
            message_history=self.message_history,  # 引用同一列表
        )
```

### 6.3 LocalAgentRuntime 会话管理
```python
# runtime.py
class LocalAgentRuntime(AgentRuntime):
    def __init__(self, factory, flow_config):
        self.factory = factory
        self.flow_config = flow_config
        # 新增：活跃会话字典（内存）
        self._active_sessions: dict[str, RuntimeDeps] = {}

    async def invoke(
        self,
        agent_id: str,
        message: str,
        # 新增参数：会话 ID
        session_id: str | None = None,
        **kwargs
    ):
        # 1. 获取或创建 RuntimeDeps
        if session_id and session_id in self._active_sessions:
            # 续接现有会话
            deps = self._active_sessions[session_id]
            # 更新 trace（新 span，同 session）
            trace = deps.trace.child(agent_id)
            deps.trace = trace
        else:
            # 新建会话
            trace = TraceID.new().child(agent_id)
            deps = RuntimeDeps(
                flow=self.flow_config,
                trace=trace,
                factory=self.factory,
                message_history=[],  # 清空历史
                session_id=trace.trace_id,  # 用 trace_id 作为 session_id
            )
            # 存储到活跃会话
            self._active_sessions[deps.session_id] = deps

        # 2. 加载并执行 agent（传递历史）
        agent = await self.factory.create(agent_id, self.flow_config)

        async with agent.run_mcp_servers(model=agent.model):
            result = await agent.run(
                message,
                deps=deps,
                message_history=deps.message_history  # 关键：传入历史
            )

        # 3. 更新历史（追加新消息）
        all_messages = result.all_messages()
        new_messages = all_messages[len(deps.message_history):]
        deps.message_history.extend(new_messages)

        # 4. 返回结果（包含 session_id）
        return AgentResult(
            data=str(result.data),
            metadata={
                "session_id": deps.session_id,  # 新增
                "trace_id": deps.trace_id,
                "span_id": deps.trace.span_id,
                "usage": result.usage(),
                "message_count": len(deps.message_history),  # 新增
                "new_messages": len(new_messages),  # 新增
            }
        )
```

### 6.4 delegate_task 传递和合并历史
```python
# runtime.py
async def delegate_task(ctx, target_agent: str, task: str) -> str:
    deps = ctx.deps

    # 1. 安全检查（现有逻辑，不变）
    ...

    # 2. 创建子 deps
    new_deps = deps.child(target_agent)  # 已包含 message_history 和 session_id
    agent = await deps.factory.create(target_agent, deps.flow)

    # 3. 执行（传递历史）
    async with agent.run_mcp_servers(model=agent.model):
        result = await agent.run(
            task,
            deps=new_deps,
            usage=ctx.usage,
            message_history=new_deps.message_history  # 新增
        )

    # 4. 更新历史（追加新消息）
    all_messages = result.all_messages()
    new_messages = all_messages[len(new_deps.message_history):]
    new_deps.message_history.extend(new_messages)

    # 回写到父 deps
    deps.message_history = new_deps.message_history

    return str(result.data)
```

## 七、向后兼容性

| 接口/方法 | 兼容性 | 说明
|-----------|--------|------|
| `invoke(agent_id, message, **kwargs)` | ✅ 完全 | 新增可选 session_id 参数，不传时行为不变 |
| `AgentResult` | ✅ 元数据扩展 | 新增 session_id, message_count，现有代码应忽略 |
| `RuntimeDeps` | ⚠️ 新字段 | 旧代码不传递历史字段时，使用默认值（None, []） |
| `TraceID.new()` | ✅ 可选参数 | 不传 root_trace_id 时行为不变 |
| `delegate_task()` | ⚠️ 内部逻辑 | 签名不变，仅增强内部实现 |

## 八、潜在风险与缓解

### 风险 1：内存泄漏
**问题**：`_active_sessions` 字典无限增长
**当前处理**：暂不处理（用户单次周期重启）

**后续缓解**：
```python
async def cleanup_inactive_sessions(self, ttl_seconds=86400):
    """清理过期会话"""
    import time
    now = time.time()
    to_delete = [
        sid for sid, deps in self._active_sessions.items()
        if now - deps.last_updated > ttl_seconds  # 需要添加时间戳
    ]
    for sid in to_delete:
        del self._active_sessions[sid]
```

### 风险 2：线程安全
**问题**：并发调用相同的 session_id
**当前处理**：未加锁（假设单线程/事件循环）

**缓解**（如需并发）：
```python
from asyncio import Lock

class LocalAgentRuntime:
    def __init__(self, ...):
        self._sessions_lock = Lock()
        self._active_sessions = {}

    async def invoke(self, ...):
        async with self._sessions_lock:
            # 访问 _active_sessions
            deps = self._active_sessions.get(session_id) or create_new_deps()
```

### 风险 3：消息过多
**问题**：单次 session 历史过长
**当前处理**：不限制长度（依赖 Agent 自身的 token 限制）

**后续缓解**：
```python
def child(self, target: str):
    # 复制历史副本，实现裁剪
    truncated_history = self.message_history[-100:] if len(self.message_history) > 100 else self.message_history
    return RuntimeDeps(..., message_history=truncated_history)
```

## 九、测试策略

### 9.1 单元测试（基于 test_runtime.py 模式）
```python
# test_multi_turn.py

@pytest.mark.asyncio
async def test_single_invocation_creates_session():
    """单次调用自动创建新会话"""
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=mock_flow)
    result = await runtime.invoke("test_agent", "Hello")

    assert result.metadata["session_id"] is not None
    assert result.metadata["message_count"] == 1

@pytest.mark.asyncio
async def test_multi_turn_with_session_id():
    """使用相同 session_id 累加历史"""
    runtime = LocalAgentRuntime(factory=mock_factory, flow_config=mock_flow)

    # Turn 1
    r1 = await runtime.invoke("test_agent", "First")
    session_id = r1.metadata["session_id"]
    count1 = r1.metadata["message_count"]

    # Turn 2
    r2 = await runtime.invoke("test_agent", "Second", session_id=session_id)
    count2 = r2.metadata["message_count"]

    # 验证
    assert r2.metadata["session_id"] == session_id
    assert count2 >= count1

@pytest.mark.asyncio
async def test_delegate_preserves_history():
    """delegation 调用看到完整历史"""
    # 设置：第一次调用已产生消息
    result = await mock_runtime.invoke("parent_agent", "Initial")
    session_id = result.metadata["session_id"]
    initial_count = result.metadata["message_count"]

    # 第二次调用（触发 delegate）
    result2 = await mock_runtime.invoke(
        "parent_agent",
        "Delegate to child",
        session_id=session_id
    )

    # 验证 delegate 后历史保持
    final_count = result2.metadata["message_count"]
    assert final_count >= initial_count

def test_trace_id_continuity():
    """TraceID.new() 支持 root_trace_id"""
    trace1 = TraceID.new()
    trace2 = TraceID.new(root_trace_id=trace1.trace_id)

    assert trace2.trace_id == trace1.trace_id
    assert trace2.span_id != trace1.span_id
```

### 9.2 集成测试（端到端）
```python
# test_e2e.py
async def test_e2e_multi_turn():
    runtime = LocalAgentRuntime(factory, flow_config)

    # Turn 1
    r1 = await runtime.invoke("qa_assistant", "服务器红灯")
    sid = r1.metadata["session_id"]

    # Turn 2
    r2 = await runtime.invoke("error_expert", "分析原因", session_id=sid)

    # Turn 3
    r3 = await runtime.invoke("equipment_expert", "操作步骤", session_id=sid)

    # 验证 session 一致性和历史累加
    assert r1.metadata["session_id"] == sid
    assert r2.metadata["session_id"] == sid
    assert r3.metadata["session_id"] == sid
    assert r3.metadata["message_count"] >= r2.metadata["message_count"]
```

## 十、与 CrewAI 的设计差异

| 特性 | CrewAI 路径 | PydanticAI 路径（本次改动后） |
|------|------------|---------------------------|
| 状态模型 | SimulationState（独立类） | RuntimeDeps（注入 deps）|
| 调用栈 | TaskFrame 列表追踪 | TraceID.path（路径字符串）|
| 消息格式 | {"role": ..., "content": ...} dict | ModelMessage（PydanticAI 类型）|
| StatePersistence | 不支持（全内存） | 协议已定义，后续可实现 |
| isolation 支持 | 有（is_isolated 字段）| 需要扩展 RuntimeDeps（后续）|
| 历史管理 | ConversationHistory 列表 | message_history (ModelMessage 列表）|
| 会话 ID | 无 | session_id (字符串）|
| 多轮支持 | Flow 层面完整 | Runtime 层面新增 |

## 十一、实施顺序

1. **Phase 1**: TraceID 改动（5-10 分钟）
   - 文件：`trace.py`
   - 改动：`new(cls)` 方法签名

2. **Phase 2**: RuntimeDeps 改动（10-15 分钟）
   - 文件：`runtime.py`
   - 改动：dataclass 字段、child() 方法

3. **Phase 3**: LocalAgentRuntime 改动（30-40 分钟）
   - 文件：`runtime.py`
   - 改动：`__init__()`, invoke() 核心逻辑

4. **Phase 4**: delegate_task 改动（20-30 分钟）
   - 文件：`runtime.py`
   - 改动：消息历史传递、更新逻辑

5. **Phase 5**: 测试编写（30-40 分钟）
   - 单元测试：`tests/test_pydantic_ai_sdk/test_multi_turn.py`
   - 集成测试：`tests/test_multi_turn_e2e.py`
   - 使用 MockDeps 模式

**总计预计**：2-3 小时（编码+测试）
