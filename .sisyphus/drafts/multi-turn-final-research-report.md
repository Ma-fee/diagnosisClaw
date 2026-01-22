# Multi-Turn 与 Multi-Agent 支持完整研究报告

---

## 执行摘要

**7 个并行研究任务全部完成**：
- ✅ 会话/状态模式分析（2m 37s）
- ✅ 消息流与执行模式分析（3m 8s）
- ✅ 测试模式分析（2m 45s）
- ✅ Agent 层次与 Delegation 映射（4m 11s）
- ✅ PydanticAI 多轮对话文档研究（3m 54s）
- ✅ Multi-Agent 框架对比（4m 59s）
- ✅ GitHub 生产级 Agent 会话模式搜索（4m 10s）

**总研究时长**:约 25-30 分钟
**覆盖范围**：代码库深度分析 + 官方文档 + 外部框架 + 生产模式 + 测试基础设施

---

## 一、PydanticAI Pathway - 无会话管理

### 现状问题

| 组件 | 当前实现 | 缺失 |
|------|---------|------|
| `TraceID.new()` | 每次新建 trace_id（UUID） | 不支持 root_trace_id 参数用于会话续接 |
| `RuntimeDeps` | 仅 flow, trace, factory | 无 message_history, session_id 字段 |
| `LocalAgentRuntime` | invoke() 无 session_id | 无 _active_sessions 字典，每次创建新 deps |
| `result.all_messages()` | ✅ 方法存在 | 未被外部代码调用 |

### 当前代码示例

```python
# trace.py - 不支持会话续接
@classmethod
def new(cls):  # ❌ 无参数
    return cls(trace_id=str(uuid.uuid4()), ...)

# runtime.py - 每次重新开始
async def invoke(self, agent_id: str, message: str, **kwargs):
    deps = RuntimeDeps(...)  # ❌ 新建 deps
    result = await agent.run(message, deps=deps)  # ❌ 无 message_history
    return AgentResult(data=..., metadata={"trace_id": ...})  # ❌ 无 session_id
```

### 交互式 CLI 问题
```python
# main.py:58-70
while True:
    user_input = input("User: ")
    result = await runtime.invoke(entry_agent, user_input)  # ❌ 无历史
    # 每次都是全新开始，无法记忆之前的对话
```

---

## 二、CrewAI Pathway - 部分会话管理

### 现有实现（已验证）

#### 1. 状态模型（state.py:17-30）
```python
class SimulationState(BaseModel):
    """完整会话状态"""
    id: str = "xeno_simulation_state"
    stack: list[TaskFrame] = Field(default_factory=list)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)  # ✅ 历史列表
    final_output: str | None = None
    is_terminated: bool = False
    auto_approve: bool = False
    last_signal: Any = None
```

#### 2. 历史管理（flow.py）
```python
# 构建上下文（从历史）
context = "\n".join([
    f"{msg['role']}: {msg['content']}"
    for msg in self.state.conversation_history
])

# 添加助手响应
self.state.conversation_history.append({
    "role": "assistant",
    "content": last_signal.result
})

# 重置历史
self.state.conversation_history = []
```

### 问题
- ❌ 仅在信号事件时追加（正常响应不捕获）
- ❌ 无 session_id（仅内部状态）
- ❌ 无持久化协议（进程重启即丢失）
- ✅ 有调用栈（TaskFrame）

---

## 三、State Persistence 协议（定义但未实现）

```python
# interfaces.py:25-30
@runtime_checkable
class StatePersistence(Protocol):
    async def save_state(self, session_id: str, state: dict[str, Any]) -> None: ...
    async def load_state(self, session_id: str) -> dict[str, Any] | None: ...
```

**调查结果**：
- ✅ 协议已定义
- ❌ 零实现（无 Redis, DB, 文件存储）
- ❌ pyproject.toml 无 persistence 依赖
- ❌ config/ 无 TTL 或存储配置

---

## 四、PydanticAI 官方 API（完整）

### 1. Message History 参数
```python
from pydantic_ai import Agent, ModelMessagesTypeAdapter

agent = Agent('openai:gpt-4o')

# 首次调用（无历史）
result1 = await agent.run("Hello")
serialized = ModelMessagesTypeAdapter.dump_json(result1.all_messages())

# 次次调用（传入历史）
history = ModelMessagesTypeAdapter.validate_json(serialized)
result2 = await agent.run(
    "What's your name?",
    message_history=history  # ✅ 官方支持
)
```

