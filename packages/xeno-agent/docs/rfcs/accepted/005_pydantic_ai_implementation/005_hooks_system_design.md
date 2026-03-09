# RFC 005.1: Hook 系统详细设计

## 状态
**状态**: Draft
**创建日期**: 2026-01-20
**作者**: Sisyphus
**最后更新**: 2026-01-20

---

## 概述

本文档详细描述 Xeno Agent 的 Hook 系统，该系统基于 Pydantic AI 的中间件机制，扩展支持工具级别和对话级别的可扩展性。

---

## 设计目标

1. **粒度控制**: 支持不同级别的事件拦截（Agent、Tool、Message）
2. **可组合性**: 多个 Hook 可以链式调用，支持顺序和逆序执行
3. **异步友好**: 所有 Hook 都是异步的，避免阻塞
4. **错误隔离**: 单个 Hook 的失败不应影响整个流程
5. **可观察性**: Hook 执行提供完整的上下文和日志

---

## Hook 生命周期

### 完整 Hook 执行流程

```
┌────────────────────────────────────────────────────────────────┐
│  1. Agent.run.before                                           │
│     ├─→ Hook 1: permission.check(ctx)                          │
│     ├─→ Hook 2: log.capture(request)                           │
│     └─→ Hook 3: metrics.start("agent_run")                    │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  2. Model Request (if model call needed)                       │
│     └─→ agent.run.before_model_request(ctx)                    │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  3. Message Communication                                       │
│     ├─→ message.transform.input(ctx)  [Optional Hook]          │
│     ├─→ Model sends response                                    │
│     └─→ message.transform.output(ctx) [Optional Hook]          │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  4. Tool Call Execution (if tool needed)                       │
│     ├─→ tool.call.before(ctx)                                 │
│     │   ├─→ Hook 1: permission.check_tool(tool_name)           │
│     │   ├─→ Hook 2: rate_limit.check(tool_name)               │
│     │   └─→ Hook 3: log.tool_start(tool_name, args)           │
│     │                                                           │
│     ├─→ Tool Execution (ACP Bridge / Local)                    │
│     │                                                           │
│     └─→ tool.call.after(ctx)                                  │
│         ├─→ Hook 3: log.tool_end(tool_name, result)            │
│         ├─→ Hook 2: metrics.record_tool(tool_name, duration)  │
│         └─→ Hook 1: cache.cache_result(tool_name, result)      │
└────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│  5. Agent.run.after                                            │
│     ├─→ Hook 3: metrics.end("agent_run")                       │
│     ├─→ Hook 2: log.capture(response)                          │
│     └─→ Hook 1: permission.cleanup()                          │
└────────────────────────────────────────────────────────────────┘

```

### 错误处理流程

```
Tool Call Execution
    │
    ├─→ tool.call.before (Success)
    │
    ├─→ Tool Execution (Error: Timeout)
    │       │
    │       ▼
    │   Hook: on_error(ctx, exception)
    │       │
    │       ├─→ If returns True: Continue to tool.call.after
    │       └─→ If returns False: Abort, bubble error
    │
    └─→ tool.call.after (with error context)
```

---

## Hook 接口定义

### 核心接口

```python
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Protocol

class HookContext:
    """Hook 上下文，包含执行相关信息"""

    agent: "XenoAgent"
    run_context: RunContext  # Pydantic AI 的 context
    event: str
    metadata: dict[str, Any]

    # 可选的数据
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: Any | None = None
    exception: Exception | None = None

class Hook(ABC):
    """Hook 基类"""

    event: str  # 事件名称

    @abstractmethod
    async def execute(self, ctx: HookContext) -> Any:
        """执行 Hook 逻辑"""
        pass
```

### 内置 Hook 类型

#### 1. Agent Lifecycle Hooks

```python
class AgentRunBeforeHook(Hook):
    event = "agent.run.before"

    async def execute(self, ctx: HookContext):
        # 示例: 权限检查
        if not self.check_permission(ctx):
            raise PermissionDeniedError()

class AgentRunAfterHook(Hook):
    event = "agent.run.after"

    async def execute(self, ctx: HookContext):
        # 示例: 日志记录
        self.logger.info(f"Agent run completed in {ctx.duration}s")
```

#### 2. Tool Call Hooks

