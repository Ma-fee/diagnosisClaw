# RFC 005.4: Pydantic AI 消息处理与验证机制调研

## 状态
**状态**: Draft
**创建日期**: 2026-01-20
**作者**: Sisyphus
**最后更新**: 2026-01-20

---

## 概述

本文档记录了对 Pydantic AI 框架中**消息处理、Pydantic 验证机制、以及错误恢复策略**的调研结果。这些信息是设计 Xeno Agent 系统的重要上下文，特别是关于：
- 消息历史的存储与访问
- 验证失败的处理机制
- 原始消息的保留能力
- 错误重试流程

---

## 核心调研结论

### 1. 消息存储机制

#### 存储位置

| 组件 | 属性 | 类型 | 用途 |
|-------|------|------|------|
| **RunContext** | `messages` | `list[ModelMessage]` | 单次运行的消息历史 |
| **GraphAgentState** | `message_history` | `list[ModelMessage]` | 跨运行的持久化消息历史 |
| **StreamedRunResult** | `_all_messages` | `list[ModelMessage]` | 流式运行的完整历史 |

#### 消息类型结构

```python
# 核心消息类型定义
ModelMessage = Annotated[
    ModelRequest | ModelResponse,
    pydantic.Discriminator('kind')
]

# ModelRequest (kind='request') - Pydantic AI → Model
# 包含: SystemPromptPart, UserPromptPart, ToolReturnPart, RetryPromptPart

# ModelResponse (kind='response') - Model → Pydantic AI
# 包含: TextPart, ThinkingPart, ToolCallPart, BuiltinToolCallPart
```

#### 源码证据

**RunContext 定义**:
```python
# pydantic_ai_slim/pydantic_ai/_run_context.py:41-42
@dataclasses.dataclass(kw_only=True)
class RunContext(Generic[RunContextAgentDepsT]):
    """Information about current call."""

    messages: list[_messages.ModelMessage] = field(default_factory=list)
    """Messages exchanged in conversation so far."""
```

**GraphAgentState 定义**:
```python
# pydantic_ai_slim/pydantic_ai/_agent_graph.py:89-90
@dataclasses.dataclass(kw_only=True)
class GraphAgentState:
    """State kept across execution of agent graph."""

    message_history: list[_messages.ModelMessage] = dataclasses.field(default_factory=list)
```

---

## 2. 验证失败处理机制

### 2.1 完整流程图

```
输入/输出
    │
    ▼
Pydantic 验证 (validate_python / validate_json)
    │
    ├─→ 成功 → 继续执行
    │
    └─→ 失败
        │
        ├─→ 检查重试次数
        │   │
        │   ├─→ 未超过 max_retries
        │   │       │
        │   │       ├─→ 创建 RetryPromptPart
        │   │       │   (包含 ValidationError.errors())
        │   │       │
        │   │       ├─→ 包装为 ToolRetryError
        │   │       │
        │   │       └─→ 模型自动重试
        │   │
        │   └─→ 超过 max_retries
        │           │
        │           └─→ 抛出 UnexpectedModelBehavior
        │               (终止执行）
```

### 2.2 工具参数验证失败

**核心代码位置**: `pydantic_ai_slim/pydantic_ai/_tool_manager.py:84-99`

```python
async def _call_tool(
    self,
    call: ToolCallPart,
    *,
    allow_partial: bool,
    wrap_validation_errors: bool,
    approved: bool,
    metadata: Any = None,
) -> Any:
    """Handle a tool call by validating arguments, calling tool, and handling retries."""

    # Step 1: 获取工具
    name = call.tool_name
    tool = self.tools.get(name)

    # Step 2: 验证工具参数 ⚠️ 关键
    pyd_allow_partial = 'trailing-strings' if allow_partial else 'off'
    validator = tool.args_validator

    try:
        # JSON 字符串输入
        if isinstance(call.args, str):
            args_dict = validator.validate_json(
                call.args or '{}',
                allow_partial=pyd_allow_partial,
                context=ctx.validation_context
            )
        # Python 字典输入
        else:
            args_dict = validator.validate_python(
                call.args or {},
                allow_partial=pyd_allow_partial,
                context=ctx.validation_context
            )

    # ⚠️ Step 3: 捕获验证错误
    except (ValidationError, ModelRetry) as e:
        max_retries = tool.max_retries if tool is not None else self.default_max_retries
        current_retry = self.ctx.retries.get(name, 0)

        # ⚠️ Step 4: 检查重试次数
        if current_retry == max_retries:
            # 超过最大重试次数，抛出异常终止
            raise UnexpectedModelBehavior(
                f'Tool {name!r} exceeded max retries count of {max_retries}'
            ) from e
        else:
            # Step 5: 将验证错误包装为 RetryPromptPart
            if wrap_validation_errors:
                if isinstance(e, ValidationError):
                    # ⚠️ 关键：创建 RetryPromptPart
                    m = _messages.RetryPromptPart(
                        tool_name=name,
                        content=e.errors(include_url=False, include_context=False),
                        tool_call_id=call.tool_call_id,
                    )
                    e = ToolRetryError(m)

            # Step 6: 记录失败的工具
            if not allow_partial:
                self.failed_tools.add(name)

            # Step 7: 重新抛出，让模型重试
            raise e
```