### 2. 结果 API
```python
# 获取全部消息（包含历史）
all_messages = result.all_messages()  # 返回 list[ModelMessage]

# 追踪本次新增
old_len = len(existing_history)
new_messages = all_messages[old_len:]  # ✅ 增量部分
```

### 3. 序列化工具
```python
# 序列化
json_bytes = ModelMessagesTypeAdapter.dump_json(messages)

# 反序列化
messages = ModelMessagesTypeAdapter.validate_json(json_bytes)
```

### 关键点
- `ModelMessage` 是 PydanticAI 内部类型（不是 dict）
- `message_history` 参数接受 `list[ModelMessage]`
- `all_messages()` 返回本次调用的完整消息序列（历史 + 新生成）

---

## 五、LangGraph 会话管理模式（生产级参考）

### 核心设计
```
┌─────────────────────────────────────────┐
│  LangGraph Checkpointer 架构          │
├─────────────────────────────────────────┤
│                                    │
│  thread_id ─────→ Checkpointer ──→Saved State
│  (会话标识)    (抽象接口）         (持久化）
│                        │                 │
│                        ├─→ InMemorySaver
│                        ├─→ SQLiteSaver
│                        ├─→ RedisSaver
│                        └─→ PostgreSQLSaver
```

### 实现模式

#### 1. InMemorySaver（开发环境）
```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
# 内存字典：{thread_id: State}
```

#### 2. RedisSaver（生产推荐）
```python
from langgraph.checkpoint.redis import RedisConfig, RedisSaver
import redis.asyncio as aioredis

config = RedisConfig(
    redis=aioredis.from_url("redis://localhost:6379/0"),
    checkpointer_ttl=86400,  # 24小时 TTL
    grace_period=300,  # 缓冲期
)
checkpointer = RedisSaver(config)
```

#### 3. PostgreSQLSaver（生产可选）
```python
from langgraph.checkpoint.postgres import AsyncPostgresSaver

checkpointer = AsyncPostgresSaver.from_conn_string(
    "postgresql+asyncpg://user:pass@localhost/mydb"
)
await checkpointer.setup()  # 创建表
```

### 使用模式
```python
from langgraph.graph import StateGraph
from typing import Annotated, TypedDict

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # ✅ 自动管理

workflow = StateGraph(AgentState)
app = workflow.compile(checkpointer=checkpointer)

# 会话 1
config = {"configurable": {"thread_id": "user-123"}}
result1 = await app.ainvoke({"messages": ["Hello"]}, config=config)

# 会话 2（同一 thread_id）
result2 = await app.ainvoke({"messages": ["Continue"]}, config=config)
  # ✅ 保持 messages 状态
```

### 关键设计点
1. **thread_id** 作为会话标识（类似我们的 session_id）
2. **State 对象**（而非字典）- 类型的状态
3. **add_messages** reducer - 消息自动追加
4. **Checkpointer 抽象** - 支持多种存储后端
5. **TTL 自动清理** - RedisSaver 自动过期

---

## 六、CrewAI vs PydanticAI 对比

| 特性 | CrewAI | PydanticAI (本次改动后) |
|------|--------|------------------------|
| 状态模型 | SimulationState（Pydantic) | RuntimeDeps (注入 deps) |
| 调用栈 | TaskFrame 列表 | TraceID.path (路径字符串) |
| 消息格式 | {"role": str, "content": str} dict | ModelMessage (PydanticAI 类型) |
| 状态位置 | Flow 内部 self.state | RuntimeDeps (依赖注入) |
| Delegation 栈 | stack 列表 | trace.path |
| 消息管理 | conversation_history.append() | message_history.extend() |
| 隔离支持 | is_isolated 标志 | 需要扩展（后续） |
| Session ID | 无 | session_id (字符串) |
| 持久化协议 | 不支持 | StatePersistence (可扩展) |

---

## 七、测试模式分析（现有基础设施）

### 1. MockDeps 模式（test_runtime.py:12-27）

```python
class MockDeps:
    """可复用的依赖模拟"""
    def __init__(self, flow=None, trace=None, factory=None):
        self.flow = flow or FlowConfig(...)
        self.trace = trace or TraceID.new()
        self.factory = factory
    
    def child(self, target):
        return MockDeps(...)
```

**关键特征**：
- 兼容 `RuntimeDeps` 结构
- 支持 `child()` 方法创建层级
- 用于所有权限、循环检测、深度限制测试

### 2. Mock Agent 模式
```python
mock_agent = AsyncMock()
result_mock = MagicMock()
result_mock.data = "Success"
mock_agent.run.return_value = result_mock  # ✅ PydanticAI 接口
```