```python
class ToolCallBeforeHook(Hook):
    event = "tool.call.before"

    async def execute(self, ctx: HookContext) -> bool:
        """
        返回 True: 继续执行工具
        返回 False: 中断工具执行
        """
        # 示例: 速率限制
        if self.rate_limit.is_exceeded(ctx.tool_name):
            return False
        return True

class ToolCallAfterHook(Hook):
    event = "tool.call.after"

    async def execute(self, ctx: HookContext):
        # 示例: 缓存工具结果
        if ctx.tool_result:
            self.cache.set(ctx.tool_name, ctx.tool_args, ctx.tool_result)
```

#### 3. Message Transformation Hooks

```python
class MessageTransformInputHook(Hook):
    event = "message.transform.input"

    async def execute(self, ctx: HookContext) -> list[Message]:
        # 示例: 移除敏感信息
        return self.sanitize_messages(ctx.run_context.messages)

class MessageTransformOutputHook(Hook):
    event = "message.transform.output"

    async def execute(self, ctx: HookContext) -> list[Message]:
        # 示例: 添加调试信息
        return self.add_debug_info(ctx.run_context.messages)
```

#### 4. Permission Hooks

```python
class PermissionRequestHook(Hook):
    event = "permission.request"

    async def execute(self, ctx: HookContext) -> PermissionDecision:
        # 示例: 权限决策 (Allow/Deny/AskUser)
        if self.is_sensitive_tool(ctx.tool_name):
            return PermissionDecision.ASK USER
        return PermissionDecision.ALLOW
```

---

## Hook 注册与管理

### Hook Registry

```python
from typing import Callable

class HookRegistry:
    def __init__(self):
        # event -> hooks (按优先级排序)
        self._hooks: dict[str, list[tuple[int, Hook]]] = {}

    def register(
        self,
        hook: Hook,
        priority: int = 100,
    ):
        """
        注册 Hook

        Args:
            hook: Hook 实例
            priority: 优先级 (数字越大越先执行)
        """
        if hook.event not in self._hooks:
            self._hooks[hook.event] = []

        self._hooks[hook.event].append((priority, hook))
        self._hooks[hook.event].sort(key=lambda x: x[0], reverse=True)

    async def execute_before(
        self,
        event: str,
        ctx: HookContext,
    ) -> HookResult:
        """
        执行 before hooks (顺序执行)

        Returns:
            HookResult.continue_: 继续执行
            HookResult.abort: 中断执行
        """
        hooks = self._hooks.get(event, [])
        hooks.sort(key=lambda x: x[0], reverse=True)

        for priority, hook in hooks:
            try:
                result = await hook.execute(ctx)

                # if hook returns False, abort execution
                if result is False:
                    return HookResult.abort(reason=f"Hook {hook.__class__} aborted")

                # if hook modifies context, apply changes
                if isinstance(result, dict):
                    ctx.metadata.update(result)

            except Exception as e:
                logger.error(f"Hook {hook.__class__} failed: {e}")
                continue

        return HookResult.continue_

    async def execute_after(
        self,
        event: str,
        ctx: HookContext,
    ) -> HookResult:
        """
        执行 after hooks (逆序执行)
        """
        hooks = self._hooks.get(event, [])
        hooks.sort(key=lambda x: x[0])  # 逆序

        for priority, hook in hooks:
            try:
                await hook.execute(ctx)
            except Exception as e:
                logger.error(f"Hook {hook.__class__} failed: {e}")
                continue

        return HookResult.continue_

@dataclass
class HookResult:
    continue_: bool
    reason: str | None = None

    @classmethod
    def continue_(cls) -> "HookResult":
        return cls(continue_=True)

    @classmethod
    def abort(cls, reason: str) -> "HookResult":
        return cls(continue_=False, reason=reason)
```

---

## 预置 Hooks 实现

### 1. Logging Hook

```python
import logging
from contextvars import ContextVar

# 上下文变量，用于跨函数传递 trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

class LoggingHook(Hook):
    event = "agent.run.before"

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def execute(self, ctx: HookContext):
        # 生成 trace ID
        trace_id = uuid.uuid4().hex
        trace_id_var.set(trace_id)

        self.logger.info(
            f"[{trace_id}] Agent run started",
            extra={
                "trace_id": trace_id,
                "model": ctx.run_context.model,
                "messages": len(ctx.run_context.messages),
            }
        )

class ToolLoggingHook(Hook):
    event = "tool.call.before"

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    async def execute(self, ctx: HookContext) -> bool:
        trace_id = trace_id_var.get()
        self.logger.info(
            f"[{trace_id}] Tool call: {ctx.tool_name}",
            extra={
                "trace_id": trace_id,
                "tool": ctx.tool_name,
                "args": ctx.tool_args,
            }
        )
        return True
```

