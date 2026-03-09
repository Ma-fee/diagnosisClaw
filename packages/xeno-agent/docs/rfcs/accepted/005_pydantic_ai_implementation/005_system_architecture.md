# RFC 005: Pydantic AI 系统架构设计

## 状态
**状态**: Draft
**创建日期**: 2026-01-20
**作者**: Sisyphus
**最后更新**: 2026-01-20

## 目录
- [概述](#概述)
- [背景](#背景)
- [技术选型分析](#技术选型分析)
- [系统架构](#系统架构)
- [核心组件](#核心组件)
- [数据流](#数据流)
- [配置管理](#配置管理)
- [实施路线图](#实施路线图)
- [开放问题](#开放问题)

---

## 概述

本 RFC 描述了基于 **Pydantic AI** 的灵活、可扩展的 Agent 系统架构。该系统通过 Hook 机制实现了高度的可定制性，支持动态配置加载、Claude Skills 动态集成，以及通过 Hook 层桥接 ACP（Agent Client Protocol）的能力。

### 核心目标

1. **灵活的 Hook 系统**: 支持工具级别和对话级别的 Hook，允许拦截和转换
2. **ACP 桥接能力**: 内置工具通过 Hook 实现 ACP 协议对接
3. **动态配置**: 支持运行时配置加载和热更新
4. **Skills 集成**: 原生支持 Claude Skills 的动态发现和加载
5. **插件化架构**: 通过 Hook 和 Toolset 实现插件热加载

---

## 背景

### 调研发现总结

#### 1. OpenCode 架构研究
- **Agent 模型**: `Agent = Prompt + Permission Policy + Model Config`
- **Session Loop**: 核心会话管理循环
- **Tool 抽象**: 支持 `authorize()`, `filter_output()`, `retry()`
- **关键 Hooks**:
  - `tool.execute.before`: 工具调用前拦截
  - `tool.execute.after`: 工具调用后处理
  - `chat.messages.transform`: 消息转换
- **Event Bus**: 解耦的事件驱动架构

#### 2. ACP 协议
- **协议特性**: JSON-RPC 2.0
- **工具生命周期**: `pending → in_progress → completed/failed`
- **Session 通知流**: `session/update` 携带进度信息
- **Python SDK**: 提供 `agent/base` 和 `client` 抽象
- **关键集成点**:
  - Tool call 迁移
  - Permission 桥接
  - Content 翻译
  - MCP 服务器通过 stdio 连接

#### 3. Pydantic AI 能力
- **Hook 生命周期** (`pydantic-ai-middleware`):
  - `before_run`, `after_run`
  - `before_tool_call`, `after_tool_call`
  - `before_model_request`, `on_error`
- **装饰器模式**: `@before_tool_call`, `@after_tool_call`
- **WrapperToolset**: 允许自定义工具调用逻辑
- **工具组合**:
  - `FilteredToolset`: 上下文工具过滤
  - `PrefixedToolset`: 命名空间前缀
  - `PreparedToolset`: 自定义描述、选项
  - `ApprovalRequiredToolset`: 需人工批准
- **动态工具集**: 通过 `@agent.toolset` 和 `RunContext.dps`
- **MCP 集成**: `MCPServerStdio` 支持标准服务器

#### 4. Claude Skills 架构
- **文件格式**: Markdown (YAML frontmatter + 内容)
- **层级加载**:
  - Level 1: metadata (~100 tokens)
  - Level 2: `SKILL.md` (<5k tokens)
  - Level 3: resources
- **目录结构**: `SKILL.md`, `scripts/`, `references/`, `assets/`
- **动态发现**:
  - `~/.claude/skills/` (全局)
  - `.claude/skills/` (项目级)
  - 运行时按需加载
- **集成模式**:
  - Direct API (`container.skills` 参数)
  - Claude Agent SDK
  - Pydantic AI (第三方库)
  - Tool Emulation ( agent 中实现 `use_skill()` 工具)

---

## 技术选型分析

### 为什么选择 Pydantic AI？

| 维度 | Pydantic AI | LangChain | 其他框架 |
|------|------------|-----------|----------|
| **类型安全** | ✅ 原生 Pydantic 支持 | ⚠️ 部分支持 | ⚠️ 不统一 |
| **Hook 系统** | ✅ 丰富 (`pydantic-ai-middleware`) | ⚠️ 回调链 | ⚠️ 定制化 |
| **动态工具** | ✅ 原生支持 (WrapperToolset) | ⚠️ 复杂 | ❌ |
| **并发工具调用** | ✅ 原生支持 (asyncio.create_task) | ⚠️ 部分支持 | ⚠️ 不统一 |
| **MCP 集成** | ✅ 原生 | ⚠️ 适配器 | ❌ |
| **快速迭代** | ✅ 轻量、Pythonic | ⚠️ 庞大 | ⚠️ 小众 |
| **学习曲线** | ✅ 平缓 | ⚠️ 陡峭 | ⚠️ 不一 |

**决策**: Pydantic AI 提供了最佳的类型安全性和灵活性平衡，特别是在 Hook、并发工具调用和动态工具管理方面。**

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                          Client Layer                           │
│  (HTTP/WebSocket / Stdio / CLI)                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      ACP Protocol Layer                         │
│  - AgentRequest/Response (agent↔client)                         │
│  - Tool Call Lifecycle management                               │
│  - Session notifications (session/update)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    Hook System (Core)                           │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Agent Lifecycle Hooks                                    │ │
│  │  - before_run / after_run                                │ │
│  │  - before_model_request / on_error                       │ │
│  └──────────────────────────────────────────────────────────┘ │
│  ┌────────────┬────────────┬────────────┬────────────┐       │
│  │ Tool Hooks │ Chat Hooks │ Auth Hooks │ Log Hooks │       │
│  │  - before │ messages   │ authorize  │ emit      │       │
│  │  - after  │ transform  │ permission  │ capture   │       │
│  └─────┬──────┴─────┬──────┴─────┬──────┴─────┬──────┘        │
│        │            │            │            │                │
└────────▼────────────▼────────────▼────────────▼────────────────┘
         │            │            │            │
┌────────▼────────────────────────────────────────────────────────┐
│                     Pydantic AI Core                            │
│  - Agent (with toolsets and injections)                         │
│  - RunContext (deps, state, tools)                             │
│  - MessageFlow (prompt → response)                             │
│  - Model/LLM Abstraction                                       │
└────────┬────────────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│                  Tool & Plugin Layer                           │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Dynamic Toolsets                                         │ │
│  │  - FilteredToolset (context-based)                      │ │
│  │  - PrefixToolset (namespacing)                          │ │
│  │  - PreparedToolset (descriptions)                      │ │
│  │  - ACPBridgeToolset (protocol translation)              │ │
│  └──────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Plugin Loaders                                         │ │
│  │  - SkillsLoader (Claude Skills)                       │ │
│  │  - MCPLoader (MCP servers)                             │ │
│  │  - CustomPluginLoader (Python modules)                 │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────┬────────────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────────────────────┐
│                   Configuration & State                       │
│  - Dynamic Config (hot reload)                                 │
│  - Session State (memory, context)                             │
│  - Permissions (policy engine)                                │
│  - Caching (responses, tools)                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心组件

### 1. Agent Core

**职责**: Pydantic AI Agent 实例的封装和管理

```python
class XenoAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.toolsets: dict[str, AbstractToolset] = {}
        self.hooks: list[Hook] = []
        self._initialize_agent()

    def _initialize_agent(self):
        # 创建 Pydantic AI Agent
        self.agent = Agent(
            model=self.config.model,
            toolsets=self.toolsets,
            hooks=self.hooks,
            deps_type=AgentDependencies,
        )
```

### 2. Hook System

**职责**: 集中式 Hook 管理和执行

```python
class HookRegistry:
    hooks: dict[str, list[Hook]]

    def register(self, hook: Hook):
        """注册 Hook"""
        pass

    async def execute_before(self, event: str, ctx: HookContext):
        """执行 before hooks"""
        pass

    async def execute_after(self, event: str, ctx: HookContext):
        """执行 after hooks"""
        pass
```

**事件类型**:
- `agent.run.before`: Agent 运行前
- `agent.run.after`: Agent 运行后
- `tool.call.before`: 工具调用前
- `tool.call.after`: 工具调用后 (含错误处理)
- `message.transform`: 消息转换（输入/输出）
- `permission.request`: 权限请求

### 3. ACP Bridge

**职责**: 将 Pydantic AI 工具调用桥接到 ACP 协议

```python
class ACPBridgeToolset(AbstractToolset):
    def __init__(self, acp_client: ACPClient):
        self.acp_client = acp_client

    async def tools(self, ctx: RunContext) -> list[ToolDefinition]:
        # 1. 从 ACP Client 获取可用工具
        # 2. 转换为 Pydantic AI 工具定义
        # 3. 注册 Hook: tool.call.before → acp.notify(tool_call.started)
        # 4. 注册 Hook: tool.call.after → acp.notify(tool_call.finished)
        pass

    async def execute_tool(self, tool_name: str, args: dict):
        # 1. 发送 AgentRequest 到 ACP Client
        # 2. 等待 AgentResponse
        # 3. 解析结果并返回
        pass
```

### 4. Dynamic Loader

**职责**: 动态加载 Skills 和 MCP 插件

```python
class DynamicLoader:
    async def load_skills(self, paths: list[Path]):
        # 1. 扫描目录，发现 Skills
        # 2. 解析 SKILL.md (Level 2)
        # 3. 创建 ToolDefinition
        # 4. 动态注册到 Agent
        pass

    async def load_mcp_servers(self, config: list[MCPConfig]):
        # 1. 启动 MCPServerStdio 进程
        # 2. 列出可用工具
        # 3. 包装为 MCPServerToolset
        pass

    async def watch_and_reload(self):
        # 监听文件变化，动态重载
        pass
```

### 5. Configuration Manager

**职责**: 动态配置加载和热更新

```python
class ConfigManager:
    def __init__(self, config_files: list[Path]):
        self.config_data: dict = {}
        self.watchers: list[FileSystemWatcher] = []

    async def load_all(self):
        # 加载所有配置文件
        pass

    async def reload(self, path: Path):
        # 热重新加载配置
        pass

    def get_deps(self) -> AgentDependencies:
        # 生成 Agent 依赖注入的配置数据
        pass
```

---

## 数据流

### 正常对话流程

```
Client Request
    │
    ▼
[ACP: client/request]
    │
    ▼
[middleware: agent.before_run]
    │
    ▼
[Hook Registry: Before Hooks]
    │: permission.check, log.capture, metrics.start
    │
    ▼
[Pydantic AI: Agent.run]
    │
    ├─→ [Model Request]
    │       │
    │       ▼
    │   [middleware: before_model_request]
    │
    ├─→ [Tool Call Needed?]
    │       │ Yes
    │       ▼
    │   [Hook Registry: tool.call.before]
    │       │
    │       ▼
    │   [ACP Bridge: Translate Tool Call]
    │       │
    │       ▼
    │   [ACP: Agent Request (Tool)] → Client
    │       │
    │       ▼
    │   [ACP: Agent Response (Tool Result)]
    │       │
    │       ▼
    │   [Hook Registry: tool.call.after]
    │
    └─→ [Response Generated]
            │
            ▼
        [Hook Registry: After Hooks]
            │
            ▼
        [middleware: agent.after_run]
            │
            ▼
        [ACP: Agent Response] → Client
```

### Hook 执行顺序

```
事件: agent.run

[原序] Before Hooks
  1. permission.check()
  2. log.capture(request)
  3. metrics.start("agent_run")
  4. cache.check_lookup()

[Agent 执行] ...

[逆序] After Hooks
  4. cache.cache_result()
  3. metrics.end("agent_run")
  2. log.capture(response)
  1. permission.cleanup()

错误处理:
  └─→ on_error Hook
      └─→ Stack trace & context
```

---

## 配置管理

### 配置文件结构

```yaml
# config/agent.yaml
model: "claude-3-5-sonnet-20241022"
version: "0.1.0"

# Hook 配置
hooks:
  - type: permission
    policy: "config/policy.yaml"
  - type: logging
    level: "INFO"
    output: "logs/agent.log"
  - type: caching
    enabled: true
    ttl: 3600

# 工具集配置
toolsets:
  - type: "acp_bridge"
    config:
      client: "stdio"
  - type: "skills"
    paths:
      - "~/.claude/skills"
      - ".claude/skills"
  - type: "mcp"
    servers:
      - name: "filesystem"
        command: ["npx", "@modelcontextprotocol/server-filesystem", "/path"]
      - name: "github"
        command: ["npx", "@modelcontextprotocol/server-github"]

# 动态配置监听
watch:
  - "config/*.yaml"
  - ".claude/skills/**/SKILL.md"
  handler: "hot_reload"
```

### 运行时依赖注入

```python
class AgentDependencies:
    config: AgentConfig
    acp_client: ACPClient
    cache: CacheService
    permissions: PermissionEngine
    logger: LoggerService

    # 动态加载的工具集
    dynamic_tools: dict[str, ToolDefinition]
```

---

## 实施路线图

### Phase 1: Core Foundation (Week 1-2)
- [ ] Pydantic AI 集成和 Agent 基类
- [ ] Hook Registry 基础实现
- [ ] 配置文件加载 (YAML)

### Phase 2: Hook System (Week 2-3)
- [ ] 核心生命周期 Hooks
- [ ] Tool call before/after Hooks
- [ ] Message transformation Hooks
- [ ] 错误处理 Hooks

### Phase 3: ACP Bridge (Week 3-4)
- [ ] ACP Client 包装
- [ ] Tool call → ACP AgentRequest 转换
- [ ] ACP AgentResponse → 返回值转换
- [ ] Session notification 流

### Phase 4: Dynamic Loading (Week 4-5)
- [ ] Skills Loader (目录扫描 + 解析)
- [ ] MCP Server Loader (进程管理 + 工具列表)
- [ ] 热重载机制 (文件监视)

### Phase 5: Integration & Testing (Week 5-6)
- [ ] 端到端测试
- [ ] 性能基准测试
- [ ] 文档完善

---

## 开放问题

1. **Hook 异常处理**: 如果 `tool.call.before` Hook 抛出异常，应该如何处理？
2. **ACP 连接管理**: 多个 ACP 客户端连接时，工具命名空间如何管理？
3. **Skills 缓存**: Skills 加载后的缓存策略（内存 vs 磁盘）？
4. **权限系统**: Permission Policy 的实现细节（基于规则 vs AI 决策）？
5. **性能监控**: Hook 执行耗时监控和追踪（OpenTelemetry 集成）？

---

## 参考资料

- [RFC 001: Agent System Architecture](./001_agent_system_design/)
- [OpenCode 架构研究](../survey/opencode_architecture_research.md)
- [Agent Client Protocol](https://agentclientprotocol.com/)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [Claude Skills Specification](https://docs.anthropic.com/claude/docs/skills)
- [MCP Specification](https://modelcontextprotocol.io/)

---

**下一步**: 查看 [RFC 005.1: Hook 系统详细设计](./005_hooks_system_design.md)
