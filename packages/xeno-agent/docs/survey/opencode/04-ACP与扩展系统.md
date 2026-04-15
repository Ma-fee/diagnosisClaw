# ACP 与扩展系统设计

## ACP (Agent Client Protocol)

### 什么是 ACP

ACP 是 OpenCode 实现的一套用于 **Agent 客户端** 和 **Agent 服务器** 之间通信的开放协议。它基于 JSON-RPC，旨在标准化 AI Agent 的交互接口，使其具有互操作性。

OpenCode 既是 ACP Server（提供智能服务），也是 ACP Client（可以连接其他 ACP Server）。

### 核心协议定义

ACP 定义了以下关键能力：

1. **Session 管理**: 创建、恢复、配置会话
2. **工具交互**: 列出工具、调用工具、接收结果
3. **消息流**: 实时推送文本、推理过程、工具调用
4. **状态同步**: 同步工作目录、环境变量等上下文

### OpenCode 中的 ACP 实现

**文件位置**: `packages/opencode/src/acp/`

#### 1. Agent 实现 (`acp/agent.ts`)

```typescript
export class OpenCodeAgent implements Agent {
  // 初始化，声明能力
  async initialize(params: InitializeParams) {
    return {
      version: "1.0.0",
      capabilities: { ... }
    }
  }

  // 创建会话
  async newSession(params: NewSessionParams) {
    // 1. 在内部创建 Session
    const session = await Session.create({ ... })

    // 2. 映射为 ACP Session
    const acpSession = new OpenCodeSession(session, params)

    // 3. 订阅事件，实现双向同步
    this.setupEventSubscriptions(session, acpSession)

    return acpSession
  }
}
```

#### 2. Session 适配 (`acp/session.ts`)

将内部的 `Session` 对象适配为 ACP 协议要求的接口：

```typescript
class OpenCodeSession {
  // 处理用户提示
  async prompt(params: PromptParams) {
    // 1. 转换输入 (Text/Image/Resource)
    const content = this.convertInput(params.content);

    // 2. 调用内部 prompt
    await SessionPrompt.prompt(this.session, content);

    // 3. 结果通过事件流返回，不在此处直接返回
  }
}
```

#### 3. 工具映射

ACP 定义了一套标准工具类型，OpenCode 内部工具会被映射过去：

```typescript
function toToolKind(name: string): ToolKind {
  if (name === "bash") return "execute";
  if (name === "read") return "read";
  if (name === "write" || name === "edit") return "edit";
  if (name === "webfetch") return "fetch";
  // ...
  return "other";
}
```

### 为什么需要 ACP？

1. **解耦**: 允许 CLI、VS Code 插件、Web 界面等多种客户端连接同一个核心引擎
2. **互操作**: 任何支持 ACP 的 IDE 都可以直接使用 OpenCode
3. **远程开发**: 支持在远程服务器运行 Agent，本地只运行轻量客户端

## 插件系统

OpenCode 的插件系统设计非常灵活，支持通过钩子（Hooks）介入系统的各个生命周期。

### 插件加载源

1. **内置插件**: 系统自带的核心插件
2. **配置插件**: `config.plugin` 中定义的 npm 包
3. **本地插件**: `.opencode/plugin/*.js` 或 `~/.config/opencode/plugin/*.js`

### 插件接口

```typescript
interface Plugin {
  name: string;
  hooks?: {
    config?: (config: Config) => Config | Promise<Config>;

    permission?: {
      ask?: (
        info: Info,
        ctx: Context,
      ) => Promise<{ status: "allow" | "deny" | "ask" }>;
    };

    tool?: {
      register?: (registry: Registry) => void | Promise<void>;
      execute?: (info: ToolInfo, ctx: Context) => void | Promise<void>;
    };

    event?: {
      subscribe?: (bus: Bus) => void;
    };

    // 更多生命周期...
  };
}
```

### 插件运行时 (`BunProc`)

为了安全和隔离，插件通常作为 npm 包安装。OpenCode 使用 `BunProc` 来管理插件进程或加载逻辑。

```typescript
// 安装插件
await BunProc.install("opencode-plugin-security");

// 加载插件
const plugin = await import("opencode-plugin-security");
```

### 内置插件示例

#### 1. `CodexAuthPlugin`

- 处理 OpenCode 官方服务的认证
- 注入 token 到 HTTP 请求头

#### 2. `CopilotAuthPlugin`

- 处理 GitHub Copilot 的认证
- 拦截请求并添加 Copilot 特有的 headers

### 插件触发机制

插件钩子是**顺序执行**的：

```typescript
// plugin/index.ts
async function trigger<K extends keyof Hooks>(hookName: K, ...args: any[]) {
  for (const plugin of plugins) {
    if (plugin.hooks?.[hookName]) {
      await plugin.hooks[hookName](...args);
    }
  }
}
```

## 事件总线 (Bus)

OpenCode 采用事件驱动架构，通过 `Bus` 实现组件解耦。

### 全局总线

```typescript
import { bus } from "./bus";

// 发布事件
bus.emit("session.created", { id: "123" });

// 订阅事件
bus.on("session.created", (event) => {
  console.log("New session:", event.id);
});
```

### 事件类型

- `session.*`: 会话生命周期 (created, updated, removed)
- `message.*`: 消息变更 (created, updated)
- `tool.*`: 工具执行 (call, result, error)
- `permission.*`: 权限请求 (asked, granted, denied)
- `config.*`: 配置变更

### 跨实例通信

Bus 设计支持跨进程或跨实例通信（通过 SSE 或 WebSocket 桥接），这对于客户端/服务器架构至关重要。

## MCP (Model Context Protocol) 集成

OpenCode 不仅实现了 ACP，还深度集成了 Anthropic 提出的 MCP。

### 双重角色

1. **MCP Client**: OpenCode 可以连接外部 MCP Server（如 GitHub, PostgreSQL），将其工具暴露给 Agent 使用。
   - `mcp-router` 工具负责转发请求
2. **MCP Server**: OpenCode 也可以作为 MCP Server 运行，向其他 LLM 应用（如 Claude Desktop）暴露其文件操作和 bash 能力。

### 实现方式

```typescript
// 自动桥接
// 将发现的 MCP 工具注册为 OpenCode 工具
for (const tool of mcpClient.tools) {
  Tool.define(`mcp-router_${tool.name}`, {
    // ...
    execute: async (args) => {
      return mcpClient.callTool(tool.name, args);
    },
  });
}
```

这种双向协议支持使得 OpenCode 处于 AI 生态系统的连接中心位置。
