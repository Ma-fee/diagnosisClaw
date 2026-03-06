# Zed Elicitation 实现调研报告

**调研日期**: 2026-03-06  
**调研目标**: Zed 编辑器中 Elicitation 功能的实现状态及其与 Agent Client Protocol 规范的符合度

---

## 1. 核心发现：Elicitation 尚未实现

### 1.1 官方文档明确说明

在 Zed 官方文档中明确说明 Elicitation 功能尚未实现：

> "We welcome contributions that help advance Zed's MCP feature coverage (Discovery, Sampling, **Elicitation**, etc)"
> 
> — Source: `docs/src/ai/mcp.md:15`

### 1.2 当前使用的 ACP Crate 版本

```toml
# Cargo.toml
agent-client-protocol = { version = "=0.9.4", features = ["unstable"] }
```

当前版本 0.9.4 可能不包含完整的 Elicitation 支持，需要升级到有该功能的版本。

---

## 2. Zed 当前的替代方案：Tool Authorization

虽然 Elicitation 未实现，但 Zed 实现了类似的 **Tool Authorization（工具授权）** 系统：

### 2.1 核心组件

| 组件 | 文件路径 | 描述 |
|------|---------|------|
| `ToolCallStatus::WaitingForConfirmation` | `crates/acp_thread/src/acp_thread.rs` (L1759-1823) | 等待用户确认的状态 |
| `PermissionOptions` | `crates/acp_thread/src/connection.rs` (L435-487) | 权限选项枚举 |
| `AgentConnection` Trait | `crates/acp_thread/src/connection.rs` | 代理连接接口 |
| UI 渲染 | `crates/agent_ui/src/connection_view/thread_view.rs` (L5470-5741) | 授权按钮和选择器 |

### 2.2 权限选项结构

```rust
pub enum PermissionOptions {
    Flat(Vec<acp::PermissionOption>),      // 简单允许/拒绝选项
    Dropdown(Vec<PermissionOptionChoice>), // 粒度选择器
}
```

### 2.3 事件类型

- `AcpThreadEvent::ToolAuthorizationRequested` - 请求授权
- `AcpThreadEvent::ToolAuthorizationReceived` - 收到授权响应

### 2.4 响应动作

- `AllowOnce` / `AllowAlways` - 允许一次/始终允许
- `RejectOnce` / `RejectAlways` - 拒绝一次/始终拒绝

---

## 3. Agent Client Protocol Elicitation 规范

**协议版本**: `2025-11-25`  
**规范地址**: https://github.com/agentclientprotocol/agent-client-protocol/blob/main/docs/rfds/elicitation.mdx

### 3.1 Elicitation 模式

| 模式 | 用途 | 数据流 |
|------|------|--------|
| `form` | 结构化数据收集 | 协议内传输 |
| `url` | OAuth/认证/支付等敏感操作 | 浏览器/外部 |

**要求**: 客户端必须至少支持一种模式

### 3.2 请求/响应结构

#### Form Mode 请求

```json
{
  "jsonrpc": "2.0",
  "id": 43,
  "method": "session/elicitation",
  "params": {
    "sessionId": "<session-id>",
    "mode": "form",
    "message": "How would you like me to approach this refactoring?",
    "requestedSchema": {
      "type": "object",
      "properties": {
        "strategy": {
          "type": "string",
          "title": "Refactoring Strategy",
          "oneOf": [
            { "const": "conservative", "title": "Conservative" },
            { "const": "balanced", "title": "Balanced" },
            { "const": "aggressive", "title": "Aggressive" }
          ]
        }
      }
    }
  }
}
```

#### URL Mode 请求

```json
{
  "jsonrpc": "2.0",
  "id": 44,
  "method": "session/elicitation",
  "params": {
    "sessionId": "<session-id>",
    "mode": "url",
    "elicitationId": "github-oauth-001",
    "url": "https://agent.example.com/connect",
    "message": "Please authorize access to your GitHub repositories."
  }
}
```

#### 响应格式（三动作模型）

```json
// Accept
{ "jsonrpc": "2.0", "id": 43, "result": { "action": "accept", "content": { ... } } }

// Decline
{ "jsonrpc": "2.0", "id": 43, "result": { "action": "decline" } }

// Cancel
{ "jsonrpc": "2.0", "id": 43, "result": { "action": "cancel" } }
```

### 3.3 受限 JSON Schema 支持

Form mode 使用受限制的 JSON Schema 子集：

| 类型 | 支持的属性 |
|------|-----------|
| `string` | `minLength`, `maxLength`, `pattern`, `format`, `default` |
| `number` | `minimum`, `maximum`, `default` |
| `integer` | `minimum`, `maximum`, `default` |
| `boolean` | `default` |
| `enum` | `enum` 数组或 `oneOf`/`anyOf` 配合 `const`/`title` |

支持的字符串格式：`email`, `uri`, `date`, `date-time`

**不支持**: 嵌套对象、对象数组（仅枚举数组）、条件验证、自定义格式

### 3.4 客户端能力声明

```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "clientCapabilities": {
      "elicitation": {
        "form": {},
        "url": {}
      }
    }
  }
}
```

### 3.5 错误码