### 2.3 RetryPromptPart 结构

```python
# pydantic_ai_slim/pydantic_ai/messages.py:900-987

@dataclass
class RetryPromptPart:
    """A message back to a model asking it to try again.

    This can be sent for a number of reasons:
    * Pydantic validation of tool arguments failed
    * a tool raised a ModelRetry exception
    * no tool was found for tool name
    * model returned plain text when a structured response was expected
    * Pydantic validation of a structured response failed
    * an output validator raised a ModelRetry exception
    """

    content: list[ErrorDetails] | str
    """Details of why and how to model should retry.

    If retry was triggered by a ValidationError,
    this will be a list of error details.
    """

    tool_name: str | None = None
    """The name of the tool that was called, if any."""

    tool_call_id: str = field(default_factory=_generate_tool_call_id)
    """The tool call identifier."""

    part_kind: Literal['retry-prompt'] = 'retry-prompt'
```

### 2.4 验证失败的消息序列示例

```json
[
  // 1. 模型调用工具（参数错误）
  {
    "kind": "response",
    "parts": [
      {
        "part_kind": "tool-call",
        "tool_name": "search_web",
        "args": {
          "query": 123  // ⚠️ 类型错误：期望字符串
        }
      }
    ]
  },

  // 2. Pydantic 验证失败 → 自动插入 RetryPromptPart
  {
    "kind": "request",
    "parts": [
      {
        "part_kind": "retry-prompt",
        "tool_name": "search_web",
        "content": [
          {
            "type": "string_type",
            "loc": ["query"],
            "msg": "Input should be a valid string",
            "input": 123
          }
        ],
        "tool_call_id": "tool-call-123"
      }
    ]
  },

  // 3. 模型重新发起工具调用（修正参数）
  {
    "kind": "response",
    "parts": [
      {
        "part_kind": "tool-call",
        "tool_name": "search_web",
        "args": {
          "query": "hello world"  // ✅ 修正为字符串
        }
      }
    ]
  }
]
```

---

## 3. 重试机制

### 3.1 重试计数

```python
# pydantic_ai_slim/pydantic_ai/_run_context.py:51-52
@dataclasses.dataclass
class RunContext:
    retries: dict[str, int] = field(default_factory=dict)
    """Number of retries for each tool so far."""

    max_retries: int = 0
    """The maximum number of retries of this tool."""
```

### 3.2 重试流程

```python
# pydantic_ai_slim/pydantic_ai/_agent_graph.py:96-117 (伪代码）
while True:
    try:
        # 调用工具
        result = await tool_manager.call_tool(tool_name, args)

        # 成功，退出重试循环
        break

    except ToolRetryError as e:
        # 增加重试计数
        ctx.retries[tool_name] = ctx.retries.get(tool_name, 0) + 1
        current_retry = ctx.retries[tool_name]

        # 检查是否超过最大重试次数
        max_retries = tool.max_retries or default_max_retries

        if current_retry >= max_retries:
            # 超过限制，抛出异常
            raise UnexpectedModelBehavior(
                f'Tool {tool_name} exceeded max retries count of {max_retries}'
            ) from e

        # 未超过限制，创建 RetryPromptPart 让模型重试
        retry_prompt = e.retry_prompt  # 包含错误详情
        messages.append(retry_prompt)

        # 继续循环，等待模型重新发起调用
        continue
```

### 3.3 默认配置

