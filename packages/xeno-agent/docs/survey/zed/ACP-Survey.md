# Zed 编辑器 ACP (Agent Client Protocol) 深度技术调研报告

## 1. ACP 协议概述

### 协议版本
- **当前实现版本**: `agent-client-protocol = 0.9.3`
- **协议描述**: Agent Client Protocol (ACP) 是用于标准化代码编辑器和 AI coding agents 之间通信的开放协议
- **官方站点**: https://agentclientprotocol.com
- **Rust SDK**: https://github.com/agentclientprotocol/rust-sdk
- **最小支持版本**: ProtocolVersion::V1（代码中硬编码）

### 设计理念
Zed 通过 ACP 实现了 agent 的插件化架构：
1. **Zed 作为 ACP Client** - 负责用户界面、文件编辑、项目管理
2. **外部程序作为 ACP Server** - 负责 AI 推理、工具调用、任务执行
3. **通信方式** - 通过 stdin/stdout 进行 JSON-RPC 风格的消息交换

---

## 2. 支持的接口清单

### 2.1 核心连接接口 (从 acp.rs 和 connection.rs)

#### 初始化相关
```rust
// 协议版本协商和握手
acp::InitializeRequest::new(acp::ProtocolVersion::V1)
    .client_capabilities(ClientCapabilities::new()
        .fs(FileSystemCapability::new()
            .read_text_file(true)
            .write_text_file(true))
        .terminal(true)
        .meta(Meta::from_iter([
            ("terminal_output".into(), true.into()),
            ("terminal-auth".into(), true.into()),
        ])))
    .client_info(Implementation::new("zed", version))
```

**返回字段**:
- `protocol_version` - 协议版本
- `agent_capabilities` - Agent 能力声明
- `auth_methods` - 认证方法列表
- `agent_info` - Agent 信息（name, version 等）

#### 会话管理
```rust
// 创建新会话
acp::NewSessionRequest::new(cwd)
    .mcp_servers(Vec<McpServer>)

// 加载现有会话（需要 AcpBetaFeatureFlag）
acp::LoadSessionRequest::new(session_id, cwd)
    .mcp_servers(Vec<McpServer>)

// 列出会话
acp::ListSessionsRequest::new()
    .cwd(Option<PathBuf>)
    .cursor(Option<String>)
```

#### 提示/推理
```rust
acp::PromptRequest::new(session_id, message)
```

**返回类型**:
```rust
acp::PromptResponse {
    stop_reason: StopReason  // EndTurn, Cancelled, 等
}
```

#### 取消操作
```rust
acp::CancelNotification::new(session_id)
```

#### 认证
```rust
acp::AuthenticateRequest::new(method_id)
```

---

### 2.2 Client Delegate 回调接口 (由 agent 调用 Zed)

这些是 agent 调用 Zed 提供的功能：

#### 文件操作
```rust
// 请求读取文件
async fn read_text_file(
    arguments: acp::ReadTextFileRequest,
) -> Result<acp::ReadTextFileResponse, acp::Error>

// 请求写入文件
async fn write_text_file(
    arguments: acp::WriteTextFileRequest,
) -> Result<acp::WriteTextFileResponse, acp::Error>
```

#### 权限请求
```rust
// 请求用户授权工具调用
async fn request_permission(
    arguments: acp::RequestPermissionRequest,
) -> Result<acp::RequestPermissionResponse, acp::Error>
```

#### 会话通知
```rust
// Agent 推送会话状态更新
async fn session_notification(
    notification: acp::SessionNotification,
) -> Result<(), acp::Error>
```

`SessionUpdate` 支持的更新类型：
- `UserMessageChunk` - 用户消息块
- `AgentMessageChunk` - Agent 消息块
- `AgentThoughtChunk` - Agent 思考过程
- `ToolCall` - 工具调用开始
- `ToolCallUpdate` - 工具调用更新
- `Plan` - 计划更新
- `AvailableCommandsUpdate` - 可用命令更新
- `CurrentModeUpdate` - 模式更新
- `ConfigOptionUpdate` - 配置选项更新
- `SessionInfoUpdate` - 会话信息更新

