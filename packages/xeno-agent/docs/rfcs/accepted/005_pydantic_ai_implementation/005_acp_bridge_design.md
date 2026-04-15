# RFC 005.2: ACP 协议桥接设计

## 状态
**状态**: Draft
**创建日期**: 2026-01-20
**作者**: Sisyphus
**最后更新**: 2026-01-20

---

## 概述

本文档描述 Xeno Agent 如何通过 Hook 系统桥接到 ACP（Agent Client Protocol），实现工具调用的标准化通信。

---

## 设计目标

1. **协议透明**: Pydantic AI 的工具调用无缝转换为 ACP 消息
2. **双向通信**: 支持 Agent → Client 的请求和 Client → Agent 的响应
3. **Session 同步**: 维护 ACP Session 状态与 Agent Session 的一致性
4. **Tool 生命周期**: 正确映射 Tool Call 的 pending/in_progress/completed 状态
5. **扩展性**: 支持 ACP 的 ExtRequest/ExtNotification 机制

---

## ACP 协议回顾

### 核心消息类型

```json
// Client → Agent (Request)
{
  "jsonrpc": "2.0",
  "method": "prompt/message",
  "params": {
    "session": {...},
    "prompt": {...}
  },
  "id": "req-001"
}

// Agent → Client (Response)
{
  "jsonrpc": "2.0",
  "result": {...},
  "id": "req-001"
}

// Agent → Client (Notification - session/update)
{
  "jsonrpc": "2.0",
  "method": "session/update",
  "params": {
    "session_id": "...",
    "status": "in_progress",
    "content": [...]
  }
}

// Agent → Client (Request - Tool Call)
{
  "jsonrpc": "2.0",
  "method": "agent/request",
  "params": {
    "method": "tool.call",
    "params": {...}
  },
  "id": "req-tool-001"
}
```

### Tool Call 生命周期

```
1. Agent decides to use tool
   ↓
2. Agent sends AgentRequest (tool.call) to Client
   → Status: pending
   ↓
3. Client receives and starts execution
   → Agent sends session/update (tool_call: in_progress)
   ↓
4. Tool executes
   ↓
5. Agent receives AgentResponse (result or error)
   → Status: completed / failed
```

---

## 架构设计

### ACP Bridge 层次结构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Pydantic AI Agent                           │
│  - Tool Call Execution                                           │
│  - Runs tool through toolsets                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ACPBridgeToolset                              │
│  - Implements AbstractToolset                                    │
│  - tools(ctx): List available tools from ACP Client            │
│  - execute_tool(tool_name, args): Execute via ACP                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ACPBridge Hooks                                │
│  - tool.call.before: Notify ACP (tool_call: pending)           │
│  - tool.call.after: Notify ACP (tool_call: completed)          │
│  - session/update: Handle progress notifications                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ACP Client (SDK)                             │
│  - send_request(method, params)                                  │
│  - send_notification(method, params)                            │
│  - register_handler(method, callback)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Client (External)                            │
│  - Handles tool requests                                         │
│  - Sends back results                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. ACPBridgeToolset

**职责**: 将 ACP 客户端的工具桥接到 Pydantic AI

