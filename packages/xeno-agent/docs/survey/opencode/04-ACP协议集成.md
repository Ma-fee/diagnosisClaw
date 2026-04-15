# ACP 协议集成

## 什么是 ACP

ACP (Agent Client Protocol) 是一个用于连接 AI 代理（Server）和客户端（Client）的标准协议。OpenCode 既实现了 ACP Server（供客户端连接），也作为 ACP Client（连接其他 MCP 服务器）。

**核心价值**: 解耦智能层与展示层，使得同一个 Agent 逻辑可以服务于 TUI、Web、Desktop、IDE 插件等多种前端。

## ACP 架构

```
┌──────────────┐      SSE / WebSocket      ┌──────────────┐
│  ACP Client  │ <───────────────────────> │  ACP Server  │
│ (TUI/Web/IDE)│      JSON-RPC 2.0         │  (OpenCode)  │
└──────────────┘                           └──────┬───────┘
                                                  │
                                           ┌──────▼───────┐
                                           │  Agent Logic │
                                           └──────────────┘
```

## 协议能力

OpenCode 实现了 ACP 的全套核心能力：

### 1. 初始化 (Initialize)

```typescript
// Client -> Server
{
  method: "initialize",
  params: {
    clientInfo: { name: "opencode-tui", version: "1.0.0" },
    capabilities: { roots: { listChanged: true } }
  }
}

// Server -> Client
{
  result: {
    serverInfo: { name: "opencode", version: "1.1.25" },
    capabilities: {
      prompts: {},
      resources: {},
      tools: {}
    }
  }
}
```

### 2. 工具调用 (Tool Usage)

ACP 将工具调用标准化为 `tools/call` 请求：

```typescript
// Client -> Server (用户请求执行工具)
// 或者 Server -> Client (Agent 请求执行客户端工具)
{
  method: "tools/call",
  params: {
    name: "read",
    arguments: { filePath: "/path/to/file.ts" }
  }
}
```

**关键映射**:
OpenCode 将内部的 `Tool` 映射为 ACP 的 Tool 定义：

- `name` -> `name`
- `description` -> `description`
- `parameters` (Zod) -> `inputSchema` (JSON Schema)

### 3. 会话管理 (Session Management)

ACP 引入了 Session 概念，OpenCode 将其映射到内部的 Session：

- `session/create`: 创建新会话
- `session/load`: 加载历史会话
- `session/list`: 列出会话列表

### 4. 实时更新 (Real-time Updates)

通过 `notifications` 推送状态变更：

- `agent/message`: 推送文本增量 (Text Delta)
- `agent/thought`: 推送思考过程 (Reasoning Delta)
- `tool/update`: 推送工具执行状态

## 实现细节

### ACP Agent 适配器

文件: `packages/opencode/src/acp/agent.ts`

此类将 OpenCode 的内部逻辑包装为 ACP 兼容的 Agent：

```typescript
export class ACPAgent implements AgentInterface {
  // 处理用户 Prompt
  async prompt(request: PromptRequest) {
    // 1. 获取/创建 Session
    const session = await this.sessionManager.get(request.sessionID)

    // 2. 将 ACP 消息转换为 OpenCode 消息
    // ...

    // 3. 执行 Prompt 循环
    await SessionPrompt.prompt(session, input)
  }

  // 监听内部事件并转换为 ACP 通知
  private setupEventSubscriptions(connection: Connection) {
    // 监听工具更新
    this.bus.subscribe("message.part.updated", (event) => {
      connection.sendNotification("tool/update", { ... })
    })

    // 监听权限请求
    this.bus.subscribe("permission.asked", (event) => {
      connection.sendNotification("agent/permission", { ... })
    })
  }
}
```

### 工具类型映射

OpenCode 的工具在通过 ACP 暴露时，会附带 `kind` 属性，帮助客户端渲染不同的 UI：

```typescript
function toToolKind(name: string): ToolKind {
  if (name === "bash") return "execute";
  if (name === "webfetch") return "fetch";
  if (name === "edit" || name === "write") return "edit";
  if (name.includes("search") || name === "grep") return "search";
  if (name === "read") return "read";
  return "other";
}
```

## 与 MCP (Model Context Protocol) 的关系

OpenCode 既是 ACP Server，也是 MCP Client：

1. **ACP**: 用于连接前端（UI）
2. **MCP**: 用于连接后端能力（Tools/Resources）

OpenCode 可以加载 MCP Server，并将其工具暴露给 Agent 使用。

```typescript
// 配置 MCP Servers
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    }
  }
}
```

系统会自动为加载的 MCP Server 创建对应的 OpenCode Tool 包装器。

## 优势

1. **前端无关性**: CLI、Web、VSCode 插件共享同一套核心逻辑
2. **远程开发**: 协议支持网络传输，天然支持远程模式
3. **标准化**: 基于 JSON-RPC 2.0，易于调试和实现
4. **互操作性**: 遵循 ACP 标准，可与其他 ACP 兼容工具互通