#### 终端管理
```rust
// 创建终端
async fn create_terminal(
    args: acp::CreateTerminalRequest,
) -> Result<acp::CreateTerminalResponse, acp::Error>

// 终止端输出
async fn terminal_output(
    args: acp::TerminalOutputRequest,
) -> Result<acp::TerminalOutputResponse, acp::Error>

// 等待终端退出
async fn wait_for_terminal_exit(
    args: acp::WaitForTerminalExitRequest,
) -> Result<acp::WaitForTerminalExitResponse, acp::Error>

// 终止终端命令
async fn kill_terminal_command(
    args: acp::KillTerminalCommandRequest,
) -> Result<acp::KillTerminalCommandResponse, acp::Error>

// 释放终端
async fn release_terminal(
    args: acp::ReleaseTerminalRequest,
) -> Result<acp::ReleaseTerminalResponse, acp::Error>
```

#### 扩展接口（可选）
```rust
// 自定义方法调用（实验性）
async fn ext_method(_args: acp::ExtRequest)
    -> Result<acp::ExtResponse, acp::Error>

async fn ext_notification(_args: acp::ExtNotification)
    -> Result<(), acp::Error>
```

---

### 2.3 AgentConnection Trait (Zed 抽象接口)

```rust
pub trait AgentConnection {
    // 获取遥测 ID
    fn telemetry_id(&self) -> SharedString;

    // 创建新会话
    fn new_thread(
        self: Rc<Self>,
        project: Entity<Project>,
        cwd: &Path,
        cx: &mut App,
    ) -> Task<Result<Entity<AcpThread>>>;

    // 是否支持加载会话
    fn supports_load_session(&self, cx: &App) -> bool;

    // 加载现有会话
    fn load_session(
        self: Rc<Self>,
        session: AgentSessionInfo,
        project: Entity<Project>,
        cwd: &Path,
        cx: &mut App,
    ) -> Task<Result<Entity<AcpThread>>>;

    // 认证方法
    fn auth_methods(&self) -> &[acp::AuthMethod];

    // 执行认证
    fn authenticate(&self, method_id: acp::AuthMethodId, cx: &mut App)
        -> Task<Result<()>>;

    // 发送提示
    fn prompt(&self, id: Option<UserMessageId>, params: acp::PromptRequest, cx: &mut App)
        -> Task<Result<acp::PromptResponse>>;

    // 取消
    fn cancel(&self, session_id: &acp::SessionId, cx: &mut App);

    // 模型选择器
    fn model_selector(&self, session_id: &acp::SessionId)
        -> Option<Rc<dyn AgentModelSelector>>;

    // 会话模式
    fn session_modes(&self, session_id: &acp::SessionId, cx: &App)
        -> Option<Rc<dyn AgentSessionModes>>;

    // 配置选项
    fn session_config_options(&self, session_id: &acp::SessionId, cx: &App)
        -> Option<Rc<dyn AgentSessionConfigOptions>>;

    // 会话列表
    fn session_list(&self, cx: &mut App)
        -> Option<Rc<dyn AgentSessionList>>;

    // 重试
    fn retry(&self, session_id: &acp::SessionId, cx: &App)
        -> Option<Rc<dyn AgentSessionRetry>>;

    // 截断
    fn truncate(&self, session_id: &acp::SessionId, cx: &App)
        -> Option<Rc<dyn AgentSessionTruncate>>;

    // 设置标题
    fn set_title(&self, session_id: &acp::SessionId, cx: &App)
        -> Option<Rc<dyn AgentSessionSetTitle>>;
}
```

---

## 3. 核心能力列表

### 3.1 文件系统能力
- **read_text_file**: 读取文件内容
  - 支持 `line` 和 `limit` 参数进行部分读取
- **write_text_file**: 写入文件内容
  - 支持原子性写入，通过 diff 系统预览

