# Parallel Tool Calling & Error Handling 调研总结

## 概述

本文档调研 AgentPool 和 Pydantic-AI 在并行工具调用（Parallel Tool Calling）和错误处理方面的实现差异。

**核心问题**：
1. 大模型一次生成多个工具调用时，如何处理？
2. 多个工具调用中，如果某一个失败（参数校验失败），会如何处理？

---

## 1. Parallel Tool Calling 实现对比

### Pydantic-AI：工具级别并行

**核心机制**：默认并行执行单次模型响应中的多个工具调用

**实现方式**：
```python
# _agent_graph.py
# 并行执行多个工具调用
tasks = [asyncio.create_task(_call_tool(...)) for call in tool_calls]

# 使用 FIRST_COMPLETED 策略，可流式处理完成的工具结果
while pending:
    done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        # 处理完成的任务
```

**配置方式**：
- **模型级别**：`ModelSettings(parallel_tool_calls=True/False)`
- **Agent 级别**：`with agent.sequential_tool_calls():`
- **工具级别**：`@agent.tool(sequential=True)`

**适用场景**：
- 单次对话需要并行调用多个独立工具
- 需要工具级别的细粒度控制
- 与模型原生 `parallel_tool_calls` API 集成

---

### AgentPool：Agent/Team 级别并行

**核心机制**：两个层面的并行执行
1. **Team 级别**：多个 agent 并行执行
2. **函数级别**：基于依赖关系的智能分组并行

**Team 并行执行**：
```python
# team.py
# 使用 asyncio.gather 并行执行所有 agent
await asyncio.gather(*[_run(node) for node in all_nodes])
```

**函数分组并行执行**：
```python
# executor.py
# 按依赖关系分组并行执行
groups = _group_parallel(sorted_funcs)
for group in groups:
    # 组内并行执行
    group_results = await asyncio.gather(*[
        execute_single(func, pool, results, inputs)
        for func in group
    ])
```

**配置方式**：
- **Team 配置**：`mode: parallel` / `mode: sequential`
- **代码配置**：`agent1 & agent2 & agent3`（并行）
- **依赖声明**：`@node_function(depends_on=["func_a"])`

**适用场景**：
- 多 agent 协作（如：并行处理多个任务，再汇总结果）
- 复杂工作流中的并行处理（有依赖关系的函数执行）
- 跨协议的 agent 编排（ACP, AG-UI, MCP 等）

---

## 2. 关键差异对比

| 维度 | Pydantic-AI | AgentPool |
|------|-------------|-----------|
| **并行粒度** | 工具调用级别 | Agent/Team 和函数级别 |
| **默认行为** | 默认并行 | 默认串行（需显式配置） |
| **任务完成策略** | FIRST_COMPLETED（流式处理） | gather（等待全部完成） |
| **依赖处理** | 不支持工具间依赖 | 支持函数依赖关系 |
| **核心并发原语** | `create_task` + `wait(FIRST_COMPLETED)` | `asyncio.gather()` |

---

## 3. 错误处理机制（工具执行失败）

### Pydantic-AI：独立重试，部分失败不影响其他

**场景**：并行调用 3 个工具（A、B、C），假设 B 工具执行失败

**处理流程**：
```
A: ✅ 成功 → 保留结果
B: ❌ 失败 → 返回 RetryPromptPart，模型重试 B
C: ✅ 成功 → 保留结果
```

**关键代码**：
```python
# _tool_manager.py
except Exception as e:
    # 捕获工具执行失败
    current_retry = self.ctx.retries.get(name, 0)
    if current_retry < max_retries:
        # 创建 RetryPromptPart 包含错误详情
        m = RetryPromptPart(
            tool_name=name,
            content=e.errors(include_url=False),
            tool_call_id=call.tool_call_id,
        )
        self.failed_tools.add(name)
        raise ToolRetryError(m)
```

**重试策略**：
- ✅ **只重试失败的工具**（`self.ctx.retries.get(name, 0)`）
- ✅ 其他工具不受影响，继续执行
- ✅ 每个工具独立的重试计数器

---

### AgentPool：整体失败（当前实现问题）

**场景**：并行调用 3 个任务（A、B、C），假设 B 失败

**当前行为**：
```
A: ✅ 成功 → 但被取消
B: ❌ 失败 → 整个 gather 抛出异常
C: ⏸️ 被停止 → 未完成
```