### 2. Permission Hook

```python
class PermissionPolicy:
    def __init__(self, config: dict):
        self.safe_tools = set(config.get("safe_tools", []))
        self.ask_tools = set(config.get("ask_tools", []))
        self.blocked_tools = set(config.get("blocked_tools", []))

    def check_tool(self, tool_name: str) -> PermissionDecision:
        if tool_name in self.blocked_tools:
            return PermissionDecision.DENY
        if tool_name in self.ask_tools:
            return PermissionDecision.ASK_USER
        if tool_name in self.safe_tools:
            return PermissionDecision.ALLOW
        return PermissionDecision.ASK_USER  # Default: ask

@dataclass
class PermissionDecision:
    ALLOW = "allow"
    DENY = "deny"
    ASK_USER = "ask_user"

class PermissionHook(Hook):
    event = "tool.call.before"

    def __init__(self, policy: PermissionPolicy):
        self.policy = policy

    async def execute(self, ctx: HookContext) -> bool:
        decision = self.policy.check_tool(ctx.tool_name)

        if decision == PermissionDecision.DENY:
            logger.warning(f"Tool {ctx.tool_name} is blocked by policy")
            return False

        if decision == PermissionDecision.ASK_USER:
            # 通过 ACP 请求用户授权
            result = await self.request_permission(ctx)
            return result.granted

        return True

    async def request_permission(self, ctx: HookContext) -> PermissionResult:
        """通过 ACP 请求权限"""
        acp_client = ctx.agent.deps.acp_client
        response = await acp_client.send_request(
            method="permission/request",
            params={
                "tool_name": ctx.tool_name,
                "args": ctx.tool_args,
            }
        )
        return PermissionResult(granted=response.get("granted", False))
```

### 3. Caching Hook

```python
from cachetools import TTLCache

class CacheService:
    def __init__(self, ttl: int = 3600):
        self.cache = TTLCache(maxsize=1000, ttl=ttl)

    def get_key(self, tool_name: str, args: dict) -> str:
        """生成缓存键"""
        import json
        payload = {"tool": tool_name, "args": args}
        return hashlib.sha256(json.dumps(payload).encode()).hexdigest()

    def get(self, tool_name: str, args: dict) -> Any:
        key = self.get_key(tool_name, args)
        return self.cache.get(key)

    def set(self, tool_name: str, args: dict, result: Any):
        key = self.get_key(tool_name, args)
        self.cache[key] = result

class CacheHook(Hook):
    event = "tool.call.before"

    def __init__(self, cache: CacheService):
        self.cache = cache

    async def execute(self, ctx: HookContext) -> bool:
        # 尝试从缓存获取
        cached = self.cache.get(ctx.tool_name, ctx.tool_args)
        if cached is not None:
            # 直接返回缓存结果，跳过工具执行
            ctx.tool_result = cached
            ctx.metadata["from_cache"] = True
            return False  # 中断工具执行

        return True  # 继续执行

class CacheResultHook(Hook):
    event = "tool.call.after"

    def __init__(self, cache: CacheService):
        self.cache = cache

    async def execute(self, ctx: HookContext):
        # 如果是从缓存返回的，不需要再次缓存
        if ctx.metadata.get("from_cache"):
            return

        # 缓存工具结果
        if ctx.tool_result and ctx.exception is None:
            self.cache.set(ctx.tool_name, ctx.tool_args, ctx.tool_result)
```

### 4. Rate Limiting Hook

```python
from collections import defaultdict

class RateLimiter:
    def __init__(self, limit: int = 10, window: int = 60):
        self.limit = limit
        self.window = window  # in seconds
        self.requests: defaultdict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        # 清理过期的请求记录
        self.requests[key] = [
            ts for ts in self.requests[key] if now - ts < self.window
        ]
        # 检查是否超过限制
        if len(self.requests[key]) >= self.limit:
            return False
        # 记录当前请求
        self.requests[key].append(now)
        return True

class RateLimitHook(Hook):
    event = "tool.call.before"

    def __init__(self, limiter: RateLimiter):
        self.limiter = limiter

    async def execute(self, ctx: HookContext) -> bool:
        key = f"{ctx.tool_name}:{ctx.run_context.user_id}"
        if not self.limiter.is_allowed(key):
            raise RateLimitExceededError(
                f"Tool {ctx.tool_name} rate limit exceeded"
            )
        return True
```