### 3.2 编辑能力
- **Diff 预览**: Zed 提供内联 diff 视图
- **Keep/Reject 工作流**: 用户可以接受或拒绝单个编辑
- **Checkpoint 支持**: Git checkpoint 集成

### 3.3 终端能力
- **create_terminal**: 创建新的终端实例
- **kill_terminal_command**: 终止端命令
- **terminal_output**: 获取终端输出
- **wait_for_terminal_exit**: 等待终端退出
- **release_terminal**: 释放终端资源
- **终端输出流**: 支持通过 `terminal_output` meta 字段流式输出

### 3.4 权限管理
- **Flat Options**: 简单的允许/拒绝选项
- **Dropdown Options**: 带有选项的下拉菜单
- **Always Allow**: 记住用户的许可决定
- **权限类型**:
  - `AllowOnce`: 仅本次允许
  - `AllowAlways`: 总是允许
  - `DenyOnce`: 本次拒绝

### 3.5 会话管理能力
- **Session Modes**: 支持多种会话模式（如 Claude Code 的不同模式）
- **Model Selection**: 支持模型选择和切换
- **Config Options**: 支持配置选项（如温度、最大 token 等）
- **Session History**: 列出和加载历史会话（需要 beta flag）

### 3.6 MCP 集成
- **MCP Servers**: Zed 可以将已配置的 MCP 服务器传递给 agent
- **Stdio MCP**: 通过标准 I/O 连接 MCP
- **HTTP MCP**: 通过 HTTP 连接 MCP
- **环境变量**: 支持传递环境变量

### 3.7 消息格式
- **ContentBlock**: 支持多种内容类型
  - `Text`: 纯文本
  - `ResourceLink`: 文件/资源链接
  - `Image`: base64 编码的图片
  - `Resource`: 嵌入式资源内容

### 3.8 工具调用支持
- **ToolKind**:
  - `Fetch`: 获取信息（只读）
  - `Execute`: 执行操作（可能修改）
  - `Other`: 自定义类型（如 subagent）
- **ToolCallLocation**: 工具调用位置（文件路径和行号）
- **Terminal Output in ToolCalls**: 工具调用中可以包含终端输出流

### 3.9 计划 (Plan) 能力
```rust
pub struct PlanEntry {
    pub content: Entity<Markdown>,
    pub priority: PlanEntryPriority,  // High, Medium, Low
    pub status: PlanEntryStatus,      // Pending, InProgress, Completed
}
```

---

## 4. 架构图和调用链

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Zed (ACP Client)                           │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐               │
│  │ AgentPanel │  │  AcpThread │  │  Diff UI   │               │
│  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘               │
│        │                │                 │                     │
│        ▼                ▼                 ▼                      │
│  ┌────────────────────────────────────────────┐                 │
│  │     AgentConnection (trait)               │                 │
│  │  - prompt()                               │                 │
│  │  - authenticate()                          │                 │
│  │  - new_thread()                           │                 │
│  │  - model_selector()                       │                 │
│  └─────────────────┬──────────────────┘     │                 │
│                    │                         │                 │
└────────────────────┼─────────────────────────┘                 │
                     │ stdin/stdout                             │
                     │ JSON-RPC messages                        │
