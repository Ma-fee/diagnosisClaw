# Zed ACP Subagent 功能调研报告

**调研日期**: 2026-02-11  
**调研范围**: Zed 编辑器中的 ACP (Agent Client Protocol) 协议及 Subagent 实现机制  
**数据来源**: Zed 源码 (zed-industries/zed)、ACP 官方文档 (agentclientprotocol.com)

---

## 目录

1. [执行摘要](#执行摘要)
2. [ACP 协议简介](#acp-协议简介)
3. [Zed 中 Subagent 的关键发现](#zed-中-subagent-的关键发现)
4. [实现机制详解](#实现机制详解)
5. [代码路径索引](#代码路径索引)
6. [开发 ACP Server 的建议](#开发-acp-server-的建议)
7. [GitHub 开发时间线](#github-开发时间线)
8. [相关资源](#相关资源)

---

## 执行摘要

### 🔥 核心发现

1. **ACP 协议本身没有原生的 subagent 类型定义** - Subagent 是通过 ToolCall 扩展机制实现的
2. **Zed 使用 `agent-client-protocol` crate v0.9.4** - 这是一个外部依赖，非 Zed 内部实现
3. **Subagent 通过 `_meta` 字段传递 session ID** - 利用 ACP 的扩展性机制
4. **Eval 环境暂未实现 subagent 支持** - `create_subagent` 返回 `unimplemented!()`

### 技术栈

- **协议**: Agent Client Protocol (ACP) v1
- **Rust SDK**: `agent-client-protocol` v0.9.4 (features: ["unstable"])
- **传输**: JSON-RPC over stdio（本地）或 HTTP/WebSocket（远程）
- **架构**: Agent ↔ Client 双向通信

---

## ACP 协议简介

### 概述

Agent Client Protocol (ACP) 是一个标准化的通信协议，用于连接代码编辑器 (Client) 和 AI 编程助手 (Agent)。类似于 LSP (Language Server Protocol)，ACP 旨在解决编辑器与 AI 助手之间的集成碎片化问题。

### 核心概念

| 概念 | 说明 |
|------|------|
| **Client** | 代码编辑器/IDE (如 Zed、JetBrains) |
| **Agent** | 使用生成式 AI 自主修改代码的程序 |
| **Session** | 独立的对话上下文，有唯一的 `SessionId` |
| **ToolCall** | Agent 请求执行的工具操作 |
| **Prompt Turn** | 一次完整的交互周期（用户消息 → Agent 响应） |

### 核心方法

- `initialize` - 初始化连接和能力协商
- `session/new` - 创建新会话
- `session/prompt` - 发送用户消息
- `session/update` - 实时更新会话状态
- `session/cancel` - 取消操作

### 扩展机制

所有协议类型包含 `_meta` 字段 (`{ [key: string]: unknown }`)，用于自定义扩展：

```json
{
  "_meta": {
    "traceparent": "00-80e1afed08e019fc1110464cfa66635c-7a085853722dc6d2-01",
    "custom_field": "value"
  }
}
```

---

## Zed 中 Subagent 的关键发现

### ⚠️ 重要结论

**Zed 的 subagent 不是 ACP 协议的标准特性**，而是通过协议扩展机制实现的特定功能。

### 实现方式

Zed 通过以下方式实现 subagent：

#### 1. ToolCall + `_meta` 扩展

```rust
// crates/agent/src/tools/subagent_tool.rs
const SUBAGENT_SESSION_ID_META_KEY: &str = "subagent_session_id";

// 发送 ToolCall 时附加 subagent session ID
let meta = acp::Meta::from_iter([(
    SUBAGENT_SESSION_ID_META_KEY.into(),
    subagent_session_id.to_string().into(),
)]);
event_stream.update_fields_with_meta(acp::ToolCallUpdateFields::new(), Some(meta));
```

#### 2. 事件传播机制

| 层级 | 事件定义 | 文件路径 |
|------|----------|----------|
| ACP Thread | `AcpThreadEvent::SubagentSpawned(acp::SessionId)` | `crates/acp_thread/src/acp_thread.rs:970` |
| Agent Thread | `ThreadEvent::SubagentSpawned(acp::SessionId)` | `crates/agent/src/thread.rs:614` |
| UI 层 | `load_subagent_session()` | `crates/agent_ui/src/acp/thread_view.rs:1053` |
| Eval | 日志记录 | `crates/eval/src/example.rs:331` |

#### 3. 核心参数和限制

```rust
// crates/agent/src/tools/subagent_tool.rs
const MAX_SUBAGENT_DEPTH: u8 = 4;         // 最大嵌套深度 4 层
const MAX_PARALLEL_SUBAGENTS: usize = 8;  // 最大并行数 8 个
const CONTEXT_THRESHOLD: f32 = 0.25;      // 剩余 25% 令牌时触发总结
```

### Subagent Tool 输入参数

```rust
pub struct SubagentToolInput {
    /// UI 显示标签
    pub label: String,
    /// 任务描述
    pub task_prompt: String,
    /// 完成后的总结提示
    pub summary_prompt: Option<String>,
    /// 可选超时（毫秒）
    pub timeout_ms: Option<u64>,
    /// 允许使用的工具白名单
    pub allowed_tools: Option<Vec<String>>,
}
```

### SubagentContext

```rust
pub struct SubagentContext {
    /// 父线程 ID
    pub parent_thread_id: acp::SessionId,
    /// 嵌套深度 (0=根代理, 1=第一层...)
    pub depth: u8,
}
```

---

## 实现机制详解

### 生命周期流程

```
┌─────────────┐
│  用户输入   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  LLM 调用 Subagent Tool             │
│  - label: "Researching alternatives" │
│  - task_prompt: "..."               │
│  - allowed_tools: ["read", "search"]│
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  SubagentTool::run()                │
│  1. 创建新 ACP Session (新 SessionId)│
│  2. 发送 ToolCall (status: pending) │
│  3. 通过 _meta 附加 subagent_session_id│
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  触发 SubagentSpawned 事件           │
│  - UI 显示子代理卡片                 │
│  - 可展开/收起查看详情               │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  子代理执行                          │
│  - 独立的 prompt turn               │
│  - 受 allowed_tools 限制             │
│  - 超时支持                          │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  子代理完成                          │
│  - 发送 summary (如有)               │
│  - 通过 summary_prompt 格式结果      │
│  - ToolCall status: completed        │
└─────────────────────────────────────┘
```

### 取消机制

- 父代理取消时自动级联取消子代理
- 用户可通过 UI 主动取消子代理任务
- 取消事件通过 ACP 的 `session/cancel` 传播

### 权限控制

子代理的工具权限受父代理限制：

```rust
// 验证 allowed_tools 是否为父代理可用工具的子集
fn validate_allowed_tools(
    parent_tools: &[String],
    requested_tools: Option<Vec<String>>
) -> Result<()> {
    if let Some(tools) = requested_tools {
        for tool in &tools {
            if !parent_tools.contains(tool) {
                return Err("Tool not allowed");
            }
        }
    }
    Ok(())
}
```

---

## 代码路径索引

### 核心文件

| 文件路径 | 说明 | 关键行号 |
|----------|------|----------|
| `crates/agent/src/tools/subagent_tool.rs` | Subagent Tool 实现 | 1-307 |
| `crates/agent/src/agent.rs` | AgentEnvironment 实现 subagent 创建 | 1067, 1580+ |
| `crates/agent/src/thread.rs` | ThreadEnvironment trait 定义 | 595-603 |
| `crates/acp_thread/src/acp_thread.rs` | AcpThreadEvent 定义 | 970 |
| `crates/acp_thread/src/connection.rs` | AgentConnection trait | 1-796 |
| `crates/agent_ui/src/acp/thread_view.rs` | UI 层 subagent 处理 | 1053, 1495 |
| `crates/eval/src/instance.rs` | Eval 环境 (create_subagent 未实现) | 683-693 |
| `crates/eval/src/example.rs` | Eval subagent 事件处理 | 331 |

### 相关配置

| 文件 | 内容 |
|------|------|
| `Cargo.toml` | `agent-client-protocol = { version = "=0.9.4", features = ["unstable"] }` |
| `crates/acp_thread/Cargo.toml` | 依赖 `agent-client-protocol.workspace = true` |

---

## 开发 ACP Server 的建议

### 方案对比

| 方案 | 复杂度 | 兼容性 | 扩展性 | 推荐度 |
|------|--------|--------|--------|--------|
| ToolCall + _meta | 低 | Zed 专用 | 有限 | ⭐⭐⭐ |
| ACP Proxy | 中 | 通用 | 高 | ⭐⭐⭐⭐⭐ |
| 原生 ACP Agent | 低 | 通用 | 低 | ⭐⭐⭐⭐ |

### 方案 1: 使用 ToolCall 模拟 (短期)

如果你需要兼容 Zed 的现有实现：

```rust
use agent_client_protocol as acp;

// 创建模拟 subagent 的 ToolCall
fn create_subagent_tool_call(
    &self,
    parent_session_id: acp::SessionId,
    label: &str,
) -> acp::ToolCall {
    let subagent_session_id = acp::SessionId::new(uuid::Uuid::new_v4().to_string());
    
    acp::ToolCall::new("subagent-001", label)
        .kind(acp::ToolKind::Other)
        .status(acp::ToolCallStatus::InProgress)
        .meta(acp::Meta::from_iter([
            ("subagent_session_id", subagent_session_id.to_string()),
            ("parent_session_id", parent_session_id.to_string()),
        ]))
}

// 发送 session update
async fn spawn_subagent(&self, session_id: acp::SessionId) {
    let tool_call = self.create_subagent_tool_call(session_id, "Researching");
    
    self.send_session_update(
        session_id,
        acp::SessionUpdate::ToolCall(tool_call)
    ).await;
    
    // 在后台执行子任务
    tokio::spawn(async move {
        // 子代理逻辑
        // ...
        
        // 完成后更新 ToolCall 状态
        let update = acp::ToolCallUpdate::new("subagent-001")
            .status(acp::ToolCallStatus::Completed)
            .content(vec![
                acp::ToolCallContent::Text("Subagent completed".into())
            ]);
            
        self.send_session_update(
            session_id,
            acp::SessionUpdate::ToolCallUpdate(update)
        ).await;
    });
}
```

### 方案 2: 使用 ACP Proxy (推荐)

基于 [ACP Proxy Chains RFD](https://agentclientprotocol.com/rfds/proxy-chains.md)：

```rust
// 实现 Proxy  trait
use sacp_proxy::Proxy;

#[async_trait]
impl Proxy for MySubagentProxy {
    async fn proxy_initialize(&self, request: ProxyInitializeRequest) -> InitializeResponse {
        // Proxy 知道自己有 successor
        // 可以拦截、修改、增强消息
    }
    
    async fn handle_message(&self, message: Message) -> Result<Message> {
        // 拦截 prompt 请求
        // 可以创建子代理会话
        // 转发到 successor
    }
}
```

Proxy 的优势：
- **通用性**: 适用于任何 ACP Client
- **可组合**: 可以链式组合多个 Proxy
- **功能丰富**: 可以注入上下文、过滤响应、协调多代理

### SDK 使用示例

```rust
// Cargo.toml
[dependencies]
agent-client-protocol = "0.9.4"

// 实现 Agent trait
use agent_client_protocol::{Agent, AgentSide, InitializeRequest, InitializeResponse};
use agent_client_protocol::{PromptRequest, PromptResponse, StopReason};

#[async_trait]
impl Agent for MyAgent {
    async fn initialize(&self, request: InitializeRequest) -> InitializeResponse {
        InitializeResponse::new(ProtocolVersion::V1)
            .agent_capabilities(
                AgentCapabilities::new()
                    .load_session(true)
                    .prompt_capabilities(
                        PromptCapabilities::new()
                            .image(true)
                            .embedded_context(true)
                    )
            )
            .auth_methods(vec![
                AuthMethod::new("api_key", "API Key Authentication")
            ])
    }
    
    async fn prompt(&self, request: PromptRequest) -> PromptResponse {
        // 处理用户消息
        // 可能需要创建 subagent tool calls
        
        PromptResponse::new(StopReason::EndTurn)
    }
}
```

---

## GitHub 开发时间线

### Subagent 相关 PR

| 日期 | PR | 标题 | 作者 |
|------|-----|------|------|
| 2026-01-06 | #46187 | Thread spawning + execution | @rtfeldman |
| 2026-01-06 | #46188 | Render subagents in thread | @rtfeldman |
| 2026-01-07 | #46284 | Granular Tool Permission Buttons | @rtfeldman |
| 2026-01-14 | #47647 | Cancel subagents | @cameron1024 |
| 2026-02-04 | #48381 | Move subagent spawning to ThreadEnvironment | @bennetbo |

### 关键 PR 内容

**PR #46187** - 核心执行逻辑
- `Thread::new_subagent()` 构造函数
- `SubagentTool::run()` 生命周期管理
- `SubagentContext` 父子线程关系
- 最大深度 4 层, 最大并行数 8 个

**PR #48284** - 细粒度权限控制
- 60 commits, 2558 新增行
- 每工具权限规则: `allow`/`deny`/`confirm`
- 智能权限按钮: "Always allow `<tool>`"
- 支持 MCP 工具的权限控制

**PR #48381** - 架构重构
- 将子代理创建迁移到 `ThreadEnvironment`
- 支持更灵活的 subagent provider 接入

---

## 相关资源

### 官方文档

- [ACP 官网](https://agentclientprotocol.com/)
- [ACP 协议索引](https://agentclientprotocol.com/llms.txt)
- [Tool Calls 文档](https://agentclientprotocol.com/protocol/tool-calls.md)
- [扩展性文档](https://agentclientprotocol.com/protocol/extensibility.md)
- [Proxy Chains RFD](https://agentclientprotocol.com/rfds/proxy-chains.md)

### Rust SDK

- **Crate**: [agent-client-protocol](https://crates.io/crates/agent-client-protocol) v0.9.4
- **GitHub**: [agentclientprotocol/rust-sdk](https://github.com/agentclientprotocol/rust-sdk)
- **文档**: [docs.rs/agent-client-protocol](https://docs.rs/agent-client-protocol)

### 协议规范

- [协议概述](https://agentclientprotocol.com/protocol/overview.md)
- [初始化](https://agentclientprotocol.com/protocol/initialization.md)
- [会话设置](https://agentclientprotocol.com/protocol/session-setup.md)
- [Prompt Turn](https://agentclientprotocol.com/protocol/prompt-turn.md)
- [完整 Schema](https://agentclientprotocol.com/protocol/schema.md)

### Zed 源码

- **仓库**: [zed-industries/zed](https://github.com/zed-industries/zed)
- **Agent Crate**: `crates/agent/`
- **ACP Thread**: `crates/acp_thread/`
- **Agent UI**: `crates/agent_ui/`

---

## 结论与建议

### 关键发现总结

1. **Subagent 在 Zed 中已实现并可用** - 通过 Feature flag 默认启用
2. **ACP 协议本身没有原生 subagent 定义** - Zed 通过 ToolCall + _meta 扩展实现
3. **Eval 系统不支持 subagent** - 生产环境可用，评估框架未实现
4. **Agent Client Protocol 是外部标准** - 使用 crates.io 上的公开 crate

### 对用户项目的建议

如果你要在自己的项目中实现类似功能：

1. **短期**: 使用 ToolCall + `_meta` 字段（Zed 兼容）
2. **中期**: 关注 ACP Proxy 规范的发展
3. **长期**: 等待 ACP 官方可能推出的 subagent 标准

### 注意事项

- Subagent 实现依赖于 `agent-client-protocol` 的 `unstable` 特性
- 当前版本为 0.9.4，协议仍在演进中
- 建议订阅 [ACP RFDs](https://agentclientprotocol.com/rfds/about.md) 获取最新进展

---

*报告生成时间: 2026-02-11*  
*调研工具: grep, webfetch, GitHub API, 源码阅读*

---

## 附录 B: Claude Code ACP 适配器中的 Subagent

### 调研结果

**Claude Code ACP 适配器 (`zed-industries/claude-code-acp`) 中没有实现真正的 ACP Subagent 功能**。

### 发现详情

#### 1. 代码搜索结果

在 `zed-industries/claude-code-acp` 仓库中搜索 subagent 相关代码：

```bash
# 搜索结果
src/tests/acp-agent.test.ts  # 1 处提及
```

**仅在测试文件中发现一处相关代码**。

#### 2. Task Tool 的处理

在测试文件 `src/tests/acp-agent.test.ts` 中，发现了对 Claude Code `Task` tool 的测试：

```typescript
it("should handle Task tool calls", () => {
  const tool_use = {
    type: "tool_use",
    id: "toolu_01ANYHYDsXcDPKgxhg7us9bj",
    name: "Task",
    input: {
      description: "Handle user's work request",
      prompt: "The user has asked me to...",
      subagent_type: "general-purpose",  // ← 注意这里有 subagent_type 字段
    },
  };

  expect(toolInfoFromToolUse(tool_use)).toStrictEqual({
    kind: "think",  // ← 但被映射为 "think" 类型
    title: "Handle user's work request",
    content: [...],
  });
});
```

#### 3. 关键发现

| 项目 | 状态 | 说明 |
|------|------|------|
| Claude Code 原生 Task Tool | ✅ 存在 | 有 `subagent_type` 字段 |
| ACP Subagent 实现 | ❌ 不存在 | 没有创建 ACP subagent session |
| ToolCall 映射 | ⚠️ 简化处理 | Task 被映射为 `kind: "think"` |
| Subagent Spawned 事件 | ❌ 不触发 | 没有 `SubagentSpawned` 事件 |

### 结论

**Claude Code ACP 适配器没有实现 subagent 功能**。

当有 Task tool 调用时：
1. Claude Code SDK 内部处理 subagent 逻辑
2. ACP 适配器仅将其视为普通的 tool call
3. 映射为 `kind: "think"` 的 ToolCall 展示给用户
4. 不会创建新的 ACP session 或触发 subagent 事件

这意味着：
- ❌ 在 Zed UI 中看不到 subagent 卡片
- ❌ 无法单独取消子代理任务
- ❌ 没有 subagent 嵌套层级显示
- ✅ Claude Code 内部仍可并行执行任务
- ✅ 最终结果会返回给 parent session

### 与 Zed 原生 Agent 的对比

| 功能 | Zed 原生 Agent | Claude Code (via ACP) |
|------|----------------|----------------------|
| Subagent Tool | ✅ 完整实现 | ❌ Task tool 简化映射 |
| Subagent Spawned 事件 | ✅ 触发 | ❌ 不触发 |
| 嵌套层级显示 | ✅ 支持 | ❌ 看不到层级 |
| 单独取消子代理 | ✅ 支持 | ❌ 只能取消整个 session |
| 工具权限控制 | ✅ 细粒度 | ⚠️ 依赖 Claude Code 内部 |

### 对开发者的启示

如果你要开发接入 Zed 的 ACP server：

1. **Claude Code 适配器没有提供 subagent 参考实现**
2. 如果需要 subagent 功能，需要自己实现：
   - 创建新的 ACP session (`session/new`)
   - 发送 `SubagentSpawned` 事件 (通过 `_meta`)
   - 管理父子 session 关系
   - 协调工具权限

3. 或者等待：
   - Anthropic 官方在 Claude Code 中实现 ACP subagent 支持
   - ACP 协议标准化 subagent 规范