### 3. 测试覆盖
```python
# ✅ 权限拒绝（test_delegate_task_permission_denied）
# ✅ 循环检测（test_delegate_task_cycle_detection）
# ✅ 深度限制（test_delegate_task_max_depth_exceeded）
# ✅ 成功调用（test_delegate_task_success）
# ❌ 未测试：多轮对话、session 复用、history 追踪
```

### 4. Async 测试模式
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

---

## 八、关键发现汇总

### 问题清单

| # | 问题 | 影响 | 优先级 |
|---|------|------|--------|
| 1 | PydanticAI 交互模式每次新建对象 | 无法多轮对话 | 🔴 高 |
| 2 | RuntimeDeps 缺少历史字段 | 无法传递 conversation | 🔴 高 |
| 3 | TraceID 不支持会话续接 | 无法关联 turns | 🔴 高 |
| 4 | StatePersistence 未实现 | 无法持久化 | 🟡 中 |
| 5 | CrewAI 历史不完整 | 遗漏正常响应 | 🟡 低 |
| 6 | 无测试验证多轮 | 潜在回归 | 🟡 中 |

### 技术痛点

1. **状态隔离** - 不同实现路径状态不连通
2. **消息格式不统一** - dict vs ModelMessage
3. **无清理机制** - 内存会话无限增长
4. **并发未考虑** - 同 session_id 并发调用

---

## 九、推荐实现方案（最小改动）

### 改动概述

| 组件 | 改动类型 | 复杂度 | 时间 |
|------|---------|--------|------|
| `TraceID.new()` | 签名扩展 | ⭐ 低 | 5分钟 |
| `RuntimeDeps` | 字段扩展 | ⭐⭐ 低 | 10分钟 |
| `LocalAgentRuntime.invoke()` | 核心逻辑 | ⭐⭐⭐⭐ 高 | 40分钟 |
| `delegate_task()` | 内部增强 | ⭐⭐ 中 | 20分钟 |
| 测试 | 新增文件 | ⭐⭐⭐ 中 | 30分钟 |

**总计**：约 1.5-2 小时

---

### 详细设计

#### 1. TraceID 支持 root_trace_id
```python
# trace.py
@classmethod
def new(cls, root_trace_id: Optional[str] = None) -> "TraceID":
    """创建新 trace（支持会话续接）"""
    return cls(
        trace_id=root_trace_id or str(uuid.uuid4()),
        span_id=str(uuid.uuid4()),
        parent_id=None,
        path=[]
    )
```

#### 2. RuntimeDeps 扩展
```python
# runtime.py
@dataclass
class RuntimeDeps:
    flow: FlowConfig
    trace: TraceID
    factory: AgentFactoryProtocol
    # 新增：消息历史（ModelMessage 类型）
    message_history: list[_messages.ModelMessage] = field(default_factory=list)
    # 新增：会话标识
    session_id: Optional[str] = None

    def child(self, target: str) -> "RuntimeDeps":
        return RuntimeDeps(
            flow=self.flow,
            trace=self.trace.child(target),
            factory=self.factory,
            session_id=self.session_id,  # ✅ 继承 session
            message_history=self.message_history,  # ✅ 引用同一列表
        )
```

#### 3. LocalAgentRuntime 会话管理
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
        # === 1. 获取或创建 RuntimeDeps ===
        if session_id and session_id in self._active_sessions:
            # 续接现有会话
            deps = self._active_sessions[session_id]
            trace = deps.trace.child(agent_id)  # 新 span，同 session
            deps.trace = trace
        else:
            # 新建会话
            trace = TraceID.new().child(agent_id)
            deps = RuntimeDeps(
                flow=self.flow_config,
                trace=trace,
                factory=self.factory,
                message_history=[],
                session_id=trace.trace_id,  # 用 trace_id 作为 session
            )
            self._active_sessions[deps.session_id] = deps

        # === 2. 执行 agent（传递历史）===
        agent = await self.factory.create(agent_id, self.flow_config)
        async with agent.run_mcp_servers(model=agent.model):
            result = await agent.run(
                message,
                deps=deps,
                message_history=deps.message_history  # ✅ 关键
            )

        # === 3. 更新历史的消息 ===
        all_messages = result.all_messages()
        new_messages = all_messages[len(deps.message_history):]
        deps.message_history.extend(new_messages)

        # === 4. 返回结果（包含 session_id）===
        return AgentResult(
            data=str(result.data),
            metadata={
                "session_id": deps.session_id,  # ✅ 新增
                "trace_id": deps.trace_id,
                "span_id": deps.trace.span_id,
                "usage": result.usage(),
                "message_count": len(deps.message_history),
                "new_messages": len(new_messages),
            }
        )