**关键问题**：
```python
# team.py - 当前实现
await asyncio.gather(*[_run(node) for node in all_nodes])  # ❌ 缺少 return_exceptions=True

# executor.py - 当前实现
group_results = await asyncio.gather(*tasks)  # ❌ 缺少 return_exceptions=True
```

**问题分析**：
- `asyncio.gather()` **默认**在第一个异常时立即抛出
- 没有设置 `return_exceptions=True`
- **单个任务失败会导致整个并行批次失败**

---

### 修复建议

AgentPool 应该改为：

```python
# Team 执行应该捕获所有异常
await asyncio.gather(*[_run(node) for node in all_nodes], return_exceptions=True)

# 函数执行也应该捕获所有异常
group_results = await asyncio.gather(*tasks, return_exceptions=True)
```

修复后的行为：
```
A: ✅ 成功 → 保留结果
B: ❌ 失败 → 记录到 errors 字典
C: ✅ 成功 → 保留结果
```

---

## 4. 参数校验失败处理（RetryPromptPart 机制）

### 场景示例

大模型生成了 3 个工具调用：A、B、C，其中 **B 的参数不符合 Pydantic schema**。

```
A: search_weather(location="北京") ✅ 参数正确
B: search_stocks(symbol=123) ❌ 参数类型错误（应该是字符串）
C: search_news(topic="AI") ✅ 参数正确
```

---

### Pydantic-AI 处理流程

#### 第 1 步：参数校验失败

```python
# _tool_manager.py
try:
    # 使用 Pydantic 校验参数
    args_dict = validator.validate_json(call.args or '{}', allow_partial=pyd_allow_partial, context=ctx.validation_context)
    # 调用工具
    return await self.toolset.call_tool(name, args_dict, ctx, tool)
except ValidationError as e:
    # 参数校验失败
    current_retry = self.ctx.retries.get(name, 0)
    if current_retry < max_retries:
        # 创建 RetryPromptPart
        m = RetryPromptPart(
            tool_name=name,
            content=e.errors(include_url=False, include_context=False),
            tool_call_id=call.tool_call_id,
        )
        self.failed_tools.add(name)
        raise ToolRetryError(m)
```

#### 第 2 步：创建 RetryPromptPart

`RetryPromptPart` 包含：
- `tool_name`: 失败的工具名称（如 `search_stocks`）
- `content`: 错误详情（如 `"expected str, got int"`）
- `tool_call_id`: 工具调用 ID（OpenAI 等模型需要）

```python
# messages.py
class RetryPromptPart(ModelRequestPart):
    """用于告诉模型需要重试某个工具调用"""
    tool_name: str
    content: ErrorDetails | str
    tool_call_id: str | None
```

#### 第 3 步：发送给模型

在 `_agent_graph.py` 中，`RetryPromptPart` 会被添加到 `ModelRequest`：

```python
# 对话历史会包含：
[
    UserPromptPart("查询天气、股票和新闻"),
    ToolCallPart(tool_name="search_weather", args='{"location":"北京"}'),  # A
    ToolReturnPart(result="北京今天晴天"),  # A 的结果
    ToolCallPart(tool_name="search_stocks", args='{"symbol":123}'),  # B ❌
    RetryPromptPart(  # 告诉模型 B 失败了
        tool_name="search_stocks",
        content=[{"msg": "expected str, got int"}],
        tool_call_id="call_123"
    ),
    ToolCallPart(tool_name="search_news", args='{"topic":"AI"}'),  # C
    ToolReturnPart(result="AI 新闻摘要"),  # C 的结果
]
```

#### 第 4 步：模型重新生成整个响应

**关键点**：模型会看到**完整的对话历史**，然后重新生成一个**完整的新响应**。

模型需要：
1. 看到之前所有的工具调用（A、B、C）
2. 看到 B 的参数校验失败
3. **修正 B 的参数**
4. **重新生成所有工具调用**（包括 A、修正后的 B、C）

```
模型的第 2 次响应：
A: search_weather(location="北京") ✅（可能再次调用）
B: search_stocks(symbol="AAPL") ✅（修正了参数）
C: search_news(topic="AI") ✅（可能再次调用）
```

---

### 关键机制

#### 1. 失败工具跟踪