```python
from pydantic_ai import Agent, AbstractToolset, RunContext, Tool
from typing import AsyncIterator

class ACPBridgeToolset(AbstractToolset):
    """桥接 ACP 工具到 Pydantic AI"""

    def __init__(self, acp_client: ACPClient):
        self.acp_client = acp_client
        self._tool_cache: dict[str, Tool] = {}

    async def tools(self, ctx: RunContext) -> AsyncIterator[Tool]:
        """
        运行时获取 ACP 可用工具列表

        流程:
        1. 向 ACP Client 请求工具列表
        2. 转换为 Pydantic AI Tool 定义
        3. 注册 Hook: tool.call.before → 通知 ACP
        4. 注册 Hook: tool.call.after → 更新状态
        """
        # 从 ACP 获取工具列表
        acp_tools = await self.acp_client.get_available_tools()

        for acp_tool in acp_tools:
            tool = self._convert_tool(acp_tool)
            yield tool

            # 缓存工具元数据（用于 Hook）
            self._tool_cache[acp_tool.name] = tool

    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        ctx: RunContext,
    ) -> Any:
        """
        通过 ACP 执行工具

        流程:
        1. 发送 AgentRequest (tool.call) 到 ACP Client
        2. 等待 AgentResponse
        3. 处理错误，转换结果格式
        4. 返回结果
        """
        # Step 1: 发送工具调用请求
        request_id = f"tool-{uuid.uuid4()}"

        await self.acp_client.send_request(
            method="agent/request",
            params={
                "id": request_id,
                "method": tool_name,
                "params": args,
            },
        )

        # Step 2: 等待 ACP 响应 (使用 future/event)
        response = await self.acp_client.wait_for_response(request_id)

        # Step 3: 处理结果
        if "error" in response:
            raise ToolExecutionError(
                tool_name,
                response["error"],
            )

        return response["result"]

    def _convert_tool(self, acp_tool:ACPTool) -> Tool:
        """将 ACP 工具转换为 Pydantic AI Tool"""
        return Tool(
            name=acp_tool.name,
            description=acp_tool.description,
            parameters_json_schema=acp_tool.input_schema,
        )
```

### 2. ACP Bridge Hooks

**职责**: 生命周期通知和状态同步

```python
class ACPBridgeHooks:
    """ACP 桥接相关的 Hook"""

    def __init__(self, acp_client: ACPClient, toolset: ACPBridgeToolset):
        self.acp_client = acp_client
        self.toolset = toolset

    async def tool_call_before(self, ctx: HookContext) -> bool:
        """
        工具调用前的 Hook

        功能:
        1. 向 ACP 发送 session/update (tool_call: pending)
        2. 记录工具调用元数据
        """
        if ctx.tool_name not in self.toolset._tool_cache:
            return True  # 非 ACP 工具，跳过

        # 发送通知: tool_call pending
        await self.acp_client.send_notification(
            method="session/update",
            params={
                "tool_call": {
                    "id": self._generate_call_id(ctx),
                    "name": ctx.tool_name,
                    "args": ctx.tool_args,
                    "status": "pending",
                    "timestamp": time.time(),
                }
            }
        )

        return True  # 继续执行

    async def tool_call_started(self, ctx: HookContext):
        """
        工具执行开始的 Hook

        通知 ACP: tool_call in_progress
        """
        if ctx.tool_name not in self.toolset._tool_cache:
            return

        await self.acp_client.send_notification(
            method="session/update",
            params={
                "tool_call": {
                    "id": self._get_call_id(ctx),
                    "status": "in_progress",
                }
            }
        )

    async def tool_call_after(self, ctx: HookContext):
        """
        工具调用后的 Hook

        功能:
        1. 向 ACP 发送 session/update (tool_call: completed/failed)
        2. 记录执行时间
        3. 处理错误情况
        """
        if ctx.tool_name not in self.toolset._tool_cache:
            return

        status = "completed" if ctx.exception is None else "failed"

        await self.acp_client.send_notification(
            method="session/update",
            params={
                "tool_call": {
                    "id": self._get_call_id(ctx),
                    "status": status,
                    "result": ctx.tool_result if status == "completed" else None,
                    "error": str(ctx.exception) if status == "failed" else None,
                    "duration": ctx.metadata.get("duration", 0),
                }
            }
        )

    def _generate_call_id(self, ctx: HookContext) -> str:
        """生成唯一的工具调用 ID"""
        return f"{ctx.run_context.session_id}-{ctx.tool_name}-{uuid.uuid4().hex[:8]}"

    def _get_call_id(self, ctx: HookContext) -> str:
        """从 metadata 获取工具调用 ID"""
        return ctx.metadata.get("call_id", "")
```

### 3. ACP Client 包装