```python
# pydantic_ai_slim/pydantic_ai/_tool_manager.py
class ToolManager:
    default_max_retries: int = 3  # 默认最多重试 3 次
```

---

## 4. 原始消息访问能力

### 4.1 能力矩阵

| 需求 | 支持情况 | 说明 |
|------|---------|------|
| **完整消息历史** | ✅ 支持 | `RunContext.messages` 和 `GraphAgentState.message_history` |
| **验证失败保留** | ✅ 支持（但不完全原始） | 错误转换为 `RetryPromptPart` |
| **原始未验证消息** | ❌ 不支持 | 无法直接访问完全原始的、未经验证的消息 |
| **验证错误详情** | ✅ 支持 | `RetryPromptPart.content` 包含完整错误列表 |
| **错误上下文** | ✅ 支持 | 工具名、参数、时间戳 |
| **重试历史** | ✅ 支持 | `ctx.retries` 记录每个工具的重试次数 |

### 4.2 访问消息历史的方法

#### 方法 1: 在 Hook 中访问

```python
async def my_hook(ctx: HookContext):
    # ✅ ctx.run_context.messages 包含完整历史
    all_messages = ctx.run_context.messages

    # ✅ 筛选 RetryPromptPart（验证失败）
    from pydantic_ai._messages import RetryPromptPart
    errors = [
        msg for msg in all_messages
        if isinstance(msg, RetryPromptPart)
    ]

    for error_msg in errors:
        print(f"Tool: {error_msg.tool_name}")
        print(f"Errors: {error_msg.content}")  # list[ErrorDetails]
```

#### 方法 2: 使用 capture_run_messages

```python
from pydantic_ai import capture_run_messages

with capture_run_messages() as captured:
    await agent.run()

# ✅ captured.messages 包含完整历史
for msg in captured.messages:
    if msg.kind == 'response':
        for part in msg.parts:
            if hasattr(part, 'part_kind') and part.part_kind == 'retry-prompt':
                print(f"Validation failed: {part.content}")
```

---

## 5. 输出验证

### 5.1 核心代码位置

**pydantic_ai_slim/pydantic_ai/_output.py:71-98**

```python
@dataclass
class OutputValidator(Generic[AgentDepsT, OutputDataT_inv]):
    function: OutputValidatorFunc[AgentDepsT, OutputDataT_inv]

    async def validate(
        self,
        result: T,
        run_context: RunContext[AgentDepsT],
        wrap_validation_errors: bool = True,
    ) -> T:
        """Validate a result by calling to function.

        Returns:
            Result of either validated result data (ok) or a retry message (Err).
        """
        if self._takes_ctx:
            args = run_context, result
        else:
            args = (result,)

        try:
            # Step 1: 调用用户定义的输出验证函数
            if self._is_async:
                function = cast(Callable[[Any], Awaitable[T]], self.function)
                result_data = await function(*args)
            else:
                function = cast(Callable[[Any], T], self.function)
                result_data = await _utils.run_in_executor(function, *args)
            return result_data

        # ⚠️ Step 2: 捕获 ModelRetry 异常（包括 ValidationError）
        except ModelRetry as r:
            if wrap_validation_errors:
                # Step 3: 将错误包装为 RetryPromptPart
                m = _messages.RetryPromptPart(
                    content=r.message,
                    tool_name=run_context.tool_name,
                )
                if run_context.tool_call_id:
                    m.tool_call_id = run_context.tool_call_id
                raise ToolRetryError(m) from r
            else:
                # 不包装，直接抛出
                raise r

        # ⚠️ Step 4: 其他异常直接抛出
        except ValidationError as e:
            if wrap_validation_errors:
                m = _messages.RetryPromptPart(
                    content=e.errors(include_url=False, include_context=False),
                    tool_name=run_context.tool_name,
                )
                if run_context.tool_call_id:
                    m.tool_call_id = run_context.tool_call_id
                raise ToolRetryError(m) from e
            raise
```

### 5.2 输出验证示例

```python
from pydantic_ai import Agent, result_validator

@result_validator
def validate_output(result: str) -> str:
    """输出验证函数"""
    if len(result) > 1000:
        # 抛出 ModelRetry 会让模型重试
        raise ModelRetry("Result too long, max 1000 chars")
    if "<script>" in result:
        raise ModelRetry("Result contains dangerous content")
    return result

# 当输出验证失败时的消息序列
[
  # 模型输出
  {'kind': 'response', 'parts': [{'part_kind': 'text', 'text': '...'}]},

  # 自动插入的重试提示
  {
    'kind': 'request',
    'parts': [
      {
        'part_kind': 'retry-prompt',
        'content': 'Result too long, max 1000 chars',
      }
    ]
  }
]
```