```python
# _tool_manager.py
class ToolManager:
    failed_tools: set[str]  # 记录失败的工具名称

    def for_run_step(self) -> Self:
        """为新的运行步骤创建新的上下文"""
        ctx = self.ctx.for_run_step(failed_tools=self.failed_tools)
        return self
```

#### 2. 独立重试计数

```python
# 每个工具独立的重试计数器
current_retry = self.ctx.retries.get(tool_name, 0)

if current_retry >= max_retries:
    raise UnexpectedModelBehavior(f'Tool exceeded max retries')
```

#### 3. 最大重试限制

默认每个工具最多重试 **1 次**（可以通过 `max_retries` 配置）。

---

### AgentPool 处理方式

AgentPool 继承 Pydantic-AI 的机制：
- 使用相同的 `ToolManager`
- 参数校验完全依赖 Pydantic-AI
- 失败时同样创建 `RetryPromptPart`
- 模型同样重新生成整个响应

---

## 5. 核心问题与答案

### Q1: 参数校验失败时，是重试失败的某个工具，还是全部重试？

**答案：模型重新生成整个响应，而不是只重新生成失败的某个工具调用。**

**设计理由**：
1. **简化模型理解**：模型更容易理解完整的对话历史，而不是复杂的局部修正指令
2. **一致性**：所有工具调用都是完整响应的一部分，部分重试会导致上下文不连续
3. **模型能力**：模型有能力基于历史信息修正错误，不需要人工干预

**缺点**：更频繁的模型调用，可能增加成本和延迟。

---

### Q2: 参数校验失败时，其他工具的执行受影响吗？

**答案（Pydantic-AI）**：
- ✅ 之前成功的工具结果会保留
- ✅ 模型看到完整的对话历史（包括成功的工具调用、失败的工具调用、RetryPromptPart）
- ✅ 其他工具继续正常执行

**答案（AgentPool）**：
- ✅ 继承 Pydantic-AI 的机制，行为相同
- ⚠️ 工具执行失败时，当前实现有问题（见第 3 节修复建议）

---

### Q3: RetryPromptPart 是如何工作的？

**答案**：
1. 参数校验失败时，创建 `RetryPromptPart` 包含错误详情
2. `RetryPromptPart` 作为 `ModelRequestPart` 的一部分发送给模型
3. 告诉模型某个工具调用失败，需要修正参数
4. 模型基于完整的对话历史重新生成响应

---

### Q4: 有没有跟踪失败工具的机制？

**答案（Pydantic-AI）**：
- ✅ `ToolManager` 维护 `failed_tools: set[str]` 字段
- ✅ 记录当前运行步骤中校验失败的工具名称
- ✅ 每个失败的工具都有独立的重试计数器（`ctx.retries.get(tool_name, 0)`）

**答案（AgentPool）**：
- ✅ 继承 Pydantic-AI 的机制，行为相同

---

## 6. 对比总结

### 工具执行失败

| 维度 | Pydantic-AI | AgentPool |
|------|-------------|-----------|
| **失败影响范围** | 仅影响失败的工具 | 影响整个并行批次（当前实现问题） |
| **其他工具执行** | ✅ 继续执行 | ❌ 被停止/取消（当前实现问题） |
| **重试策略** | 单个工具独立重试 | 需手动重试整个批次（当前实现问题） |
| **部分结果** | ✅ 保留成功的结果 | ❌ 取消/未定义（当前实现问题） |
| **错误传播** | 返回 RetryPromptPart | 抛出异常 |

**修复建议**：AgentPool 需要添加 `return_exceptions=True` 参数

---

### 参数校验失败

| 问题 | 答案 |
|------|------|
| **重试范围** | ❌ **不是**只重试失败的某个工具调用 |
| **实际行为** | ✅ **模型重新生成整个响应**（包含所有工具调用） |
| **其他工具影响** | ✅ 之前成功的工具结果保留，模型看到完整历史 |
| **重试计数** | ✅ 每个工具独立的重试计数器（默认最多 1 次） |
| **失败跟踪** | ✅ `failed_tools` 记录失败的工具名称 |

---

## 7. 最佳实践建议

### 对于 Pydantic-AI

✅ **推荐**：
1. 使用 `ModelSettings(parallel_tool_calls=True)` 启用并行工具调用
2. 使用 `@agent.tool(sequential=True)` 标记需要串行执行的工具
3. 使用 `with agent.sequential_tool_calls():` 临时强制串行执行
4. 配置 `max_retries` 参数控制重试次数