**职责**: ACP 协议的底层通信

```python
import asyncio
from typing import Any, Callable

class ACPClient:
    """ACP 客户端适配器"""

    def __init__(self, transport: "Transport"):
        self.transport = transport
        self.request_handlers: dict[str, Callable] = {}
        self.pending_requests: dict[str, Awaitable[Any]] = {}

    async def send_request(
        self,
        method: str,
        params: dict,
        id: str | None = None,
    ) -> dict:
        """
        发送 JSON-RPC 2.0 请求

        Returns:
            响应结果 (result 或 error)
        """
        request_id = id or str(uuid.uuid4())

        # 创建 future
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        # 发送请求
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": request_id,
        }
        await self.transport.send(message)

        # 等待响应
        response = await future
        return response

    async def send_notification(
        self,
        method: str,
        params: dict,
    ):
        """
        发送 JSON-RPC 2.0 通知 (无 ID，无响应)
        """
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        await self.transport.send(message)

    async def wait_for_response(
        self,
        request_id: str,
        timeout: float = 30.0,
    ) -> dict:
        """等待指定请求的响应"""
        try:
            return await asyncio.wait_for(
                self.pending_requests[request_id],
                timeout=timeout,
            )
        finally:
            self.pending_requests.pop(request_id, None)

    def register_handler(
        self,
        method: str,
        handler: Callable,
    ):
        """注册请求/通知处理器"""
        self.request_handlers[method] = handler

    async def get_available_tools(self) -> list[ACPTool]:
        """
        获取 ACP 可用工具列表

        实现:
        1. 向 Client 请求 tools/list
        2. 解析响应，转换工具定义
        """
        response = await self.send_request(
            method="client/request",
            params={
                "method": "tools/list",
                "params": {},
            },
        )

        return [
            ACPTool(**tool_data)
            for tool_data in response["result"]["tools"]
        ]

    async def handle_message(self, message: dict):
        """处理收到的消息（响应或请求）"""
        # 处理响应
        if "id" in message:
            if "result" in message or "error" in message:
                # 这是对我们请求的响应
                future = self.pending_requests.get(message["id"])
                if future:
                    future.set_result(message)
            else:
                # 这是一个客户端发来的请求
                await self._handle_client_request(message)
        # 处理通知
        else:
            await self._handle_client_notification(message)

    async def _handle_client_request(self, message: dict):
        """处理 Client 发来的请求"""
        method = message["method"]
        handler = self.request_handlers.get(method)

        if handler:
            try:
                result = await handler(message["params"])
                # 发送响应
                await self.transport.send({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": message["id"],
                })
            except Exception as e:
                await self.transport.send({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": str(e),
                    },
                    "id": message["id"],
                })

    async def _handle_client_notification(self, message: dict):
        """处理 Client 发来的通知"""
        method = message["method"]
        handler = self.request_handlers.get(method)

        if handler:
            await handler(message["params"])
```

### 4. Transport 抽象

**职责**: 底层通信协议实现（stdio/WebSocket/HTTP）

```python
from abc import ABC, abstractmethod

class Transport(ABC):
    """传输层抽象"""

    @abstractmethod
    async def send(self, message: dict):
        """发送消息"""
        pass

    @abstractmethod
    async def receive(self) -> dict:
        """接收消息"""
        pass

class StdioTransport(Transport):
    """Stdio 传输（用于 CLI 工具）"""

    def __init__(self, stdin: TextIO, stdout: TextIO):
        self.stdin = stdin
        self.stdout = stdout

    async def send(self, message: dict):
        import json
        line = json.dumps(message)
        self.stdout.write(line + "\n")
        self.stdout.flush()

    async def receive(self) -> dict:
        import json
        line = await asyncio.to_thread(self.stdin.readline)
        return json.loads(line.strip())

class WebSocketTransport(Transport):
    """WebSocket 传输（用于 Web 客户端）"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def send(self, message: dict):
        import json
        await self.websocket.send_text(json.dumps(message))

    async def receive(self) -> dict:
        import json
        text = await self.websocket.receive_text()
        return json.loads(text)
```