---

## Hook 装饰器

简化 Hook 注册的装饰器语法：

```python
def register_hook(event: str, priority: int = 100):
    """Hook 注册装饰器"""
    def decorator(cls: type[Hook]) -> type[Hook]:
        # 自动设置 event 属性
        cls.event = event

        # 注册到全局 registry
        registry.register(cls(), priority=priority)
        return cls

    return decorator

# 使用示例
@register_hook(event="tool.call.before", priority=1000)
class MyCustomHook(Hook):
    async def execute(self, ctx: HookContext):
        if ctx.tool_name == "dangerous_tool":
            logger.warning("Dangerous tool called!")
        return True
```

---

## Hook 执行的最佳实践

### 1. Hook 优先级规划

```yaml
# 建议的 Hook 优先级配置

# 安全相关（最高优先级）
permission.check: 1000
rate_limit.check: 900

# 缓存相关（中等优先级）
cache.lookup: 800
cache.store: 200

# 并发控制（中等优先级）
concurrency.control: 750

# 日志相关（低优先级）
log.request: 100
log.response: 100
log.tool_start: 100
log.tool_end: 200  # after hook，低优先级

# 监控相关（低优先级）
metrics.start: 100
metrics.end: 200
```

### 并发控制 Hook

```python
class ConcurrencyControlHook(Hook):
    """控制并发的 Hook"""

    event = "tool.call.before"

    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, ctx: HookContext) -> bool:
        # 获取信号量，限制并发的工具调用数
        try:
            await asyncio.wait_for(
                self.semaphore.acquire(),
                timeout=30.0,  # 30 秒超时
            )
        except asyncio.TimeoutError:
            raise ConcurrencyLimitExceededError(
                f"Maximum concurrent tool calls ({self.max_concurrent}) exceeded"
            )

        # 执行工具前的逻辑
        return True

    async def tool_call_after(self, ctx: HookContext):
        # 释放信号量
        if ctx.metadata.get("acquire_semaphore"):
            self.semaphore.release()
```

### 并发工具调用协调

```python
class ParallelToolCoordinatorHook(Hook):
    """协调并发工具调用的 Hook"""

    event = "agent.run.before"

    def __init__(self, agent: "XenoAgent"):
        self.agent = agent

    async def execute(self, ctx: HookContext) -> bool:
        # 检查任务是否适合并发执行
        is_parallel_candidate = self._analyze_parallel_potential(ctx)

        if is_parallel_candidate:
            # 临时启用并发
            ctx.metadata["original_parallel_setting"] = (
                self.agent.config.parallel_tool_calls
            )
            self.agent.config.parallel_tool_calls = True
        else:
            # 强制串行
            ctx.metadata["original_parallel_setting"] = (
                self.agent.config.parallel_tool_calls
            )
            self.agent.config.parallel_tool_calls = False

        return True

    async def tool_call_after(self, ctx: HookContext):
        # 恢复原始设置
        if "original_parallel_setting" in ctx.metadata:
            self.agent.config.parallel_tool_calls = ctx.metadata[
                "original_parallel_setting"
            ]
```

### 2. Hook 错误处理策略

```python
class ResilientHookRegistry(HookRegistry):
    """带错误恢复的 Hook Registry"""

    async def execute_before(self, event: str, ctx: HookContext):
        hooks = self._hooks.get(event, [])

        for priority, hook in hooks:
            try:
                result = await hook.execute(ctx)
            except Exception as e:
                # 记录错误，但不影响其他 Hook 执行
                logger.error(
                    f"Hook {hook.__class__.__name__} failed: {e}",
                    exc_info=True,
                )
                continue

        return HookResult.continue_()
```

---

## 并发工具调用 (Parallel Tool Calling)

Pydantic AI 原生支持并发工具调用，当 LLM 在一次响应中返回多个工具调用时，框架会自动并发执行。

### 默认并发行为