┌────────────────────┼─────────────────────────┐                 │
│  ┌─────────────▼─────────────────────────────┐   │             │
│  │  ACP Agent (External Process)             │   │             │
│  │  - Initialize                             │   │             │
│  │  - NewSession                             │   │             │
│  │  - Prompt + SessionUpdate stream          │   │             │
│  │  - Tool calls (file, terminal, etc.)     │   │             │
│  └─────────────┬─────────────────────────────┘   │             │
│                │                                 │             │
│  ┌─────────────▼─────────────────────────────┐   │             │
│  │  AI Model (Anthropic, OpenAI, etc.)      │   │             │
│  └─────────────────────────────────────────────┘   │             │
└───────────────────────────────────────────────────┘
```

### 4.2 调用流程（创建新会话）

```
User        UI (AgentPanel)    AS (AgentServerStore)    AC (AcpConnection)    AG (ACP Agent)
 │                │                      │                      │                      │
 │ Click "New Thread" │                      │                      │                      │
 ├───────────────>│                      │                      │                      │
 │                │ connect(agent_server) │                      │                      │
 │                ├─────────────────────>│                      │                      │
 │                │                      │ connect() (spawn process)                     │
 │                │                      ├─────────────────────>│                      │
 │                │                      │                      │ Initialize (stdin)   │
 │                │                      │                      ├─────────────────────>│
 │                │                      │                      │                      │
 │                │                      │                      │ Initialize Response (stdout)
 │                │                      │                      │<─────────────────────┤
 │                │                      │                      │                      │
 │                │                      │                      │ NewSession (stdin)    │
 │                │                      │                      ├─────────────────────>│
 │                │                      │                      │                      │
 │                │                      │                      │ NewSession Response (stdout)
 │                │                      │                      │<─────────────────────┤
 │                │                      │ thread: Entity<AcpThread>                  │
 │                │                      │<─────────────────────┤                      │
 │                │ thread ready         │                      │                      │
 │                │<─────────────────────┤                      │                      │
 │                │                      │                      │                      │
 │ Type message    │                      │                      │                      │
 ├───────────────>│                      │                      │                      │
 │                │ prompt(message)       │                      │                      │
 │                ├─────────────────────>│                      │                      │
 │                │                      │                      │ Prompt Request (stdin)│
 │                │                      │                      ├─────────────────────>│
 │                │                      │                      │                      │
 │ Show updates   │                      │                      │                      │
 │<───────────────┼─────────────────────┼─────────────────────┼──────────────────────┤
 │                │                      │                      │                      │
 │                │                      │                      │ SessionUpdate (stdout)│
 │                │                      │                      │<─────────────────────┤
 │                │                      │                      │                      │
 │                │                      │                      │ ... (more updates)   │
 │                │                      │                      │                      │
 │                │                      │                      │ Prompt Response (stdout)
 │                │                      │                      │<─────────────────────┤
 │                │                      │                      │                      │
 │                │ PromptResponse       │                      │                      │
 │                │<─────────────────────┤                      │                      │
```

### 4.3 关键数据流

#### 消息格式
```rust
// Agent → Zed (SessionUpdate)
acp::SessionNotification {
    session_id: SessionId,
    update: SessionUpdate,
}

// Zed → Agent (Prompt)
acp::PromptRequest {
    session_id: SessionId,
    message: Vec<ContentBlock>,
}

// Agent → Zed (ToolCall)
acp::ToolCall {
    tool_call_id: ToolCallId,
    title: String,
    kind: ToolKind,  // Fetch | Execute | Other
    status: ToolCallStatus,
    content: Vec<ToolCallContent>,
    locations: Vec<ToolCallLocation>,
    meta: Option<Meta>,
}
```

#### 终端输出流
```rust
// 在 ToolCallUpdate 的 meta 中
meta: {
    "terminal_output": {
        "terminal_id": "uuid",
        "data": "base64-encoded-bytes"
    }
}