---

## 数据流映射

### Tool Call 完整流程

```
[Pydantic AI Agent]
    │
    │ 1. Model 决定调用工具: "web_search"
    │
    ▼
[tool.call.before Hook]
    │
    ├─→ [ACPBridgeHooks.tool_call_before]
    │       │
    │       └─→ ACP Client: Send Notification
    │           Method: session/update
    │           Params: {tool_call: {status: "pending"}}
    │
    ▼
[ACPBridgeToolset.execute_tool]
    │
    ├─→ 2. 发送 AgentRequest
    │       Method: agent/request
    │       Params: {method: "web_search", args: {...}}
    │
    │   [Transport Layer]
    │       │
    │       ▼
    │   [External Client]
    │       │
    │       ├─→ 收到 AgentRequest
    │       │
    │       ├─→ 开始执行工具
    │       │
    │       └─→ [ACP Client] receives: session/update
    │           Method: session/notification
    │           Params: {tool_call: {status: "in_progress"}}
    │
    │   [Transport Layer]
    │       │
    ▼
[ACP Client receives AgentResponse]
    │
    ├─→ 3. 等待响应 (future)
    │
    │   [Transport Layer]
    │       │
    ▼
[tool.call.before Hook (started)]
    │
    ├─→ [ACPBridgeHooks.tool_call_started]
    │       └─→ ACP Client: Send Notification
    │           Method: session/update
    │           Params: {tool_call: {status: "in_progress"}}
    │
    ▼
[Tool Execution ...]
    │
    │   4. 工具执行完成
    │
    ▼
[Response Received]
    │
    ├─→ 5. 解析结果
    │
    ▼
[tool.call.after Hook]
    │
    ├─→ [ACPBridgeHooks.tool_call_after]
    │       │
    │       └─→ ACP Client: Send Notification
    │           Method: session/update
    │           Params: {tool_call: {status: "completed", result: {...}}
    │
    ▼
[Pydantic AI Agent]
    │
    └─→ 6. 将结果返回给 Model
```

---

## ACP 扩展支持

### ExtRequest / ExtNotification

ACP 协议支持扩展方法（`ext/*`），Xeno Agent 通过 Hook 系统支持自定义扩展：

```python
class ExtRequestHandlerHook(Hook):
    event = "ext.request"

    async def execute(self, ctx: HookContext) -> Any:
        """
        处理自定义扩展请求

        示例:
        - custom/analytics
        - custom/debug
        - custom/config_reload
        """
        ext_method = ctx.metadata.get("ext_method")
        handler = self.ext_handlers.get(ext_method)

        if handler:
            return await handler(ctx.metadata.get("params"))

        raise NotImplementedError(f"Unknown extension: {ext_method}")
```

### 扩展注册

```python
acp_client.register_handler(
    method="custom/analytics",
    handler=lambda params: analytics_service.report(params),
)
```

---

## 配置

### ACP Bridge 配置

```yaml
# config/acp_bridge.yaml
transport:
  type: "stdio"  # or "websocket", "http"

# ACP Client 配置
client:
  timeout: 30.0
  retry:
    max_attempts: 3
    delay: 1.0

# 工具桥接配置
toolset:
  enabled: true
  namespace: "acp"  # 工具命名空间前缀
  timeout: 60.0

# Hook 配置
hooks:
  enabled: true
  notifications:
    - tool_call.pending
    - tool_call.in_progress
    - tool_call.completed
    - tool_call.failed
```

---

## 错误处理

### 错误映射表