---

## 6. 访问原始消息的变通方案

### 6.1 方案 1: 自定义 Tool Hook（推荐）

**优点**:
- ✅ 在验证前拦截，保存原始参数
- ✅ 无侵入性，仅需注册 Hook
- ✅ 灵活性高

**缺点**:
- ⚠️ 只能捕获工具调用，无法捕获模型输出
- ⚠️ 需要自己管理消息存储

**实现**:
```python
class RawMessageCaptureHook:
    def __init__(self):
        self.raw_messages: list[dict] = []

    async def tool_call_before(self, ctx: HookContext) -> bool:
        """在 Pydantic 验证前保存原始输入"""
        if ctx.tool_args:
            self.raw_messages.append({
                "timestamp": time.time(),
                "tool_name": ctx.tool_name,
                "raw_args": ctx.tool_args,  # ✅ 原始参数
                "validated": False,  # 尚未验证
            })
        return True

    async def tool_call_after(self, ctx: HookContext):
        """验证后标记状态"""
        # 找到对应的原始消息，标记为已验证
        for msg in reversed(self.raw_messages):
            if msg["tool_name"] == ctx.tool_name:
                msg["validated"] = True
                msg["validated_args"] = ctx.tool_result
                if ctx.exception:
                    msg["error"] = str(ctx.exception)
                break
```

### 6.2 方案 2: 自定义 WrapperToolset

**优点**:
- ✅ 可以拦截所有工具调用
- ✅ 可以修改工具行为
- ✅ 与 ACP Bridge 无缝集成

**缺点**:
- ⚠️ 需要更多 Boilerplate 代码
- ⚠️ 必须正确转发所有工具操作

**实现**:
```python
class RawMessageToolset(ACPBridgeToolset):
    def __init__(self, *args, raw_logger=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_logger = raw_logger or RawMessageLogger()

    async def execute_tool(self, tool_name: str, args: dict, ctx):
        """在发送到 ACP 前记录原始输入"""
        # ✅ 保存原始请求
        await self.raw_logger.log_raw_tool_call(
            tool_name=tool_name,
            raw_args=args,  # 原始参数
            timestamp=time.time(),
        )

        # 继续执行
        return await super().execute_tool(tool_name, args, ctx)

class RawMessageLogger:
    async def log_raw_tool_call(self, tool_name: str, raw_args: dict, timestamp: float):
        # 可以选择：
        # 1. 写入数据库
        # 2. 写入文件
        # 3. 发送到消息队列
        pass
```

### 6.3 方案 3: 修改 Tool 的 args_validator

**优点**:
- ✅ 在 Pydantic 验证层级操作
- ✅ 可以访问验证上下文

**缺点**:
- ⚠️ 需要修改每个工具定义
- ⚠️ 侵入性强

**实现**:
```python
from pydantic_ai import Tool
from pydantic import BaseModel, model_validator

# 方案 A: Hook 在验证前
class MyToolArgs(BaseModel):
    query: str

    @model_validator(mode='before')
    @classmethod
    def validate_before(cls, data):
        # 在 Pydantic 官方验证前执行
        raw_inputs.append({
            "raw": data,
            "timestamp": time.time(),
        })
        return data

@tool
def my_tool(query: str) -> str:
    """My custom tool"""
    return f"Result: {query}"

# 方案 B: 自定义验证器
@tool
def my_tool(query: str) -> str:
    """My custom tool with custom validation"""
    # 原始验证逻辑
    from pydantic import ValidationError
    try:
        if not query:
            raise ValueError("Query cannot be empty")
    except Exception as e:
        # 保存到全局上下文
        raw_errors.append({
            "tool": "my_tool",
            "raw_input": {"query": query},
            "error": str(e),
            "timestamp": time.time(),
        })
        raise

    # 正常逻辑
    return f"Result: {query}"
```

### 6.4 方案 4: Syslog/Telemetry Hook

**优点**:
- ✅ 捕获全部输入输出
- ✅ 独立于特定工具验证

**缺点**:
- ⚠️ 无法直接访问验证前的原始状态
- ⚠️ 只能记录验证后的数据

