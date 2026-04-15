# Zed ACP Subagent 功能调研报告

**调研日期**: 2026-02-11  
**更新日期**: 2026-02-16  
**调研范围**: Zed 编辑器中的 ACP (Agent Client Protocol) 协议及 Subagent 实现机制  
**数据来源**: Zed 源码 (zed-industries/zed)、ACP 官方文档 (agentclientprotocol.com)

---

## 目录

1. [执行摘要](#执行摘要)
2. [ACP 协议简介](#acp-协议简介)
3. [Zed 中 Subagent 的关键发现](#zed-中-subagent-的关键发现)
4. [实现机制详解](#实现机制详解)
5. [渲染层对接机制](#渲染层对接机制)
6. [代码路径索引](#代码路径索引)
7. [ACP 生态进展](#acp-生态进展)
8. [开发 ACP Server 的建议](#开发-acp-server-的建议)
9. [GitHub 开发时间线](#github-开发时间线)
10. [相关资源](#相关资源)

---

## 执行摘要

### 🔥 核心发现

1. **ACP 协议本身没有原生的 subagent 类型定义** - Subagent 是通过 ToolCall 扩展机制实现的
2. **Zed 使用 `agent-client-protocol` crate v0.9.4** - 这是一个外部依赖，非 Zed 内部实现
3. **Subagent 通过 `_meta` 字段传递 session ID** - 利用 ACP 的扩展性机制
4. **Eval 环境暂未实现 subagent 支持** - `create_subagent` 返回 `unimplemented!()`

### ⚠️ 重要状态更新 (2026-02-16)

> **Subagent 功能已实现但暂时关闭**
>
> 2026-02-13，Zed 通过 PR #49104 将 `subagents` 特性标志临时关闭。该功能代码完整且经过充分测试，关闭是由于特性标志意外开启后的回滚操作。预计在 Staff 测试后重新向公众开放。
>
> **当前状态**: 🔒 Staff Only (需要 `subagents` feature flag)

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

#### 2. 架构演进：ThreadEnvironment（2026-02 更新）

**PR #48381** 引入了新的架构，将子代理创建逻辑从 `SubagentTool` 移至 `ThreadEnvironment`：

```rust
// crates/agent/src/agent.rs
impl NativeThreadEnvironment {
    pub(crate) fn create_subagent_thread(
        agent: WeakEntity<NativeAgent>,
        parent_thread_entity: Entity<Thread>,
        label: String,
        initial_prompt: String,
        timeout: Option<Duration>,
        allowed_tools: Option<Vec<String>>,
        cx: &mut App,
    ) -> Result<Rc<dyn SubagentHandle>> {
        // 1. 检查深度限制
        // 2. 检查并行限制  
        // 3. 过滤允许的工具（只保留父线程存在的工具）
        // 4. 创建 subagent thread
        // 5. 注册到 parent 的 running_subagents
        // 6. 返回 SubagentHandle
    }
}

// SubagentHandle trait 用于生命周期管理
pub trait SubagentHandle {
    fn id(&self) -> acp::SessionId;
    fn wait_for_summary(&self, summary_prompt: String, cx: &AsyncApp) -> Task<Result<String>>;
}
```

**架构优势**：
- 统一的创建入口，深度/并行限制检查内聚
- 工具过滤逻辑集中，避免重复代码
- 超时和取消信号统一管理
- 修复了之前 `stop_by_user` workaround 的混乱
- 支持 `close_session` 正确释放资源

#### 3. 事件传播机制

| 层级 | 事件定义 | 文件路径 |
|------|----------|----------|
| ACP Thread | `AcpThreadEvent::SubagentSpawned(acp::SessionId)` | `crates/acp_thread/src/acp_thread.rs:970` |
| Agent Thread | `ThreadEvent::SubagentSpawned(acp::SessionId)` | `crates/agent/src/thread.rs:614` |
| UI 层 | `load_subagent_session()` | `crates/agent_ui/src/acp/thread_view.rs:1053` |
| Eval | 日志记录 | `crates/eval/src/example.rs:331` |

#### 4. 核心参数和限制

```rust
// crates/agent/src/thread.rs
pub const MAX_SUBAGENT_DEPTH: u8 = 4;         // 最大嵌套深度 4 层
pub const MAX_PARALLEL_SUBAGENTS: usize = 8;  // 最大并行数 8 个
const CONTEXT_THRESHOLD: f32 = 0.25;           // 剩余 25% 令牌时触发总结（已弃用）
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
// crates/agent/src/thread.rs
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SubagentContext {
    /// 父线程 ID
    pub parent_thread_id: acp::SessionId,
    /// 嵌套深度 (0=根代理, 1=第一层...)
    pub depth: u8,
}
```

### 特性标志状态

| 标志 | 状态 | 说明 |
|------|------|------|
| `subagents` | 🔒 Staff Only | 已通过 PR #49104 (2026-02-13) 临时关闭 |
| `acp-beta` | ✅ 已启用 | ACP 协议 Beta 功能 |

---

## 渲染层对接机制

Zed 通过 GPUI 框架为 subagent 提供了完整的 UI 渲染支持，实现了从底层协议到用户界面的无缝集成。

### UI 渲染架构

**核心渲染文件**: `crates/agent_ui/src/acp/thread_view/active_thread.rs`

Subagent 的 UI 渲染主要发生在 `active_thread.rs` 文件中（约 6000+ 行），通过以下方法实现：

| 方法 | 行号范围 | 功能 |
|------|----------|------|
| `render_subagent_tool_call()` | 行 5914+ | 工具调用渲染入口 |
| `render_subagent_card()` | 行 6000+ | Subagent 卡片 UI |
| `render_subagent_expanded_content()` | 行 6200+ | 可展开内容渲染 |
| `render_subagent_permission_buttons()` | 行 6250+ | 权限控制按钮 |

### 渲染流程

```
┌─────────────────────────────────────────────────────────────┐
│                     ToolCall 触发                             │
│                  (status: pending/completed)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              render_subagent_tool_call()                    │
│在里面：                                                     │
│  1. 读取 ToolCall 的 display_label                          │
│  2. 构建 SubagentHandle 用于操作                            │
│  3. 调用 render_subagent_card()                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   render_subagent_card()                    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Card Header (始终显示)                               │   │
│  │ - 折叠/展开按钮                                      │   │
│  │ - 图标 (loading/完成/错误)                           │   │
│  │ - 标题 (label)                                       │   │
│  │ - Error 图标 (如果有错误)                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                             │                               │
│                             ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Expanded Content (展开时显示)                        │   │
│  │ - 当前步骤描述                                       │   │
│  │ - Token 使用情况                                     │   │
│  │ - 文件变更列表 (Created/Modified/Renamed/Deleted)   │   │
│  │ - Diffs 统计 (total / hunks added / hunks removed)  │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### UI 组件详情

#### 1. 状态指示器

Subagent 状态通过图标直观展示：

```rust
// 代码示意（基于 Zed 实现）
enum SubagentState {
    Loading,   // 转圈圈图标
    Completed, // 对勾图标
    Error,     // 错误图标
}
```

#### 2. 文件变更追踪

展开的 subagent 卡片会显示所有文件变更：

```rust
// crates/agent/src/thread.rs
pub struct SubagentFileState {
    created: Vec<PathBuf>,
    modified: Vec<PathBuf>,
    renamed: Vec<(PathBuf, PathBuf)>,  // (old, new)
    deleted: Vec<PathBuf>,
}

pub struct SubagentDiffState {
    total: usize,
    hunks_added: usize,
    hunks_removed: usize,
}
```

#### 3. 权限控制系统

Subagent 可以发起新的工具调用，这些调用需要父代理确认：

```rust
// UI 渲染权限按钮
fn render_subagent_permission_buttons(&self) -> impl IntoElement {
    // 显示："Allow subagent to use `<tool>`?"
    // 按钮："Deny" / "Allow"
    
    // 或者："Always allow `<tool>` from `<subagent>`?"
    // 按钮："Allow Once" / "Always Allow"
}
```

#### 4. 嵌套层级可视化

通过 Tab 缩进实现嵌套层级展示：

```rust
// 在 GPUI element 上使用 padding_left 或 margin_left
.child(div().pl_4().child(subagent_card))  // 增加 1 rem 左缩进
```

### 实时更新机制

Subagent UI 通过以下方式实时更新：

1. **GPUI 通知系统**: `cx.notify()` 触发重新渲染
2. **事件订阅**: `cx.subscribe(subagent_thread, |this, entity, event, cx| ...)`
3. **主动轮询**: 通过 `task::spawn` 后台任务定期更新状态

### 与 Claude Code ACP 适配器的对比

| 功能 | Zed 原生 Agent | Claude Code (via ACP) |
|------|----------------|----------------------|
| Subagent UI 卡片 | ✅ 完整渲染 | ❌ 简化为 `kind: "think"` |
| 展开/折叠 | ✅ 支持 | ❌ 不支持 |
| 文件变更显示 | ✅ 完整信息 | ❌ 无显示 |
| 嵌套层级 | ✅ 缩进展示 | ❌ 无层级 |
| 单独取消按钮 | ✅ 每个 subagent 可取消 | ❌ 只能取消整个 session |
| 工具权限控制 | ✅ 细粒度控制 | ⚠️ 依赖内部实现 |

---

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

| 日期 | PR | 标题 | 作者 | 状态 |
|------|-----|------|------|------|
| 2026-01-06 | #46187 | Thread spawning + execution | @rtfeldman | ✅ Merged |
| 2026-01-06 | #46188 | Render subagents in thread | @rtfeldman | ✅ Merged |
| 2026-01-14 | #46840 | Serialize subagent threads for persistence | @rtfeldman | ✅ Merged |
| 2026-01-20 | #47232 | Fix nested request rate limiting deadlock | @rtfeldman | ✅ Merged |
| 2026-01-22 | #47494 | Fix rate limiter holding permits | @rtfeldman | ✅ Merged |
| 2026-01-23 | #47499 | Show red X icon for interrupted subagents | @rtfeldman | ✅ Merged |
| 2026-01-26 | #47647 | Cancel subagents | @cameron1024 | ✅ Merged |
| 2026-02-04 | #48381 | Move subagent spawning to ThreadEnvironment | @bennetbo | ✅ Merged |
| 2026-02-12 | #49028 | Fix thread title override bug | @danilo-leal | ✅ Merged |
| 2026-02-12 | #49030 | Add some UI tweaks to the subagent thread | @danilo-leal | ✅ Merged |
| 2026-02-13 | #49104 | Turn `subagents` flag to false | @danilo-leal | ✅ Merged |
| 2026-02-18 | #49054 | Back action can navigate to previous workspace | @rtfeldman | ✅ Merged |
| 2026-02-18 | #49350 | Fix cancellation issues with subagents | @bennetbo | ✅ Merged |
| 2026-02-19 | #49042 | Improve minified preview for subagent cards | @bennetbo | 🟡 Draft |
| **2026-02-13** | **#49104** | **Turn `subagents` flag to false** | - | **⚠️ 临时关闭** |

### 关键 PR 内容

**PR #46187** - 核心执行逻辑
- `Thread::new_subagent()` 构造函数
- `SubagentTool::run()` 生命周期管理
- `SubagentContext` 父子线程关系
- 最大深度 4 层, 最大并行数 8 个

**PR #48381** - 架构重构（2026-02-04）
- 将子代理创建迁移到 `ThreadEnvironment::create_subagent_thread()`
- 引入 `SubagentHandle` trait 管理生命周期
- 移除 `stop_by_user` workaround，统一使用 `thread.cancel()`
- 添加 `close_session` 支持，正确释放会话资源
- 支持更灵活的 subagent provider 接入

**PR #49350** - 修复取消问题（2026-02-18）
- 修复子代理取消时的等待指示器问题
- 移除 `stop_by_user` workaround 的最终清理
- 确保父线程取消时正确传播到子代理

**PR #49054** - 返回导航（2026-02-18）
- 添加 backward/forward session stacks
- `navigate_to_session` 记录导航历史
- 支持 `GoBack`/`GoForward` 在子代理间导航
- `ctrl--` 快捷键返回父线程

**PR #47494, #47232** - Rate Limiter 修复
- 修复子代理嵌套请求的死锁问题
- 添加 `bypass_rate_limit` 标志避免嵌套等待
- 确保 rate limiter permit 在工具执行期间正确释放

**PR #49030** - UI 改进（2026-02-12）
- 添加前进箭头指示层级关系
- 添加勾选图标表示子代理完成
- 改进子代理线程的可视化效果

### 相关 Issue 讨论

| Issue | 状态 | 摘要 |
|-------|------|------|
| #49000 | 🟡 Open | Claude Code 外部 Agent: Bash 工具看到过时的文件系统快照 |
| #47944 | 🟡 Open | Claude Code 外部 Agent 在错误的 git 分支上工作 |
| #44834 | 🟡 Open | `tool_call_update` 内容未反映在 UI 中（嵌套 subagent 场景）|
| #48049 | ✅ Closed | Agent UI 视觉测试 panic（已修复 2026-02-09）|
| #48651 | ✅ Closed | Opencode Agent 颜色配置问题（已修复）|
| #17252 | Open | Improve Agent Output: keep_answer_consise 参数使用 |
| #17311 | Open | Agent is bad at not doing work that was requested |
| #17390 | Open | Create new zed project from the agent panel |

**注意**: Issue #49000 和 #47944 是 **外部 Agent (Claude Code)** 的问题，不影响 Zed 原生 Subagent 功能。

---

## ACP 生态进展

### ACP Registry 上线 (2026-01-28)

Zed 官方推出了 ACP Registry，这是一个托管和发现 ACP Server 的平台：
- 🌐 地址: https://zed.dev/blog/acp-registry
- 📦 功能: Server 发布、发现、版本管理、依赖追踪
- 🔍 支持: 搜索 ACP Server 的 capabilities

### JetBrains 加入 ACP 开发 (2025-10-06)

JetBrains 正式宣布加入 ACP 协议开发：
- ✅ 支持产品: IntelliJ IDEA, PyCharm, WebStorm 等
- 🤝 合作方式: 与 Zed 团队共同推进协议标准化
- 📅 进展报告: https://zed.dev/blog/acp-progress-report

### 时间线

```
2025-10-06 ──── JetBrains 加入 ACP
      │
      ▼
2026-01-28 ──── ACP Registry 上线
      │
      ▼
2026-02-10 ──── 远程项目支持 ACP
      │
      ▼
2026-02-13 ──── Subagent 临时关闭 (PR #49104)
```

### 社区资源

| 资源 | 链接 | 说明 |
|------|------|------|
| ACP 进度报告 | https://zed.dev/blog/acp-progress-report | 官方月度更新 |
| ACP Registry 博客 | https://zed.dev/blog/acp-registry | Registry 功能介绍 |
| RFDS | https://agentclientprotocol.com/rfds/ | 协议 RFC 草案 |

---

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

1. **Subagent 功能完整但暂时关闭** - 代码成熟，但 PR #49104 (2026-02-13) 将 `subagents` 标志临时设为 `false`（已在 2026-02-18 重新启用）
2. **ACP 协议本身没有原生 subagent 定义** - Zed 通过 ToolCall + _meta 扩展实现
3. **架构重大演进** - PR #48381 (2026-02-04) 将子代理创建逻辑迁移到 `ThreadEnvironment`，引入 `SubagentHandle` trait，修复了 rate limiter 死锁问题
4. **Eval 系统不支持 subagent** - 生产环境可用（当 flag 启用时），评估框架未实现
5. **渲染层对接完整** - GPUI 集成提供了完整的 subagent 卡片、权限按钮、实时更新、返回导航
6. **生态不断扩展** - JetBrains 加入、ACP Registry 上线、远程项目支持

### 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| Subagent Core | ✅ 完整 | 生命周期、嵌套深度、并行限制实现完善 |
| UI Rendering | ✅ 完整 | GPUI 卡片、展开/折叠、实时更新、返回导航 |
| ACP 协议 | ✅ v0.9.4 | 使用 agent-client-protocol crate |
| Rate Limiter | ✅ 已修复 | 嵌套请求死锁问题已解决（PR #47494, #47232）|
| 功能开关 | 🔒 Feature Flag | `subagents` flag 控制，Staff 可启用 |
| 序列化 | ✅ 已支持 | 子代理线程可持久化和恢复（PR #46840）|

### 对用户项目的建议

如果你要在自己的项目中实现类似功能：

1. **短期**: 使用 ToolCall + `_meta` 字段（Zed 兼容）
2. **中期**: 关注 ACP Proxy 规范的发展
3. **长期**: 等待 ACP 官方可能推出的 subagent 标准
4. **额外**: JetBrains 的 ACP 实现即将推出，可关注其开源实现

### 注意事项

- ⚠️ Subagent 功能目前需要 `subagents` feature flag（Staff 权限）
- Subagent 实现依赖于 `agent-client-protocol` 的 `unstable` 特性
- 当前版本为 0.9.4，协议仍在演进中
- **Rate Limiting**: 子代理与父 Agent 共享配额，嵌套场景下协议已修复死锁问题
- **外部 Agent 限制**: Claude Code 等外部 Agent 存在 Bash 工具文件系统快照不一致问题（Issue #49000），不影响 Zed 原生 Subagent
- ACP Registry 已上线，可考虑将 Server 发布到该平台
- 建议订阅 [ACP RFDs](https://agentclientprotocol.com/rfds/about.md) 获取最新进展

---

*报告生成时间: 2026-02-11*  
*首次更新时间: 2026-02-16*  
**最新更新时间: 2026-02-19**  
*调研工具: GitHub API, grep, webfetch, 源码阅读*

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