```python
# 模型返回多个工具调用
response = await agent.run("搜索巴黎天气和 AAPL 股价")

# Pydantic AI 自动使用 asyncio.create_task 并发执行
# Tool 1: weather_forecast (Paris)
# Tool 2: get_stock_price (AAPL)  ← 同时执行，无需等待
```

### 控制并发策略

#### 1. 工具级别：` sequential=True`

```python
@agent.tool_plain(sequential=True)  # 强制顺序执行
async def sensitive_tool(x: str) -> str:
    # 这个工具会等待其他工具完成后才执行
    # 适用于有状态依赖的工具
    return f"Processed {x}"

# 或在工具注册时配置
agent = Agent(
    model="claude-3.5-sonnet-20241022",
    tools=[Tool(sensitive_tool, sequential=True)]
)
```

#### 2. 上下文管理器：`agent.sequential_tool_calls()`

```python
async def main():
    # 整个运行期间所有工具都串行执行
    with agent.sequential_tool_calls():
        result = await agent.run("查询多个有依赖的数据")
        # 所有工具都会串行，即使模型要求并发

# 用于需要严格顺序的场景，如：
# - 有共享状态的工具
# - 有副作用且必须按顺序执行的操作
```

#### 3. Agent 设置：`parallel_tool_calls=False`

```python
agent = Agent(
    model="claude-3.5-sonnet-20241022",
    parallel_tool_calls=False,  # 全局禁用并发
)
```

### 并发工具调用与 Hooks 的集成

```python
class ParallelToolCallHook(Hook):
    """并发工具调用的 Hook 集成示例"""

    event = "tool.call.before"

    async def execute(self, ctx: HookContext) -> bool:
        # 检测是否应该并发
        should_be_parallel = self._check_parallel_requirement(ctx)

        if should_be_parallel:
            # 通过 ACP 通知并发执行计划
            # 注意：Pydantic AI 内部会使用 asyncio.create_task
            # Hook 只需记录和优化
            ctx.metadata["parallel_mode"] = True
            await self._log_parallel_plan(ctx)

        return True

    def _check_parallel_requirement(self, ctx: HookContext) -> bool:
        """判断工具是否应该并发"""
        # 1. 工具之间没有数据依赖
        # 2. 工具不会修改共享状态
        # 3. 工具执行开销较高（适合并发优化）
        return (
            ctx.metadata.get("dependencies") is None
            and ctx.tool_name not in self._stateful_tools
        )

    async def _log_parallel_plan(self, ctx: HookContext):
        """记录并发执行计划"""
        parallel_tools = ctx.metadata.get("parallel_tools", [])
        logger.info(
            f"Executing {len(parallel_tools)} tools in parallel: "
            f"{', '.join(parallel_tools)}"
        )
```

### Output Tools 的并发策略

对于 **Output Tools**（用于结构化输出而非执行），可以使用 `end_strategy` 参数：

```python
from pydantic_ai.settings import AgentSettings

settings = AgentSettings(
    end_strategy="exhaustive",  # 🔥 关键！
)

agent = Agent(
    model="gemini-2.0-flash-exp",
    settings=settings,
)

# 'exhaustive' 策略的作用：
# - 即使模型已经生成最终答案，也执行所有工具
# - 特别适用于有副作用的工具（日志、通知、metrics）
```

**示例场景**：
```python
# 模型响应：
# - "总结分析" (output tool)
# - "记录日志" (tool with side effect)
# - "发送通知" (tool with side effect)

# end_strategy='exhaustive' 确保所有工具都执行
```

### Hook 系统中的并发控制

```python
class ConcurrencyControlHook(Hook):
    """带有并发限制的 Hook"""

    event = "tool.call.before"

    def __init__(self, semaphore: asyncio.Semaphore):
        self.semaphore = semaphore

    async def execute(self, ctx: HookContext) -> bool:
        # 获取信号量，控制并发工具调用数量
        async with self.semaphore:
            # 执行工具前的逻辑
            ctx.metadata["acquire_semaphore"] = True
            return True

# 使用示例
agent = Agent(
    model="claude-3.5-sonnet-20241022",
    hooks={
        ConcurrencyControlHook(semaphore=asyncio.Semaphore(5))
    }
)
```

### ACP Bridge 中的并发支持