**实现**:
```python
class TelemetryCaptureHook:
    event = "agent.run.before"

    def __init__(self, storage: MessageStorage):
        self.storage = storage

    async def execute(self, ctx: HookContext) -> bool:
        """保存原始 prompt"""
        await self.storage.save(
            type="input",
            prompt=ctx.run_context.prompt,
            timestamp=time.time(),
        )
        return True

class MessageStorage:
    async def save(self, type: str, prompt, timestamp: float):
        # 根据需求存储
        pass
```

---

## 7. 完整示例

### 7.1 完整消息日志系统

```python
import time
from typing import Any
from pydantic_ai import Agent, RunContext

class CompleteMessageLogger:
    """完整消息记录器（包括验证失败）"""

    def __init__(self):
        self.raw_messages: list[dict] = []
        self.validated_messages: list[dict] = []
        self.error_messages: list[dict] = []

    async def log_tool_call(self, ctx: RunContext, tool_name: str, args: dict):
        """记录原始工具调用"""
        self.raw_messages.append({
            "timestamp": time.time(),
            "tool_name": tool_name,
            "raw_args": args,
            "status": "pending",
        })

    async def log_validation_success(self, tool_name: str, validated_args: dict):
        """记录验证成功"""
        self.validated_messages.append({
            "timestamp": time.time(),
            "tool_name": tool_name,
            "validated_args": validated_args,
        })

    async def log_validation_error(self, tool_name: str, error: ValidationError):
        """记录验证失败"""
        self.error_messages.append({
            "timestamp": time.time(),
            "tool_name": tool_name,
            "error_details": error.errors(),  # ✅ 完整错误信息
        })

# 使用
logger = CompleteMessageLogger()

class ToolValidationHook:
    event = "tool.call.before"

    def __init__(self, logger: CompleteMessageLogger):
        self.logger = logger

    async def execute(self, ctx: HookContext) -> bool:
        if ctx.tool_name:
            await logger.log_tool_call(ctx.run_context, ctx.tool_name, ctx.tool_args)
        return True

class ToolResultHook:
    event = "tool.call.after"

    def __init__(self, logger: CompleteMessageLogger):
        self.logger = logger

    async def execute(self, ctx: HookContext):
        if ctx.exception:
            from pydantic import ValidationError
            if isinstance(ctx.exception, ValidationError):
                await logger.log_validation_error(
                    ctx.tool_name,
                    ctx.exception
                )
        elif ctx.tool_result is not None:
            await logger.log_validation_success(
                ctx.tool_name,
                ctx.tool_result
            )
```

### 7.2 验证失败的实际用例

```python
from pydantic_ai import Agent, Tool
from pydantic import BaseModel, ValidationError

# 工具定义
@tool
def search_web(query: str) -> str:
    """Search web for information"""
    return f"Results for: {query}"

# 第一次调用（参数类型错误）
try:
    result = await agent.run(
        prompt="Search for 123",  # 模型传递了数字而不是字符串
    )
except UnexpectedModelBehavior as e:
    print(f"Failed after 3 retries: {e}")

# 消息流程
# 1. model: search_web(args={'query': 123})
# 2. pydantic: ValidationError (type error)
# 3. agent: RetryPromptPart(content=[{'type': 'string_type'}])
# 4. model: search_web(args={'query': '123'})  # 自动重试
# 5. ✅ 成功

# 超过重试次数
@tool(max_retries=1)  # 限制最多重试 1 次
def strict_tool(data: str) -> str:
    """Strict validation tool"""
    if len(data) < 10:
        raise ValidationError("Too short", model=StrictToolArgs)
    return data

try:
    result = await agent.run(
        prompt="Call strict_tool with 'hi'",  # 太短
    )
except UnexpectedModelBehavior as e:
    print(f"Final failure: {e}")

# 消息流程
# 1. model: strict_tool(args={'data': 'hi'})
# 2. pydantic: ValidationError
# 3. agent: RetryPromptPart # 重试 1
# 4. model: strict_tool(args={'data': 'hi'})
# 5. pydantic: ValidationError
# 6. ⚠️ 超过 max_retries (1) → 抛出 UnexpectedModelBehavior
```

### 7.3 输出验证示例

