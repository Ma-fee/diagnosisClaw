# RFC 005: Pydantic AI Implementation

本目录包含基于 **Pydantic AI** 的 Xeno Agent 系统架构设计文档。

---

## 目录

| RFC 文档 | 描述 | 状态 |
|---------|------|-----|
| [005_system_architecture.md](./005_system_architecture.md) | 系统整体架构，包括技术选型、核心组件、数据流 | 📄 Draft |
| [005_hooks_system_design.md](./005_hooks_system_design.md) | Hook 系统详细设计，包括接口定义、预置 Hooks、最佳实践 | 📄 Draft |
| [005_acp_bridge_design.md](./005_acp_bridge_design.md) | ACP 协议桥接设计，包括工具生命周期、错误处理 | 📄 Draft |
| [005_plugins_and_skills_loading.md](./005_plugins_and_skills_loading.md) | 动态插件和 Skills 加载系统，包括热重载、安全考虑 | 📄 Draft |

---

## 快速导航

### 核心设计

1. **[系统架构](./005_system_arcitecture.md)**: 从全局视角理解系统的各个层次
2. **[Hook 系统](./005_hooks_system_design.md)**: 深入 Hook 的实现细节和最佳实践
3. **[ACP 桥接](./005_acp_bridge_design.md)**: 理解如何将 Pydantic AI 工具调用转换为 ACP 消息
4. **[插件系统](./005_plugins_and_skills_loading.md)**: 学习如何动态加载和管理 Skills/MCP/自定义插件

### 主题索引