```

#### 4. delegate_task 传递历史
```python
# runtime.py
async def delegate_task(ctx, target_agent: str, task: str) -> str:
    deps = ctx.deps

    # 1. 安全区检查（现有逻辑，不变）
    ...

    # 2. 创建子 deps（已继承 message_history）
    new_deps = deps.child(target_agent)
    agent = await deps.factory.create(target_agent, deps.flow)

    # 3. 执行（传递历史）
    async with agent.run_mcp_servers(model=agent.model):
        result = await agent.run(
            task,
            deps=new_deps,
            usage=ctx.usage,
            message_history=new_deps.message_history  # ✅ 新增
        )

    # 4. 更新历史
    all_messages = result.all_messages()
    new_messages = all_messages[len(new_deps.message_history):]
    new_deps.message_history.extend(new_messages)
    deps.message_history = new_deps.message_history  # 同步回父

    return str(result.data)
```

#### 5. 测试策略
```python
# test_pydantic_ai_sdk/test_multi_turn.py

@pytest.mark.asyncio
async def test_single_invocation_creates_session():
    rt = LocalAgentRuntime(..., ...)
    result = await rt.invoke("agent", "Hello")

    assert result.metadata["session_id"] is not None
    assert result.metadata["message_count"] == 1

@pytest.mark.asyncio
async def test_multi_turn_with_session_id():
    rt = LocalAgentRuntime(..., ...)

    r1 = await rt.invoke("agent", "First")
    sid = r1.metadata["session_id"]
    count1 = r1.metadata["message_count"]

    r2 = await rt.invoke("agent", "Second", session_id=sid)

    assert r2.metadata["session_id"] == sid
    assert r2.metadata["message_count"] >= count1
    assert len(rt._active_sessions) == 1  # 仅一个会话

@pytest.mark.asyncio
async def test_delegate_preserves_history():
    # 设置初始消息
    result = await rt.invoke("parent", "Initial")
    sid = result.metadata["session_id"]
    initial = result.metadata["message_count"]

    # 触发 delegate 活动
    result2 = await rt.invoke(
        "parent",
        "Delegate to child",
        session_id=sid
    )

    assert result2.metadata["message_count"] >= initial
```

---

## 十、向后兼容性分析

### API 兼容性
| 接口/方法 | 兼容性 | 变化说明 |
|-----------|--------|---------|
| `invoke(agent_id, message, **kwargs)` | ✅ 完全 | 新增可选 `session_id`，忽略时行为不变 |
| `AgentResult` | ✅ 元数据扩展 | 新增字段，现有代码自动忽略 |
| TraceID.new() | ✅ 完全 | 新增可选参数，不传时行为不变 |
| RuntimeDeps | ⚠️ 字段添加 | 旧未传递字段时使用默认值 |
| delegate_task() | ✅ 内部逻辑 | 签名不变，增强实现 |

### 破坏场景风险
**低风险场景**：
- 现有单个 `invoke()` 调用 → 行为完全不变
- 不使用返回的 metadata → 无影响

**需要注意**：
- 现有测试使用 MockDeps → 如不传递新字段，仍通过（使用默认值）

### 迁移路径
```
现有代码 → 无需改动
├─ 单次调用 → 继续
└─ 使用原始模式 → 继续

新增多轮对话 → 使用新功能
├─ 调用方保存 session_id
├─ 下次调用传入 session_id
└─ 立即启用多轮支持
```

---

## 十一、外部框架最佳实践总结

### 1. LangGraph 模式
| 模式 | 说明 | 适用性 |
|------|------|--------|
| **thread_id** | 会话标识（类似我们的 session_id） | ✅ 采纳 |
| **Checkpointer 抽象** | 存储与执行分离 | ⚠️ 暂不（先内存） |
| **State 对象** | 类型化状态 | ⚠️ 暂不（使用数据类） |
| **TTL 自动清理** | Redis 自动过期 | ✅ 应该借鉴（后续） |
| **add_messages** | 自动 reducer | ❌ 不适用（手动 extend） |

### 2. LobeHub LobeChat 模式
```typescript
// 状态管理器模式
interface IAgentStateManager {
  getOrCreateSession(id: string): Promise<AgentSession>;
  updateSession(id: string, updates: Partial<AgentSession>): Promise<void>;
  cleanupInactiveSessions(ttl: number): Promise<number>;
}