| Code | 名称 | 描述 |
|------|------|------|
| `-32042` | `URLElicitationRequiredError` | 需要先进行 URL 模式 elicitation |
| `-32602` | `Invalid params` | 客户端不支持该模式 |

---

## 4. 差距分析

| 特性 | Zed 当前实现 | ACP Elicitation 规范 | 差距 |
|------|-------------|---------------------|------|
| **Schema 支持** | 无（简单选项） | 受限 JSON Schema | ❌ 缺失 |
| **输入类型** | 二元（允许/拒绝） | 字符串、数字、布尔、枚举、多选 | ❌ 缺失 |
| **模式** | 无 | `form` + `url` | ❌ 缺失 |
| **范围** | 工具调用级 | Session 级 | ⚠️ 不同 |
| **方法** | 内置到工具流 | `session/elicitation` | ❌ 缺失 |
| **响应模型** | 二元（Allow/Reject） | `accept`/`decline`/`cancel` | ⚠️ 不同 |
| **验证** | 无 | Schema 验证 | ❌ 缺失 |
| **协议版本** | 0.9.4 | 2025-11-25 | ⚠️ 需升级 |

---

## 5. 安全要求

### URL Mode 安全要求
- ✅ 不允许自动获取 URL 或元数据
- ✅ 打开前必须显示完整 URL
- ✅ 必须使用安全浏览器上下文（如 SFSafariViewController）
- ✅ 应该高亮域名防止子域名欺骗
- ✅ 不应在表单字段中将 URL 渲染为可点击链接

### Form Mode 安全要求
- ✅ 禁止在 form mode 中收集敏感数据（密码、API keys、凭证）
- ✅ 敏感数据收集必须使用 URL mode

---

## 6. 实现建议

若计划为 Zed 实现 Elicitation，关键集成点：

### 6.1 需要修改的文件

| 文件 | 需要添加的功能 |
|------|--------------|
| `crates/acp_thread/src/acp_thread.rs` | 添加 `ElicitationRequest` 处理，与现有 `ToolCallStatus::WaitingForConfirmation` 并列 |
| `crates/acp_thread/src/connection.rs` | 扩展 `AgentConnection` trait 的 elicitation 能力 |
| `crates/agent_ui/src/connection_view/thread_view.rs` | 基于 JSON Schema 的表单渲染（当前只有 Flat/Dropdown 选项） |
| `Cargo.toml` | 升级 `agent-client-protocol` crate 到支持 elicitation 的版本 |

### 6.2 依赖项更新

需要确认 `agent-client-protocol` crate 的哪个版本开始支持 Elicitation 类型定义。

### 6.3 UI 设计考虑

- Form 模式：需要能够根据受限 JSON Schema 动态生成表单组件
- URL 模式：需要显示确认对话框，展示完整 URL，并提供在浏览器中打开的选项

### 6.4 与现有 Session Config Options 的整合

Zed 已有 `SessionConfigOption` 并带有一些 schema 约束，需要评估：
- 是整合到现有系统
- 还是保持独立实现

---

## 7. 相关 GitHub Issues 和 PRs

### 7.1 相关 Issue

| Issue | 状态 | 描述 |
|-------|------|------|
| [#37307](https://github.com/zed-industries/zed/issues/37307) | closed | MCP requests no longer visible in Agent UI. 提到 elicitation flows 受影响 |

### 详细的 Issue 信息

**Issue #37307 - AI: MCP requests no longer visible in Agent UI**
- **状态**: Closed (completed)
- **创建时间**: 2025-09-01
- **标签**: `area:ai`, `area:ai/mcp`, `state:needs repro`
- **核心问题**: 
  - MCP 请求不再显示在 Agent UI 中
  - 这破坏了 elicitation flows（工具似乎停滞或超时）
- **评论数**: 6
- **点赞数**: 4

### 7.2 直接相关的 PR

搜索 `repo:zed-industries/zed elicitation` 返回 0 个 PR。

---

## 8. 总结

**现状**: Zed 暂未实现 ACP Elicitation 规范。目前有 Tool Authorization 作为替代方案，但功能较为简单（仅支持二元允许/拒绝决策）。

**与规范的差距**:
1. 缺少 `session/elicitation` 方法处理
2. 不支持受限 JSON Schema 表单渲染
3. 缺少 `form` 和 `url` 两种模式
4. 缺少三动作响应模型
5. ACP crate 版本较旧

**GitHub 状态**:
- 没有发现专门实现 Elicitation 的 PR
- Issue #37307 提到 elicitation 相关的问题，但已关闭
- 社区对 MCP/Elicitation 有需求但未找到正式的开发计划

**建议**:
- 升级 `agent-client-protocol` crate 版本
- 参考现有 Tool Authorization 架构，扩展实现 Elicitation
- 优先实现 Form mode，因为 URL mode 涉及浏览器集成更复杂

---

## 9. 参考资源

- **ACP Elicitation 规范**: https://github.com/agentclientprotocol/agent-client-protocol/blob/main/docs/rfds/elicitation.mdx
- **Zed MCP 文档**: `docs/src/ai/mcp.md`
- **MCP 规范**: https://modelcontextprotocol.io/specification/draft/client/elicitation
- **Zed Issue #37307**: https://github.com/zed-industries/zed/issues/37307