#### 🔌 Hooks
- Agent Lifecycle Hooks: `agent.run.before/after`
- Tool Call Hooks: `tool.call.before/after`
- **并发工具调用 Hook**: 支持并行工具调用控制（`sequential`, `parallel_tool_calls`, `with agent.sequential_tool_calls()`）- [详见并发工具调用](./005_hooks_system_design.md#并发工具调用-parallel-tool-calling)
- Message Transform Hooks: `message.transform.input/output`
- Error Handling Hooks: `on_error`
- Hook Registry: [详见 Hook 系统](./005_hooks_system_design.md)

#### 🛠️ ACP Integration
- Tool Call Lifecycle: `pending → in_progress → completed/failed`
- ACPBridgeToolset: 桥接工具集
- Session Notifications: `session/update`
- Transport Layer: Stdio/WebSocket/HTTP
- [详见 ACP 桥接](./005_acp_bridge_design.md)

#### 🔌 Plugins
- Claude Skills: Markdown 格式，三层加载
- MCP Servers: `MCPServerStdio`, `@modelcontextprotocol/server-*`
- Custom Plugins: Python 模块动态加载
- Hot Reload: 文件监视器
- [详见插件系统](./005_plugins_and_skills_loading.md)

---

## 设计原则

### 1. 灵活的 Hook 系统
- 粒度控制：支持 Agent、Tool、Message 级别的拦截
- 可组合性：链式调用，支持顺序和逆序执行
- 异步友好：所有 Hook 都是异步的

### 2. ACP 协议透明
- 双向通信：Agent ↔ Client 完整的消息流
- Session 同步：维护状态一致性
- 工具生命周期：正确映射 ACP 的状态机

### 3. 动态配置
- 热重载：运行时重载插件和配置
- 命名空间隔离：`skills:pdf_processor:extract_text`
- 配置驱动：YAML 配置文件

### 4. 类型安全
- 原生 Pydantic 支持：所有数据模型都经过验证
- 强类型 Hooks：编译时检查 Hook 参数
- LSP 友好：完整的类型提示

---

## 技术选型

| 技术 | 原因 |
|-----|------|
| [Pydantic AI](https://ai.pydantic.dev/) | 轻量级、类型安全、Hook 丰富 |
| [ACP (Agent Client Protocol)](https://agentclientprotocol.com/) | 标准化的 Agent-Client 通信 |
| [Claude Skills](https://docs.anthropic.com/claude/docs/skills) | 官方技能生态，Markdown 格式 |
| [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) | 标准化的工具协议 |

---

## 实施路线图

### ✅ Phase 1: Core Foundation (Week 1-2)
- [ ] Pydantic AI 集成和 Agent 基类
- [ ] Hook Registry 基础实现
- [ ] 配置文件加载 (YAML)

### 🔨 Phase 2: Hook System (Week 2-3)
- [ ] 核心生命周期 Hooks
- [ ] Tool call before/after Hooks
- [ ] Message transformation Hooks
- [ ] 错误处理 Hooks

### 🔗 Phase 3: ACP Bridge (Week 3-4)
- [ ] ACP Client 包装
- [ ] Tool call → ACP AgentRequest 转换
- [ ] ACP AgentResponse → 返回值转换
- [ ] Session notification 流

### 🔌 Phase 4: Dynamic Loading (Week 4-5)
- [ ] Skills Loader (目录扫描 + 解析)
- [ ] MCP Server Loader (进程管理 + 工具列表)
- [ ] 热重载机制 (文件监视)

### ✅ Phase 5: Integration & Testing (Week 5-6)
- [ ] 端到端测试
- [ ] 性能基准测试
- [ ] 文档完善

---

## 相关 RFC

- [RFC 001: Agent System Architecture](../001_agent_system_design/)
- [RFC 002: Reproduction Tasks](../002_reproduction_tasks.md)
- [RFC 003: HITL Migration](../003_hitl_migration.md)
- [RFC 004: Skills Refactor](../004_skills_refactor.md)

---

## 调研参考

### OpenCode 架构研究
- **文档位置**: [../survey/opencode_architecture_research.md](../survey/opencode_architecture_research.md)
- **关键发现**:
  - Agent 抽象：`Prompt + Permission Policy + Model Config`
  - Session Loop 管理会话循环
  - Key Hooks: `tool.execute.before/after`, `chat.messages.transform`
  - Event Bus 架构

### ACP 协议
- **文档位置**: [../../agent-client-protocol/](../../agent-client-protocol/)
- **关键发现**:
  - JSON-RPC 2.0 协议
  - Tool Call 生命周期：`pending → in_progress → completed/failed`
  - Session Notifications 流
  - Python SDK 提供 agent/client 抽象

### Pydantic AI
- **官方文档**: https://ai.pydantic.dev/
- **关键发现**:
  - Hook 系统 (`pydantic-ai-middleware`)
  - WrapperToolset 自定义工具调用
  - FilteredToolset, PrefixedToolset 等工具组合
  - MCP 集成 (`MCPServerStdio`)

### Claude Skills
- **官方文档**: https://docs.anthropic.com/claude/docs/skills
- **关键发现**:
  - Markdown 格式 (YAML frontmatter + content)
  - 三层渐进式加载：Level 1 (metadata), Level 2 (SKILL.md), Level 3 (resources)
  - 动态发现：`~/.claude/skills/` 和 `.claude/skills/`

---

## 开放问题

### 系统架构
- [ ] **性能优化**: Hook 链过长时的性能优化策略？
- [ ] **分布式追踪**: 是否 OpenTelemetry 集成以追踪跨模块调用？

### Hook 系统
- [ ] **Hook 并发**: 多 Agent 共享 Hook Registry 时的并发处理？
- [ ] **Hook 动态加载**: 运行时注册/卸载 Hook 的安全性？

### ACP 桥接
- [ ] **Session 管理**: 是否需要持久化 Session 状态到数据库？
- [ ] **工具调用链**: 工具调用工具的递归处理策略？

### 插件系统
- [ ] **插件隔离**: 是否为每个插件创建独立的 Python 进程/虚拟环境？
- [ ] **版本管理**: 同一插件不同版本的处理机制？
- [ ] **依赖冲突**: 插件间 Python 依赖的冲突解决？

---

## 贡献

如果你对本 RFC 有任何疑问或建议，请：
1. 创建 Issue 讨论开放问题
2. 提交 PR 改进文档
3. 在团队会议中讨论

---

**最后更新**: 2026-01-20
**维护者**: Sisyphus