class InMemoryAgentStateManager implements IAgentStateManager {
  private sessions: Map<string, AgentSession> = new Map();
}
```

**可借鉴**：显式 `cleanup_inactive_sessions()` 方法

### 3. CrewAI Flow 模式
```python
# 调用栈 CALL-RETURN 模式
state.stack.append(TaskFrame(...))     # PUSH
state.stack.pop()                     # POP
current = state.stack[-1]                # GET TOP
```

**我们的实现**：使用 `TraceID.path` (字符串路径)替代栈对象

### 4. 生产级会话生命周期
```
创建 → Active (1st invoke)
      ↓
Active → Updates (subsequent invokes)
      ↓
Inactive → Cleanup (TTL expires)
      ↓
Cleanup → Deleted (remove from dict)
```

---

## 十二、风险与缓解

### 风险 1：内存泄漏
**问题**：`_active_sessions` 无限增长

**缓解（当前不实施，可后续添加）**：
```python
async def cleanup_inactive_sessions(self, ttl_seconds=86400):
    """清理 24 小时未活跃会话"""
    # 方案 1：添加 last_updated 字段
    # 方案 2：定期任务清理
    pass
```

### 风险 2：并发安全
**问题**：同一 session_id 并发调用

**缓解（当前场景不触发）**：
- 假设单线程/事件循环
- 如需并发：`asyncio.Lock` 保护 `_active_sessions`

### 风险 3：消息过多
**问题**：单个 session 历史过长

**缓解（当前依赖 Agent 限制）**：
- PydanticAI agent.run() 内部有 token 限制
- 长历史自动被截断
- 当前无需手动裁剪

---

## 十三、实施顺序与里程碑

### 阶段 1：基础架构（0.5h）
- [ ] TraceID.new() 添加 root_trace_id 参数
- [ ] RuntimeDeps 添加 message_history, session_id
- [ ] RuntimeDeps.child() 继承新字段

### 阶段 2：Runtime 实现（1.0h）
- [ ] LocalAgentRuntime 添加 _active_sessions
- [ ] invoke() 支持 session_id 参数
- [ ] invoke() 逻辑：获取/创建/更新 deps
- [ ] invoke() 执行：传递 message_history
- [ ] invoke() 返回：添加 session_id 到 metadata

### 阶段 3：Delegation 增强（0.5h）
- [ ] delegate_task() 传递 message_history
- [ ] delegate_task() 更新历史并同步
- [ ] 日志输出：显示 session_id, message_count

### 阶段 4：测试（0.5h）
- [ ] test_trace_id_continuity()
- [ ] test_runtime_deps_child_inherits_session()
- [ ] test_single_invocation_creates_session()
- [ ] test_multi_turn_with_session_id()
- [ ] test_delegate_preserves_history()
- [ ] MockDeps 扩展（如需）

### 阶段 5：验证（0.2h）
- [ ] 手动测试：端到端多轮对话
- [ ] 确认向后兼容
- [ ] 性能测试（可选）

---

## 十四、成功标准

### 功能验收
- [ ] 首次 invoke 创建新会话，返回 session_id
- [ ] 使用相同 session_id 复用会话
- [ ] 相同 session 的 message_count 累加
- [ ] delegate 调用能看到完整历史
- [ ] 不传 session_id 时行为与之前一致

### 非功能要求
- [ ] 无外部依赖（Redis, DB）
- [ ] 代码风格与现有一致
- [ ] 所有现有测试通过
- [ ] 新增测试覆盖核心场景

### 文档输出
- [ ] 计划文档：`.sisyphus/plans/multi-turn-conversation-support.md`
- [ ] 研究摘要：`.sisyphus/drafts/multi-turn-research-summary.md`

---

## 附录：快速参考

### PydanticAI 关键 API
```python
from pydantic_ai.messages import ModelMessagesTypeAdapter

# 序列化
json_bytes = ModelMessagesTypeAdapter.dump_json(messages)

# 反序列化
messages = ModelMessagesTypeAdapter.validate_json(json_bytes)

# 选择：const messages = ModelMessagesTypeAdapter.validate_json(json_bytes)
```

### CrewAI 状态模式
```python
# 调用栈
state.stack.append(task_frame)  # PUSH
state.stack.pop()               # POP
current = state.stack[-1]     # PEEK

# 历史累加
state.conversation_history.append({"role": "user", "content": msg})
```

### LangGraph 会话模式
```python
# thread_id 作为会话标识
config = {"configurable": {"thread_id": "user-123"}}
result = await app.ainvoke(input_data, config=config)

# 同一 thread_id → 状态保持
```

---

**报告完成时间**: 2026-01-22
**总研究任务**: 7 个并行任务
**参考资料**：完整代码库 + PydanticAI 官方文档 + LangGraph GitHub