❌ **避免**：
1. 不要过度使用 `sequential=True`，会降低性能
2. 不要设置过大的 `max_retries`，会增加成本

---

### 对于 AgentPool

✅ **推荐**：
1. 使用 `mode: parallel` 配置启用多 agent 并行执行
2. 使用 `@node_function(depends_on=["func_a"])` 声明函数依赖
3. 使用 `agent1 & agent2 & agent3` 创建并行 Team

❌ **避免**：
1. 当前实现有 bug（缺少 `return_exceptions=True`）
2. 建议修复后再使用并行模式

---

## 8. 关键代码位置

### Pydantic-AI

| 文件 | 说明 |
|-----|-----|
| `_agent_graph.py` | 并行工具调用的核心实现（_call_tools 函数） |
| `_tool_manager.py` | ToolManager 类，包含参数校验和重试逻辑 |
| `settings.py` | ModelSettings 定义，包含 parallel_tool_calls 配置 |
| `models/openai.py` | OpenAI 模型适配器，传递 parallel_tool_calls 参数 |
| `messages.py` | RetryPromptPart 定义 |

### AgentPool

| 文件 | 说明 |
|-----|-----|
| `delegation/team.py` | Team 并行执行（需要修复） |
| `running/executor.py` | 函数分组并行执行（需要修复） |
| `running/run_nodes.py` | 节点并行执行接口 |

---

## 9. 待修复问题

### AgentPool 错误处理 Bug

**问题**：`asyncio.gather()` 未设置 `return_exceptions=True`

**影响**：
- 单个任务失败会导致整个并行批次失败
- 所有其他任务被取消/停止
- 无法保留部分成功的任务结果

**修复位置**：
1. `delegation/team.py` 第 67 行
2. `running/executor.py` 第 263 行

**修复方案**：
```python
# 修复前
await asyncio.gather(*[_run(node) for node in all_nodes])
group_results = await asyncio.gather(*tasks)

# 修复后
await asyncio.gather(*[_run(node) for node in all_nodes], return_exceptions=True)
group_results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 10. 总结

### Pydantic-AI 的优势

1. ✅ **工具级别粒度**：在单次模型响应中，并行执行多个工具调用
2. ✅ **智能调度**：使用 `FIRST_COMPLETED` 策略，可以尽早处理完成的工具结果
3. ✅ **灵活控制**：支持全局、局部、工具级别的串行控制
4. ✅ **容错性强**：单个工具失败不影响其他工具
5. ✅ **模型集成**：直接与模型 API 的 `parallel_tool_calls` 参数集成

---

### AgentPool 的优势

1. ✅ **Agent 级别粒度**：并行执行多个完整的 agent 或工作流
2. ✅ **依赖感知**：支持函数间的依赖关系，智能分组并行
3. ✅ **框架通用**：不依赖特定模型，适用于各种 agent 类型
4. ✅ **工作流导向**：更适合多 agent 协作和复杂工作流场景

---

### 使用建议

**选择 Pydantic-AI 如果你需要**：
- 在单次对话中并行调用多个独立工具
- 需要工具级别的细粒度控制
- 需要与模型的原生并行工具调用集成
- 单 agent 场景下的高性能工具执行

**选择 AgentPool 如果你需要**：
- 多 agent 协作和并行处理
- 复杂的工作流和依赖管理
- 跨协议的 agent 编排（ACP, AG-UI, MCP 等）
- 基于函数依赖的智能并行执行

**两者互补**：如果需要多 agent 并行，且每个 agent 内部又要多工具并行，可以结合使用——AgentPool 管理 agent 并行，每个 agent 内部使用 Pydantic-AI 的 parallel_tool_calls。

---

## 参考资源

### 相关文档

- AgentPool 工具系统：`01-tools-config-overview.md`
- Schema 生成流程：`03-schema-generation-flow.md`
- 工具实现指南：`04-implement-new-tool-guide.md`

### 源码位置

- Pydantic-AI：`/Users/yuchen.liu/src/yilab/iroot-llm/packages/pydantic-ai/`
- AgentPool：`/Users/yuchen.liu/src/yilab/iroot-llm/packages/agentpool/`