```python
class ACPBridgeToolset(AbstractToolset):
    """支持并发的 ACP 工具桥接"""

    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        ctx: RunContext,
    ) -> Any:
        # 1. 检查工具是否标记为strict=False（可并发）
        if self._can_run_parallel(tool_name):
            # 2. 发送多个 ACP AgentRequest
            # 3. 使用 asyncio.gather 并发等待
            requests = self._prepare_acp_requests(tool_name, args)
            responses = await asyncio.gather(*requests, return_exceptions=True)

            # 4. 聚合结果
            return self._aggregate_results(responses)
        else:
            # 串行执行
            return await self._execute_serial(tool_name, args)

    def _can_run_parallel(self, tool_name: str) -> bool:
        """检查工具是否可以并发执行"""
        return (
            tool_name not in self._sequential_only_tools
            and not self.tool_metadata[tool_name].get("sequential", False)
        )
```

---

## 性能考虑

### 1. Hook 执行时间监控

```python
import time
from collections import defaultdict

class HookMetrics:
    execution_times: defaultdict[str, list[float]] = defaultdict(list)

    @classmethod
    def record(cls, hook_class: str, duration: float):
        cls.execution_times[hook_class].append(duration)

    @classmethod
    def get_p95(cls, hook_class: str) -> float:
        times = cls.execution_times[hook_class]
        if not times:
            return 0.0
        times.sort()
        return times[int(len(times) * 0.95)]

async def execute_hook_with_metrics(hook: Hook, ctx: HookContext):
    start = time.time()
    try:
        result = await hook.execute(ctx)
    finally:
        duration = time.time() - start
        HookMetrics.record(hook.__class__.__name__, duration)

        # 警告慢 Hook
        p95 = HookMetrics.get_p95(hook.__class__.__name__)
        if duration > p95 * 2:
            logger.warning(
                f"Hook {hook.__class__.__name__} slow: {duration:.3f}s (p95: {p95:.3f}s)"
            )
```

### 2. Hook 异步优化

```python
# 并行执行无依赖的 Hooks
async def execute_hooks_parallel(hooks: list[Hook], ctx: HookContext):
    tasks = [hook.execute(ctx) for hook in hooks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for hook, result in zip(hooks, results):
        if isinstance(result, Exception):
            logger.error(f"Hook {hook.__class__} failed: {result}")
```

---

## 测试策略

### 1. Hook 单元测试

```python
import pytest

@pytest.mark.asyncio
async def test_permission_hook_denies_blocked_tool():
    policy = PermissionPolicy({"blocked_tools": ["dangerous_tool"]})
    hook = PermissionHook(policy)

    ctx = HookContext(
        agent=agent,
        run_context=run_context,
        event="tool.call.before",
        tool_name="dangerous_tool",
        tool_args={},
    )

    result = await hook.execute(ctx)
    assert result is False
```

### 2. Hook 集成测试

```python
@pytest.mark.asyncio
async def test_hook_chain_execution():
    registry = HookRegistry()

    # 注册多个 Hook
    registry.register(PermissionHook(policy), priority=1000)
    registry.register(CacheHook(cache), priority=800)
    registry.register(LoggingHook(logger), priority=100)

    # 执行 Hook 链
    result = await registry.execute_before("tool.call.before", ctx)
    assert result.continue_ is False  # PermissionHook should deny
```

---

## 配置示例

```yaml
# config/hooks.yaml
hooks:
  # 权限控制
  - type: permission
    priority: 1000
    config:
      policy_file: config/permission.yaml
      fallback: ask_user

  # 速率限制
  - type: rate_limit
    priority: 900
    config:
      limit: 10
      window: 60

  # 缓存
  - type: cache
    priority: 800
    config:
      ttl: 3600

  # 日志
  - type: logging
    priority: 100
    config:
      level: INFO
      output: logs/agent.log
```

---

## 开放问题

1. **Hook 并发**: 当多个 Agent 实例共享 Hook Registry 时，如何处理并发？
2. **Hook 动态加载**: 是否支持运行时动态注册/卸载 Hook？
3. **Hook 配置热更新**: Hook 修改后是否可以不重启 Agent 实例？
4. **Hook 追踪**: 是否需要分布式追踪（如 OpenTelemetry）来追踪 Hook 执行链？

---

## 参考资料

- [RFC 005: 系统架构](./005_system_architecture.md)
- [pydantic-ai-middleware](https://github.com/pydantic-ai/pydantic-ai-middleware)
- [ASGI Middleware](https://asgi.readthedocs.io/)