| ACP Error | Pydantic AI Exception | 处理策略 |
|-----------|----------------------|----------|
| `-32700` (Parse error) | `JSONRPCParseError` | 返回 Model，要求重试 |
| `-32600` (Invalid Request) | `JSONRPCInvalidRequest` | 返回 Model，修正格式 |
| `-32601` (Method not found) | `ToolNotFoundError` | 通知 Model 工具不存在 |
| `-32602` (Invalid params) | `ToolValidationError` | 通知 Model 参数错误 |
| `-32603` (Internal error) | `ToolInternalError` | 返回 Model，提示用户 |
| 自定义错误 | `ToolExecutionError` | 传递错误消息给 Model |

### 错误恢复策略

```python
class ErrorRecoveryHook(Hook):
    event = "tool.call.after"

    async def execute(self, ctx: HookContext):
        if ctx.exception is None:
            return

        # 记录错误
        logger.error(
            f"Tool {ctx.tool_name} failed: {ctx.exception}",
            exc_info=True,
        )

        # 根据错误类型决定是否重试
        if isinstance(ctx.exception, ToolTimeoutError):
            # 建议重试
            ctx.tool_result = {
                "error": "Timeout",
                "suggestion": "Try again with longer timeout",
            }
        elif isinstance(ctx.exception, ToolNotFoundError):
            # 返回 Model 让其尝试其他工具
            ctx.tool_result = {
                "error": "Tool not found",
                "suggestion": "Try a different tool",
            }
```

---

## 性能优化

### 1. 并发工具调用支持

Pydantic AI 支持 **Native 并发工具调用**，ACP Bridge 应该适配这一特性。

#### ACP 级标支持

```yaml
# config/acp_bridge.yaml
toolset:
  enabled: true
  parallel_tool_calls: true  # 启用并发支持
  max_concurrent: 10  # 最大并发数
```

#### 并发执行策略

```python
class ParallelACPBridgeToolset(ACPBridgeToolset):
    """支持并发的 ACP Bridge Toolset"""

    def __init__(self, acp_client: ACPClient, max_concurrent: int = 10):
        super().__init__(acp_client)
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute_tool(
        self,
        tool_name: str,
        args: dict,
        ctx: RunContext,
    ) -> Any:
        # 如果需要串行，使用父类逻辑
        if self._is_sequential_tool(tool_name):
            return await super().execute_tool(tool_name, args, ctx)

        # 并发执行多个 ACP 工具调用
        # 注意：Pydantic AI 层已在需要时并发执行多个工具
        # 这里处理单个工具内部的并发操作（如批量查询）
        return await self._execute_with_concurrency(tool_name, args)

    async def _execute_with_concurrency(self, tool_name: str, args: dict) -> Any:
        """带并发控制的工具执行"""
        async with self.semaphore:
            # 发送 ACP AgentRequest
            response = await self.acp_client.send_request(
                method="agent/request",
                params={
                    "method": tool_name,
                    "params": args,
                    "concurrent": True,  # 标记为并发调用
                },
            )

            return response["result"]
```

#### Hook 集成：并发通知

```python
class ParallelACPHook(ACPBridgeHooks):
    """处理并发工具调用的 Hook"""

    async def tool_call_before(self, ctx: HookContext) -> bool:
        # 检查是否为批量工具调用
        is_batch = ctx.metadata.get("batch_tool_calls", False)

        if is_batch:
            # 批量通知：一次通知多个 pending 状态
            batch_ids = ctx.metadata.get("batch_tool_ids", [])
            await self.acp_client.send_notification(
                method="session/batch_update",
                params={
                    "tool_calls": [
                        {
                            "id": call_id,
                            "status": "pending",
                            "tool": ctx.tool_name,
                        }
                        for call_id in batch_ids
                    ]
                }
            )
        else:
            # 单个工具调用使用原有逻辑
            return await super().tool_call_before(ctx)

        return True
```

### 2. 批量工具调用优化