```python
from pydantic_ai import result_validator

@result_validator
def validate_summary(summary: str) -> str:
    """Validate output"""
    if len(summary) < 50:
        raise ModelRetry("Summary too short, min 50 chars")
    if "TODO" in summary:
        raise ModelRetry("Remove TODO markers")
    return summary

agent = Agent(
    model='claude-3-5-sonnet-20241022',
    result_type=str,
    result_validator=validate_summary,
)

# 调用
result = await agent.run(
    prompt="Summarize this text...",
)

# 消息流程
# 1. model: "Too short" (36 chars)
# 2. validator: ModelRetry("Summary too short")
# 3. agent: RetryPromptPart(content="Summary too short")
# 4. model: "This is a longer summary..." (80 chars)
# 5. ✅ validator: 通过，返回结果
```

---

## 8. 关键发现总结

| 发现 | 说明 | 影响 |
|------|------|------|
| **消息历史完整性** | ✅ RunContext 和 GraphAgentState 存储完整消息历史 | 可用于审计、分析 |
| **验证失败保留** | ✅ 错误被转换为 RetryPromptPart 保留 | 可用于调试、改进模型提示 |
| **原始消息访问** | ❌ 无法直接访问未验证的原始输入 | 需要使用 Hook 拦截 |
| **错误详情可用** | ✅ RetryPromptPart.content 包含完整 ErrorDetails | 可用于错误分析 |
| **自动重试** | ✅ 模型会自动重试（默认最多 3 次） | 无需手动处理重试 |
| **重试限制** | ✅ 可配置 max_retries，超过后抛出异常 | 防止无限循环 |
| **配置灵活性** | ✅ 支持 wrap_validation_errors, allow_partial 等选项 | 适配不同场景 |
| **Hook 扩展点** | ✅ tool.call.before/after 可拦截所有工具调用 | 可实现自定义原始消息记录 |

---

## 9. 设计影响

### 9.1 Xeno Agent 设计建议

基于 Pydantic AI 的验证机制，Xeno Agent 的设计应考虑：

1. **错误处理策略**:
   - 依赖 Pydantic AI 的自动重试机制
   - 通过 `RetryPromptPart` 访问错误详情
   - 在 Hook 中记录验证失败到数据库/文件

2. **原始消息保存**:
   - 使用 `tool.call.before` Hook 拦截原始参数
   - 在 ACP Bridge 的 `execute_tool` 前保存

3. **审计日志**:
   - 访问 `ctx.messages` 获取完整消息历史
   - 筛选 `RetryPromptPart` 提取验证失败
   - 记录到审计系统

4. **自定义重试行为**:
   - 设置工具级别的 `max_retries`
   - 在 Hook 中实现自定义重试逻辑（如果需要）

### 9.2 示例：Xeno Agent 中的集成

```python
class XenoAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = CompleteMessageLogger()

        # 注册验证失败记录 Hook
        self.hooks = [
            ToolValidationHook(logger=self.logger),
            ToolResultHook(logger=self.logger),
        ]

    async def audit_conversation(self, session_id: str):
        """审计会话中的验证失败"""
        from pydantic_ai._messages import RetryPromptPart

        # 获取消息历史
        messages = self.run_context.messages

        # 筛选验证错误
        errors = [
            msg for msg in messages
            if isinstance(msg, RetryPromptPart)
        ]

        # 导出审计报告
        report = {
            "session_id": session_id,
            "validation_errors": [
                {
                    "tool_name": error.tool_name,
                    "error_details": error.content,
                    "timestamp": error.tool_call_id,
                }
                for error in errors
            ],
            "raw_messages": self.logger.raw_messages,
        }

        await self.audit_storage.save(report)
```

---

## 10. 开放问题

1. **性能影响**: 大量原始消息记录是否会影响性能？
2. **存储策略**: 原始消息应该存储到何处？（数据库 vs 文件）
3. **隐私合规**: 原始消息可能包含敏感信息，如何处理？
4. **分析工具**: 是否需要专门的工具来分析验证失败模式？

---

## 参考资料

- [RFC 005: 系统架构](./005_system_architecture.md)
- [RFC 005.1: Hook 系统设计](./005_hooks_system_design.md)
- [Pydantic AI Messages Source Code](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/messages.py)
- [Pydantic AI Tool Manager](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/_tool_manager.py)
- [Pydantic AI Output Validation](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/_output.py)

---

**最后更新**: 2026-01-20
**维护者**: Sisyphus