// 或者在 ToolCall 中创建终端
meta: {
    "terminal_info": {
        "terminal_id": "uuid",
        "cwd": "/path/to/dir"
    }
}
```

### 4.4 核心模块关系

```
AgentServerStore
├── ExternalAgent (enum)
│   ├── NativeAgent (Zed's built-in)
│   ├── Gemini
│   ├── ClaudeCode
│   ├── Codex
│   └── Custom { name }
├── ExternalAgentServer (trait)
│   ├── get_command() → AgentServerCommand
│   └── as_any_mut()
└── ExternalAgentEntry
    ├── server: Box<dyn ExternalAgentServer>
    ├── icon: Option<SharedString>
    └── source: ExternalAgentSource

AgentConnection (trait)
├── AcpConnection (implementing struct)
│   ├── connection: Rc<acp::ClientSideConnection>
│   ├── sessions: HashMap<SessionId, AcpSession>
│   ├── auth_methods: Vec<acp::AuthMethod>
│   └── agent_capabilities: acp::AgentCapabilities
└── AgentSession
    ├── thread: WeakEntity<AcpThread>
    ├── session_modes: Option<...>
    ├── models: Option<...>
    └── config_options: Option<...>
```

---

## 5. Agent 开发者对接指南

### 5.1 基本要求

#### 进程启动
Agent 必须能够：
1. 通过 stdin 接收 JSON-RPC 消息
2. 通过 stdout 发送 JSON-RPC 响应
3. 支持 ACP v1 协议
4. 在 stderr 输出日志（会被 Zed 捕获）

#### 初始化响应
Agent 必须在 Initialize 请求后返回：
```json
{
  "protocol_version": "1",
  "agent_capabilities": {
    "prompt_capabilities": {
      "text": true,
      "image": true,
      "audio": false,
      "web_search": false,
      "embedded_context": true
    },
    "session_capabilities": {
      "list": {
        "supported": true
      },
      "load": {
        "supported": false
      }
    }
  },
  "auth_methods": [
    {
      "id": "api_key",
      "name": "API Key"
    }
  ],
  "agent_info": {
    "name": "My Agent",
    "version": "1.0.0"
  }
}
```

### 5.2 必需实现的方法

#### NewSession
```json
// 请求
{
  "cwd": "/path/to/project",
  "mcp_servers": [
    {
      "id": "server-id",
      "stdio": {
        "command": "mcp-server",
        "args": ["--serve"],
        "env": []
      }
    }
  ]
}

// 响应
{
  "session_id": "session-uuid",
  "modes": [
    {
      "id": "mode-id",
      "name": "Mode Name"
    }
  ],
  "models": [
    {
      "model_id": "model-id",
      "name": "Model Name",
      "description": "...",
      "max_tokens": 128000
    }
  ],
  "config_options": [
    {
      "id": "config-id",
      "name": "Config Name",
      "kind": {
        "Select": {
          "options": {
            "Ungrouped": [
              {
                "label": "Option Label",
                "value": "option-value"
              }
            ]
          },
          "current_value": "option-value"
        }
      }
    }
  ]
}
```

#### Prompt + SessionUpdate Stream
```json
// 请求
{
  "session_id": "session-uuid",
  "message": [
    {
      "Text": {
        "text": "Hello, agent!"
      }
    }
  ]
}

// 响应（流式）
// 首先返回初始响应
{
  "stop_reason": null
}

// 然后通过 Notification 流式更新
{
  "session_id": "session-uuid",
  "update": {
    "AgentMessageChunk": {
      "content": {
        "Text": {
          "text": "Hello"
        }
      }
    }
  }
}

// 更多更新...

{
  "session_id": "session-uuid",
  "update": {
    "ToolCall": {
      "tool_call_id": "call-id",
      "title": "Read file",
      "kind": {
        "Fetch": {}
      },
      "status": "Pending",
      "content": [],
      "locations": []
    }
  }
}

// 最后
{
  "session_id": "session-uuid",
  "update": {
    "ToolCallUpdate": {
      "tool_call_id": "call-id",
      "status": "Completed"
    }
  }
}

// PromptResponse
{
  "stop_reason": "EndTurn"
}
```

### 5.3 可选但推荐的功能

#### 文件操作
如果 agent 需要读取文件，应该：
```json
// 发送请求（通过 Client trait）
{
  "path": "/path/to/file.txt",
  "line": 10,
  "limit": 100
}

// 接收响应
{
  "content": "file contents"
}
```

#### 终端管理
```json
// 创建终端
{
  "command": "npm",
  "args": ["install"],
  "cwd": "/path/to/project",
  "env": [],
  "output_byte_limit": 100000
}

// 响应
{
  "terminal_id": "terminal-uuid"
}

// 后续更新
{
  "update": {
    "ToolCallUpdate": {
      "meta": {
        "terminal_output": {
          "terminal_id": "terminal-uuid",
          "data": "base64-bytes"
        }
      }
    }
  }
}
```

#### 权限请求
```json
// 请求
{
  "session_id": "session-id",
  "tool_call": {...},
  "options": {
    "Flat": [
      {
        "option_id": "allow_once",
        "name": "Allow Once",
        "kind": {
          "AllowOnce": {}
        }
      },
      {
        "option_id": "allow_always",
        "name": "Always Allow",
        "kind": {
          "AllowAlways": {}
        }
      }
    ]
  }
}

// 响应
{
  "outcome": {
    "option_id": "allow_once"
  }
}
```

### 5.4 配置和部署

#### 作为 Zed Extension (推荐)
在 `extension.toml` 中配置：
```toml
[agent_servers.my-agent]
name = "My Agent"
icon = "icon.svg"

[agent_servers.my-agent.targets.darwin-aarch64]
archive = "https://github.com/owner/repo/releases/download/v1.0.0/agent-darwin-arm64.tar.gz"
cmd = "./agent"
args = ["--acp"]
sha256 = "abc123..."

[agent_servers.my-agent.env]
MY_API_KEY = "${MY_API_KEY}"
```

#### 作为自定义 Agent（调试）
在 `settings.json` 中配置：
```json
{
  "agent_servers": {
    "My Custom Agent": {
      "type": "custom",
      "command": "node",
      "args": ["~/projects/agent/index.js", "--acp"],
      "env": {}
    }
  }
}
```

### 5.5 调试

#### 使用 ACP Logs
```bash
# 在 Zed 中打开命令面板
Cmd+Shift+P

# 执行
dev: open acp logs
```

这会显示所有进出的 ACP 消息，包括：
- 请求和响应
- 通知
- 工具调用
- 错误

### 5.6 实现示例 (伪代码)

```typescript
import { AgentServer } from '@agentclientprotocol/sdk';

const server = new AgentServer({
  version: '1',

  async initialize(params) {
    return {
      protocolVersion: '1',
      agentCapabilities: {
        promptCapabilities: {
          text: true,
          image: true,
          audio: false,
          webSearch: false,
          embeddedContext: true
        },
        sessionCapabilities: {
          list: { supported: false },
          load: { supported: false }
        }
      },
      authMethods: [
        { id: 'api_key', name: 'API Key' }
      ],
      agentInfo: {
        name: 'My Agent',
        version: '1.0.0'
      }
    };
  },

  async newSession(params) {
    const sessionId = generateId();
    return {
      sessionId,
      modes: [],
      models: [{ modelId: 'default', name: 'Default Model' }],
      configOptions: []
    };
  },

  async* prompt(params, client) {
    // 发送 AgentMessageChunk
    await client.sendNotification({
      sessionId: params.sessionId,
      update: {
        AgentMessageChunk: {
          content: { Text: { text: 'Thinking...' } }
        }
      }
    });

    // 调用 AI 模型
    const response = await callAI(params.message);

    // 流式返回结果
    for (const chunk of response.chunks) {
      await client.sendNotification({
        sessionId: params.sessionId,
        update: {
          AgentMessageChunk: {
            content: { Text: { text: chunk } }
          }
        }
      });
    }

    return { stopReason: 'EndTurn' };
  },

  // Client 回调
  async readTextFile(params) {
    return fs.readFileSync(params.path, 'utf-8');
  },

  async writeTextFile(params) {
    fs.writeFileSync(params.path, params.content);
  },

  async requestPermission(params) {
    // 等待用户授权（通常由 UI 处理）
    return { outcome: params.options[0].optionId };
  }
});

// 启动服务器（通过 stdin/stdout）
server.start();
```

### 5.7 常见问题

#### Q: 如何处理错误？
```json
{
  "code": "InternalError",
  "message": "Detailed error message",
  "data": {
    "details": "Additional context"
  }
}

// 特殊错误码
// - AuthRequired: 需要重新认证
// - InternalError: 通用错误
// - InvalidParams: 参数无效
```

#### Q: 如何实现子 agent？
```json
{
  "tool_call_id": "call-id",
  "kind": { "Other": {} },
  "meta": {
    "tool_name": "subagent"
  },
  "content": [...]
}
```

#### Q: 终端输出如何流式传输？
```json
{
  "tool_call_id": "call-id",
  "meta": {
    "terminal_output": {
      "terminal_id": "terminal-uuid",
      "data": "base64-chunk-1"
    }
  }
}

// 然后是下一个 chunk
{
  "tool_call_id": "call-id",
  "meta": {
    "terminal_output": {
      "terminal_id": "terminal-uuid",
      "data": "base64-chunk-2"
    }
  }
}
```

---

## 6. 相关文件路径汇总

### 核心实现
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/acp.rs` - ACP 连接管理
- `/Users/yuchen.liu/src/zed/crates/acp_thread/src/acp_thread.rs` - 会话线程实现
- `/Users/yuchen.liu/src/zed/crates/acp_thread/src/connection.rs` - 连接接口定义
- `/Users/yuchen.liu/src/zed/crates/acp_thread/src/diff.rs` - Diff 表示
- `/Users/yuchen.liu/src/zed/crates/acp_thread/src/terminal.rs` - 终端抽象
- `/Users/yuchen.liu/src/zed/crates/acp_thread/src/mention.rs` - Mention 处理

### Agent Server 实现
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/claude.rs` - Claude Code 适配器
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/gemini.rs` - Gemini CLI 适配器
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/codex.rs` - Codex CLI 适配器
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/custom.rs` - 自定义 agent 支持
- `/Users/yuchen.liu/src/zed/crates/agent_servers/src/agent_servers.rs` - Agent server 管理器

### UI 组件
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/thread_view.rs` - ACP 线程视图
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/model_selector.rs` - 模型选择器
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/mode_selector.rs` - 模式选择器
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/config_options.rs` - 配置选项 UI
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/message_editor.rs` - 消息编辑器
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/entry_view_state.rs` - 条目视图状态
- `/Users/yuchen.liu/src/zed/crates/agent_ui/src/acp/thread_history.rs` - 会话历史

### 调试和工具
- `/Users/yuchen.liu/src/zed/crates/acp_tools/src/acp_tools.rs` - ACP 调试工具

### 存储
- `/Users/yuchen.liu/src/zed/crates/project/src/agent_server_store.rs` - Agent server 存储
- `/Users/yuchen.liu/src/zed/crates/project/src/agent_registry_store.rs` - Agent registry 存储

### 文档
- `/Users/yuchen.liu/src/zed/docs/src/ai/external-agents.md` - 用户文档
- `/Users/yuchen.liu/src/zed/docs/src/extensions/agent-servers.md` - 开发者文档

### Agent 工具（用于参考 ACP 工具调用）
- `/Users/yuchen.liu/src/zed/crates/agent/src/tools/` - 各种工具实现参考

---

## 7. 参考资料

- **ACP 官方站点**: https://agentclientprotocol.com
- **Rust SDK**: https://github.com/agentclientprotocol/rust-sdk
- **TypeScript SDK**: https://www.npmjs.com/package/@agentclientprotocol/sdk
- **Zed 源码**: https://github.com/zed-industries/zed

---

## 总结

Zed 的 ACP 实现非常完善，提供了：
1. **完整的协议支持** - v1 协议的所有核心方法
2. **丰富的能力** - 文件操作、终端、权限、模型选择、会话管理
3. **良好的扩展性** - 支持 MCP、自定义工具、子 agent
4. **强大的调试支持** - 内置的 ACP logs 工具
5. **参考实现** - Claude Code、Gemini CLI、Codex 等完整示例

开发兼容 Zed 的 agent 需要实现 ACP v1 协议，推荐使用官方 SDK（Rust/Python/TypeScript/Kotlin），并确保正确处理流式响应和工具调用。