```python
class BatchOptimizedACPToolset(ACPBridgeToolset):
    """批量优化的 ACP 工具集"""

    async def execute_many(
        self,
        calls: list[tuple[str, dict]],
        ctx: RunContext,
    ) -> list[Any]:
        """
        批量执行多个工具调用

        相比逐个调用，批量调用效率更高：
        - 减少 ACP Client 连接开销
        - 并发所有工具调用
        - 批量通知状态
        """
        # 1. 准备批量 ACP AgentRequest
        requests = [
            {
                "method": tool_name,
                "params": args,
            }
            for tool_name, args in calls
        ]

        # 2. 批量发送请求（如果 ACP 支持批量接口）
        # 否则使用 asyncio.gather 并发发送
        responses = await asyncio.gather(
            *[
                self.acp_client.send_request(
                    method="agent/request",
                    params=req,
                )
                for req in requests
            ],
            return_exceptions=True,
        )

        return responses
```

### 3. 工具列表缓存



```python
class CachedACPBridgeToolset(ACPBridgeToolset):
    def __init__(self, acp_client: ACPClient, cache_ttl: int = 300):
        super().__init__(acp_client)
        self.cache_ttl = cache_ttl
        self._tools_cache_time: float = 0

    async def tools(self, ctx: RunContext) -> AsyncIterator[Tool]:
        now = time.time()

        # 缓存未过期，直接返回
        if now - self._tools_cache_time < self.cache_ttl:
            for tool in self._tools.values():
                yield tool
            return

        # 重新加载工具列表
        await self._reload_tools()
        self._tools_cache_time = now

        for tool in self._tools.values():
            yield tool
```

### 2. 并行工具调用

```python
class ParallelACPBridgeToolset(ACPBridgeToolset):
    """支持并行工具调用的 ACP Toolset"""

    async def execute_many(
        self,
        calls: list[tuple[str, dict]],
        ctx: RunContext,
    ) -> list[Any]:
        """
        并行执行多个工具调用
        """
        tasks = [
            self.execute_tool(tool_name, args, ctx)
            for tool_name, args in calls
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 测试

### 单元测试

```python
import pytest

@pytest.mark.asyncio
async def test_acp_bridge_toolset_tool_conversion():
    acp_client = MockACPClient()
    toolset = ACPBridgeToolset(acp_client)

    acp_tool = ACPTool(
        name="web_search",
        description="Search the web",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        },
    )

    pydantic_tool = toolset._convert_tool(acp_tool)

    assert pydantic_tool.name == "web_search"
    assert pydantic_tool.description == "Search the web"
    assert pydantic_tool.parameters_json_schema == acp_tool.input_schema

@pytest.mark.asyncio
async def test_acp_bridge_tool_execution():
    acp_client = MockACPClient()
    toolset = ACPBridgeToolset(acp_client)

    # 模拟工具执行
    acp_client.add_response(
        "agent/request",
        {"result": {"status": "success", "data": "..."}},
    )

    ctx = MockRunContext()
    result = await toolset.execute_tool("web_search", {"query": "test"}, ctx)

    assert result["status"] == "success"
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_full_acp_integration():
    # Setup
    transport = StdioTransport(mock_stdin, mock_stdout)
    acp_client = ACPClient(transport)
    toolset = ACPBridgeToolset(acp_client)

    # Register hooks
    hooks = ACPBridgeHooks(acp_client, toolset)

    # Execute
    tools_async = toolset.tools(ctx=mock_run_context)
    tools = [tool async for tool in tools_async]

    # Verify
    assert len(tools) > 0
    assert any(t.name == "web_search" for t in tools)
```

---

## 开放问题

1. **传输层选择**: 当前的 Transport 支持单一协议，是否支持多协议切换？
2. **Session 管理**: 是否需要维护 Session 状态到数据库？
3. **工具调用链**: 如果工具调用链很长（工具调用工具），如何处理？
4. **权限映射**: ACP 的 permission.request 如何映射到本地Hook 系统？

---

## 参考资料

- [RFC 005: 系统架构](./005_system_architecture.md)
- [Agent Client Protocol](https://agentclientprotocol.com/)
- [ACP Python SDK](https://github.com/anthropics/agent-client-protocol-python)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
