# ACP 协议 RFD 工程实现优先级

> 背景：通过 ACP 协议改造现有的诊断链路（基于 xeno-agent 和 agentpool）。
> 本文档对 ACP 协议的 protocol 和 RFDs 进行工程实现优先级分类。

---

## 术语说明

- **MVP**：Minimum Viable Product，最小可行产品版本，必须完成的核心功能
- **完整复现链路**：用于复现生产环境诊断链路的完整协议实现
- **关注列表**：值得关注的扩展功能，可根据需求选择性实现
- **暂时不需要**：当前阶段不需要实现的功能
- **需额外实现**：基于 agentpool 代码扫描结果，标注当前是否已支持
  - ✅ **已实现**：agentpool 已有完整实现
  - ⚠️ **需实现**：agentpool 尚未实现或仅部分实现
  - ❓ **待确认**：需要进一步确认实现状态

---

## 1. MVP（最小版本要求）

以下是接入 ACP 协议并支持基础诊断能力的**必需实现**项：

| Protocol/RFD | 名称 | 描述 | 根云诊断关联 | 需额外实现 |
|--------------|------|------|------------------------|------------|
| `initialize` | [Initialization](/packages/agent-client-protocol/docs/protocol/initialization.mdx) | 协议初始化、版本协商、能力交换 | | ✅ 已实现（Server 端） |
| `session/new` | [Session Setup - Creating](/packages/agent-client-protocol/docs/protocol/session-setup.mdx) | 创建新会话 | | ✅ 已实现（Server 端） |
| `session/prompt` | [Prompt Turn](/packages/agent-client-protocol/docs/protocol/prompt-turn.mdx) | 发送用户提示并接收响应 | | ✅ 已实现（Server 端） |
| `session/cancel` | [Cancellation](/packages/agent-client-protocol/docs/protocol/prompt-turn.mdx#cancellation) | 取消当前对话回合 | | ✅ 已实现（Server 端） |
| `session/update` | [Session Updates](/packages/agent-client-protocol/docs/protocol/prompt-turn.mdx#3-agent-reports-output) | Agent 向客户端报告更新（消息块、工具调用、计划等） | | ✅ 已实现（Server 端） |
| **RFD: elicitation (form)** | [Elicitation: Structured User Input](/packages/agent-client-protocol/docs/rfds/elicitation.mdx) | 结构化用户输入请求（仅 Form 模式），用于对话中收集用户反馈 | | ⚠️ **需实现**（Server 端缺失） |
| **RFD: meta-propagation** | [Meta Field Propagation Conventions](/packages/agent-client-protocol/docs/rfds/meta-propagation.mdx) | `params._meta` 元数据传播约定，用于 trace 关联 | | ✅ 已实现（schema 支持 `_meta`） |
| **RFD: agent-plan** | [Agent Plan](/packages/agent-client-protocol/docs/protocol/agent-plan.mdx) | 诊断计划展示，展示 Agent 的诊断思路 | | ⚠️ **部分实现**（Server 端需完善） |

### 1.1 MVP 基础协议核心（Server 端）

| 方法/通知 | 方向 | 描述 | 根云诊断关联 | 需额外实现 |
|-----------|------|------|--------------|------------|
| `initialize` | Client → Agent | 协议初始化，交换能力信息 | | ✅ 已实现 |
| `session/new` | Client → Agent | 创建诊断会话 | | ✅ 已实现 |
| `session/prompt` | Client → Agent | 发送诊断请求 | | ✅ 已实现 |
| `session/cancel` | Client → Agent | 取消当前诊断流程 | | ✅ 已实现 |
| `session/update` (notification) | Agent → Client | 报告诊断进度和状态（内容块、工具调用、计划） | | ✅ 已实现 |
| `elicitation` (form) | Agent → Client | 请求结构化用户输入（表单模式） | | ⚠️ **需实现** |
| `agent-plan` | Agent → Client | 展示诊断计划和执行步骤 | | ⚠️ **部分实现** |

---

## 2. 完整复现链路的最优要求

实现生产级诊断链路所需的重要功能，优先实现后可获得更好的诊断体验：

| RFD | 名称 | 能力描述 | 根云诊断关联 | 需额外实现 |
|-----|------|---------|--------------|------------|
| `session/request_permission` | [Permission Requests](/packages/agent-client-protocol/docs/protocol/tool-calls.mdx#requesting-permission) | 请求工具调用权限 | | ✅ 已实现（Server 端） |
| **RFD: session-config-options** | [Session Config Options](/packages/agent-client-protocol/docs/rfds/session-config-options.mdx) | 会话级配置选项（模型选择、模式切换等） | | ✅ 已实现（Server 端） |
| **RFD: mcp-over-acp** | [MCP-over-ACP](/packages/agent-client-protocol/docs/rfds/mcp-over-acp.mdx) | 通过 ACP 通道传输 MCP 协议，允许 Agent 调用 Client 提供的 MCP Server | | ✅ 已实现（Server 端） |
| **RFD: session-resume** | [Resuming of Existing Sessions](/packages/agent-client-protocol/docs/rfds/session-resume.mdx) | 恢复现有会话（不返回历史消息），用于支持长诊断流程 | | ✅ 已实现（Server 端，UNSTABLE） |
| **RFD: session-list** | [Session List](/packages/agent-client-protocol/docs/rfds/session-list.mdx) | 列举会话，支持分页和过滤，用于会话管理 | | ✅ 已实现（Server 端，UNSTABLE） |
| **RFD: session-delete** | [Session Delete](/packages/agent-client-protocol/docs/rfds/session-delete.mdx) | 删除会话，用于会话生命周期管理 | | ⚠️ **需实现**（Server 端缺失） |
| **RFD: session-load** | [Loading Sessions](/packages/agent-client-protocol/docs/protocol/session-setup.mdx#loading-sessions) | 加载历史会话（包含完整消息历史），用于查看历史诊断 | | ✅ 已实现（Server 端） |
| **RFD: session-close** | [Session Close](/packages/agent-client-protocol/docs/rfds/session-close.mdx) | 主动关闭会话，释放资源 | | ✅ 已实现（Server 端，session/stop） |
| **RFD: session-fork** | [Session Fork](/packages/agent-client-protocol/docs/rfds/session-fork.mdx) | 分叉会话，用于探索性诊断 | | ✅ 已实现（Server 端，UNSTABLE） |
| **RFD: slash-commands** | [Slash Commands](/packages/agent-client-protocol/docs/protocol/slash-commands.mdx) | 斜杠命令支持，用于快捷操作 | | ✅ 已实现（Server 端） |
| **RFD: session-modes** | [Session Modes](/packages/agent-client-protocol/docs/protocol/session-modes.mdx) | 会话模式切换（Ask/Code/Agent 等） | | ✅ 已实现（Server 端） |

### 2.1 完整链路 - 文件系统操作（Server 端）

| 方法 | 方向 | 描述 | 根云诊断关联 | 需额外实现 |
|------|------|------|--------------|------------|
| `fs/read_text_file` | Client → Agent | 读取文本文件 | | ✅ 已实现 |
| `fs/write_text_file` | Client → Agent | 写入文本文件 | | ✅ 已实现 |
| `fs/read_binary_file` | Client → Agent | 读取二进制文件 | | ❓ 待确认 |
| `fs/create_directory` | Client → Agent | 创建目录 | | ❓ 待确认 |
| `fs/remove` | Client → Agent | 删除文件/目录 | | ❓ 待确认 |
| `fs/list` | Client → Agent | 列出目录内容 | | ⚠️ **需实现** |
| `fs/diff` | Client → Agent | 文件差异对比 | | ⚠️ **需实现** |
| `fs/edit` | Client → Agent | 文件编辑操作 | | ⚠️ **需实现** |

### 2.2 完整链路 - 终端操作（Server 端）

| 方法 | 方向 | 描述 | 根云诊断关联 | 需额外实现 |
|------|------|------|--------------|------------|
| `terminal/create` | Client → Agent | 创建终端 | | ❓ 待确认（Client 端已实现） |
| `terminal/output` | Client → Agent | 获取终端输出 | | ❓ 待确认（Client 端已实现） |
| `terminal/release` | Client → Agent | 释放终端 | | ❓ 待确认（Client 端已实现） |
| `terminal/wait_for_exit` | Client → Agent | 等待命令执行完成 | | ❓ 待确认（Client 端已实现） |
| `terminal/kill` | Client → Agent | 终止终端命令 | | ❓ 待确认（Client 端已实现） |

### 2.3 子智能体渲染（Subagent Rendering）

| 功能 | 描述 | 根云诊断关联 | 需额外实现 |
|------|------|--------------|------------|
| **Subagent 渲染** | 在 ACP Server 端实现子智能体的渲染和管理，支持诊断链路中多智能体协作的可视化 | | ⚠️ **需实现**（Server 端缺失） |

---

## 3. 关注列表

以下功能值得关注，可根据具体需求和资源情况选择性实现：

| RFD | 名称 | 描述 | 根云诊断关联 | 需额外实现 |
|-----|------|------|--------------|------------|
| **RFD: elicitation (url)** | [Elicitation: URL Mode](/packages/agent-client-protocol/docs/rfds/elicitation.mdx) | URL 模式用户输入（OAuth 等外部流程）| | ⚠️ **暂不需要**（Form 模式已满足需求） |
| **RFD: authenticate** | [Authentication](/packages/agent-client-protocol/docs/protocol/schema#authenticate) | 认证机制 | | ❓ 待明确用途（暂不需要显式认证） |
| **RFD: request-cancellation** | [Request Cancellation](/packages/agent-client-protocol/docs/rfds/request-cancellation.mdx) | LSP 风格的细粒度请求取消 `$/cancel_request` | | ⚠️ **暂不需要**（session/cancel 已满足基本需求） |
| **RFD: proxy-chains** | [Agent Extensions via ACP Proxies](/packages/agent-client-protocol/docs/rfds/proxy-chains.mdx) | ACP 代理链，支持在 Client 和 Agent 之间插入代理组件 | | ⚠️ **需实现** |
| **RFD: session-usage** | [Session Usage and Context Status](/packages/agent-client-protocol/docs/rfds/session-usage.mdx) | 令牌使用统计、成本追踪、上下文窗口状态 | | ✅ 已实现（Server 端，UNSTABLE） |
| **RFD: agent-telemetry-export** | [Agent Telemetry Export](/packages/agent-client-protocol/docs/rfds/agent-telemetry-export.mdx) | Agent 遥测数据导出（OpenTelemetry） | | ⚠️ **需实现** |
| **RFD: session-info-update** | [Session Info Update](/packages/agent-client-protocol/docs/rfds/session-info-update.mdx) | 会话信息更新通知 | | ✅ 已实现（Server 端） |
| **RFD: diff-delete** | [Diff Delete](/packages/agent-client-protocol/docs/rfds/diff-delete.mdx) | 差异删除支持 | | ❓ 待确认 |
| **RFD: boolean-config-option** | [Boolean Config Option](/packages/agent-client-protocol/docs/rfds/boolean-config-option.mdx) | 布尔类型的配置选项支持 | | ❓ 待确认 |
| **RFD: auth-methods** | [Auth Methods](/packages/agent-client-protocol/docs/rfds/auth-methods.mdx) | 多种认证方式支持 | | ⚠️ **需实现** |
| **RFD: logout-method** | [Logout Method](/packages/agent-client-protocol/docs/rfds/logout-method.mdx) | 登出功能 | | ⚠️ **需实现** |
| **RFD: acp-agent-registry** | [ACP Agent Registry](/packages/agent-client-protocol/docs/rfds/acp-agent-registry.mdx) | ACP Agent 注册表，用于发现和管理 Agent | | ⚠️ **需实现** |

---

## 4. 当前缺失功能清单（需额外实现汇总）

基于 agentpool ACP Server 端代码扫描，以下功能**需要额外实现**：

| 类别 | 功能/方法 | 优先级 | 说明 |
|------|-----------|--------|------|
| **用户交互** | `elicitation` (form) | **MVP** | 结构化用户输入请求，用于诊断中收集用户反馈 |
| **文件系统** | `fs/list` | **完整链路** | 列出目录内容 |
| **文件系统** | `fs/diff` | **完整链路** | 文件差异对比 |
| **文件系统** | `fs/edit` | **完整链路** | 文件编辑操作 |
| **会话管理** | `session/delete` | **完整链路** | 删除会话 |
| **智能体协作** | **Subagent 渲染** | **完整链路** | 子智能体渲染和管理，支持诊链路多智能体协作可视化 |
| **诊断计划** | `agent-plan` 执行逻辑 | **MVP** | 计划展示 schema 已定义，Server 端执行逻辑需完善 |

### 4.1 缺失功能详细说明

#### 4.1.1 Elicitation (Form 模式) - MVP 关键
- **当前状态**：schema 未定义，Server 端缺失实现
- **功能描述**：允许 Agent 在对话过程中向用户请求结构化输入（表单）
- **使用场景**：诊断过程中需要用户选择故障类型、确认设备参数等
- **实现要点**：
  - 定义 `session/elicitation` 方法（Agent → Client）
  - 支持受限 JSON Schema（string, number, boolean, enum）
  - 支持 3 种用户响应：accept, decline, cancel
  - Client 需渲染表单 UI

#### 4.1.2 文件系统扩展操作
- **fs/list**：列出目录内容（文件/子目录列表）
- **fs/diff**：对比文件差异（类似 git diff）
- **fs/edit**：执行文件编辑操作（插入、删除、替换）

#### 4.1.3 Subagent 渲染
- **当前状态**：完全缺失
- **功能描述**：在 ACP Server 端支持子智能体的渲染和管理
- **使用场景**：故障诊断链路中多智能体协作（如 fault_expert 委派给 equipment_expert）
- **实现要点**：
  - 支持子智能体会话创建和管理
  - 子智能体状态同步到 Client
  - 结果聚合和展示

---

## 5. 暂时不需要的列表

当前阶段不需要实现的功能，可作为未来扩展参考：

| RFD | 名称 | 描述 | 暂不实现原因 | 需额外实现 |
|-----|------|------|--------------|------------|
| **RFD: next-edit-suggestions** | [Next Edit Suggestions](/packages/agent-client-protocol/docs/rfds/next-edit-suggestions.mdx) | 代码编辑建议（类似 GitHub Copilot NES） | 和诊断对话场景无关 | N/A |
| **RFD: introduce-rfd-process** | [RFD Process](/packages/agent-client-protocol/docs/rfds/introduce-rfd-process.mdx) | RFD 流程本身 | 这是 ACP 规范开发流程，非协议实现 | N/A |
| **RFD: rust-sdk-v1** | [Rust SDK v1](/packages/agent-client-protocol/docs/rfds/rust-sdk-v1.mdx) | Rust SDK v1 版本规划 | 这是 SDK 实现规划，非协议功能 | N/A |

---

## 附录：协议能力矩阵

### ACP Capability 汇总（Server 端）

| Capability | 描述 | 优先级 | 需额外实现 |
|------------|------|--------|------------|
| `fs.readTextFile` | 读取文本文件 | **完整链路** | ✅ 已实现 |
| `fs.writeTextFile` | 写入文本文件 | **完整链路** | ✅ 已实现 |
| `fs.list` | 列出目录内容 | **完整链路** | ⚠️ **需实现** |
| `fs.diff` | 文件差异对比 | **完整链路** | ⚠️ **需实现** |
| `fs.edit` | 文件编辑操作 | **完整链路** | ⚠️ **需实现** |
| `terminal` | 终端操作 | **完整链路** | ❓ Client 端已实现，Server 需确认 |
| `loadSession` | 加载会话 | **完整链路** | ✅ 已实现 |
| `sessionCapabilities.list` | 会话列表 | **完整链路** | ✅ 已实现 (UNSTABLE) |
| `sessionCapabilities.delete` | 删除会话 | **完整链路** | ⚠️ **需实现** |
| `sessionCapabilities.resume` | 恢复会话 | **完整链路** | ✅ 已实现 (UNSTABLE) |
| `sessionCapabilities.fork` | 分叉会话 | **完整链路** | ✅ 已实现 (UNSTABLE) |
| `mcpCapabilities.acp` | MCP-over-ACP 支持 | **完整链路** | ✅ 已实现 |
| `elicitation.form` | 表单模式用户输入 | **MVP** | ⚠️ **需实现** |
| `configOptions` | 会话配置选项 | **完整链路** | ✅ 已实现 |
| `subagent.render` | 子智能体渲染 | **完整链路** | ⚠️ **需实现** |

---

## 实现路线图建议（更新版）

### Phase 1: MVP 核心（4-6 周）
1. ✅ 基础协议实现（initialize, session/new, session/prompt, cancel, update）- Server 端已有
2. ⚠️ **用户输入交互（elicitation form）**- **需新增实现（Server 端）**
3. ⚠️ 诊断计划展示（agent-plan 执行逻辑）- Server 端需完善
4. ✅ Meta 传播约定 - 已有

### Phase 2: 完整链路（6-8 周）
1. ✅ 会话生命周期管理（resume, list, fork, load, stop）- Server 端已有
2. ⚠️ session-delete - 需实现（Server 端）
3. ⚠️ **文件系统扩展（fs/list, fs/diff, fs/edit）**- **需实现**
4. ⚠️ **子智能体渲染（Subagent Rendering）**- **需实现**
5. ✅ MCP-over-ACP 支持 - 已有
6. ✅ 会话配置选项（config-options）- 已有
7. ✅ 会话模式支持（session-modes）- 已有

### Phase 3: 高级功能（可选，按需实现）
1. ⚠️ 代理链（proxy-chains）- 需实现
2. ⚠️ 遥测导出（agent-telemetry-export）- 需实现
3. ✅ 使用统计（session-usage）- 已有 (UNSTABLE)

---

## 关键发现摘要

基于 agentpool ACP Server 端代码扫描结果：

### 已实现的核心功能（✅ Server 端）
- 完整的基础协议：initialize, session/new, session/prompt, session/cancel, session/update
- 会话管理：session/load, session/list, session/resume, session/fork, session/stop
- 配置管理：session/set_mode, session/set_model, session/set_config_option
- 文件系统基础：fs/read_text_file, fs/write_text_file
- MCP-over-ACP：支持 Stdio/HTTP/SSE MCP 服务器
- Session Updates：消息块、工具调用、计划、模式变更等

### 需要额外实现（⚠️ Server 端）
1. **elicitation (form)** - ⚠️ **MVP 关键依赖**：结构化用户输入请求
2. **fs/list, fs/diff, fs/edit** - 文件系统扩展操作
3. **session-delete** - 会话删除功能
4. **subagent 渲染** - 子智能体渲染和管理
5. **agent-plan 执行逻辑** - 计划展示执行逻辑完善

### 状态说明
- 部分功能标记为 UNSTABLE（session/resume, session/list, session/fork, usage_update）
- Terminal 操作已在 Client 端实现，Server 端需确认是否需要支持
- authenticate 用途尚不明确，暂不需要显式认证

---

*本优先级文档基于 ACP 协议（截止 2025-2026 年版本）和 agentpool ACP Server 端代码扫描结果制定。*
*扫描时间：2026-03-16*
