# OpenCode 项目概览

## 项目简介

OpenCode 是一个**开源的 AI 编程助手**，旨在为开发者提供智能的工具使用和代码辅助能力。

### 项目目标

- **100% 开源** - 没有供应商锁定
- **供应商无关** - 支持 Claude、OpenAI、Google、本地模型等
- **客户端/服务器架构** - 将智能层(服务器)与展示层(CLI、TUI、Web、移动端)分离
- **专注于 TUI** - 由终端爱好者打造,推动终端用户体验的边界
- **内置 LSP 支持** - 一等公民级别的语言服务器协议集成
- **ACP 合规** - 实现 Agent Client Protocol 以保证互操作性

### 核心差异化特性

与 Claude Code 等产品相比:

1. **完全开源** - 透明的代码库和开发流程
2. **模型无关** - 不绑定特定 AI 服务商
3. **开箱即用的 LSP** - 代码理解和导航能力
4. **TUI 优先** - 由 Neovim 用户和 terminal.shop 创作者打造
5. **客户端/服务器分离** - 支持远程运行和多客户端接入

## 技术栈

### 运行时与语言

- **Bun** - 高性能 JavaScript 运行时
- **TypeScript** - 全栈类型安全
- **ESM 模块** - 现代 JavaScript 模块系统
- **Zod** - 运行时模式验证

### 核心依赖

```json
{
  "ai": "Vercel AI SDK - LLM 抽象层",
  "hono": "快速的 Web 框架",
  "@modelcontextprotocol/sdk": "MCP 协议支持",
  "@agentclientprotocol/sdk": "ACP 协议支持",
  "zod": "Schema 验证",
  "@opentui/solid": "TUI 界面框架"
}
```

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                    客户端层                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐        │
│  │ CLI  │  │ TUI  │  │ Web  │  │ Desktop  │        │
│  └──┬───┘  └──┬───┘  └──┬───┘  └────┬─────┘        │
└─────┼─────────┼─────────┼───────────┼──────────────┘
      │         │         │           │
      └─────────┴─────────┴───────────┘
                     │
              HTTP/SSE/WebSocket
                     │
      ┌──────────────▼──────────────────┐
      │      HTTP Server (Hono)        │
      │  ┌──────────────────────────┐  │
      │  │   RESTful API + SSE      │  │
      │  │   OpenAPI Spec           │  │
      │  └──────────────────────────┘  │
      └──────────────┬──────────────────┘
                     │
      ┌──────────────▼──────────────────┐
      │          核心引擎               │
      │  ┌────────┐  ┌────────┐        │
      │  │ Agent  │  │Session │        │
      │  │ System │  │Manager │        │
      │  └────┬───┘  └───┬────┘        │
      │       │          │             │
      │  ┌────▼──────────▼────┐        │
      │  │   Tool Registry    │        │
      │  │  (25+ built-in)    │        │
      │  └────────────────────┘        │
      │                                │
      │  ┌────────────────────┐        │
      │  │  Event Bus         │        │
      │  │  (publish/subscribe)│        │
      │  └────────────────────┘        │
      └──────────────┬──────────────────┘
                     │
      ┌──────────────▼──────────────────┐
      │        持久化层                 │
      │  ┌────────────────────────┐    │
      │  │  JSON File Storage     │    │
      │  │  ~/.local/state/opencode│   │
      │  └────────────────────────┘    │
      └─────────────────────────────────┘
```

## 核心概念

### 1. Agent (代理)

不同权限和行为模式的 AI 智能体:

- **Primary Agents** - 用户可选择的主要模式(build, plan)
- **Subagents** - LLM 调用的专门任务代理(general, explore)
- **System Agents** - 内部使用的系统代理(compaction, title, summary)

### 2. Session (会话)

管理对话历史和状态:

- 消息历史(用户消息 + AI 响应)
- 上下文压缩和修剪
- 快照和差异追踪
- 父子会话关系

### 3. Tool (工具)

LLM 可调用的功能:

- 文件操作(read, write, edit, patch)
- 代码搜索(grep, glob, codesearch)
- Shell 执行(bash)
- Web 功能(webfetch, websearch)
- LSP 操作(定义跳转、引用查找等)
- 子任务代理(task)

### 4. Message & Parts (消息与部件)

消息由多个部件组成:

- **TextPart** - 文本内容
- **ToolPart** - 工具调用及其结果
- **ReasoningPart** - 推理过程
- **FilePart** - 文件附件
- **SnapshotPart** - 代码快照
- **StepPart** - 步骤边界标记

### 5. Permission System (权限系统)

细粒度的工具访问控制:

- 基于模式匹配的规则
- 每个 Agent 独立的权限集
- 三种动作: `allow`, `deny`, `ask`
- 用户批准缓存

## 项目结构

```
opencode/
├── packages/
│   ├── opencode/          # 核心引擎
│   │   ├── src/
│   │   │   ├── agent/     # Agent 系统
│   │   │   ├── session/   # 会话管理
│   │   │   ├── tool/      # 工具实现
│   │   │   ├── server/    # HTTP 服务器
│   │   │   ├── storage/   # 持久化
│   │   │   ├── permission/# 权限系统
│   │   │   ├── provider/  # LLM 提供商
│   │   │   ├── plugin/    # 插件系统
│   │   │   └── ...
│   ├── sdk/js/            # JavaScript SDK
│   ├── console/           # Web 控制台
│   ├── desktop/           # 桌面应用(Tauri)
│   ├── slack/             # Slack 集成
│   └── ...
├── sdks/
│   └── vscode/            # VSCode 扩展
└── ...
```

## 数据流

### 典型的对话循环

```
1. 用户输入 → HTTP API → Session.prompt()
                              ↓
2. 创建 User Message → 添加 TextPart
                              ↓
3. SessionProcessor.process() ← 启动处理循环
                              ↓
4. LLM.stream() → 流式响应
   ├─ reasoning-delta → 更新 ReasoningPart
   ├─ text-delta → 更新 TextPart
   ├─ tool-call → 创建 ToolPart
   │               ↓
   │          执行工具 → 权限检查 → 执行
   │               ↓
   │          更新 ToolPart (completed/error)
   └─ finish-step → 保存 StepFinishPart
                              ↓
5. 检查上下文溢出 → 如需要则触发 compaction
                              ↓
6. 返回结果 → 通过 SSE 推送给客户端
```

## 存储模型

### 文件结构

```
~/.local/state/opencode/storage/
├── session/
│   └── <projectID>/
│       └── <sessionID>.json
├── message/
│   └── <sessionID>/
│       └── <messageID>.json
├── part/
│   └── <messageID>/
│       └── <partID>.json
├── project/
│   └── <projectID>.json
└── session_diff/
    └── <sessionID>.json
```

### 特点

- **基于文件的存储** - 简单、可调试、Git 友好
- **文件锁定** - 支持并发访问
- **自动迁移** - 版本升级时自动迁移数据
- **惰性初始化** - 按需加载

## 插件系统

### 插件加载位置

1. `~/.config/opencode/plugin/*` - 全局插件
2. `.opencode/plugin/*` - 项目级插件
3. 配置文件中的 `plugin` 数组

### 插件能力

- **Hooks** - 拦截和修改行为
  - `config` - 配置加载
  - `tool.execute` - 工具执行
  - `permission.ask` - 权限请求
  - `event` - 事件订阅
  - 等等

- **自定义工具** - 添加新的工具
- **自定义 Agent** - 定义新的 Agent 类型
- **Provider 集成** - 添加新的 LLM 提供商

## 总结

OpenCode 是一个设计精良的、模块化的 AI 编程助手框架:

1. **清晰的架构分层** - 客户端、服务器、核心、存储
2. **强大的工具系统** - 25+ 内置工具,易于扩展
3. **灵活的 Agent 系统** - 多种 Agent 模式和权限控制
4. **健壮的会话管理** - 上下文压缩、快照、父子会话
5. **事件驱动设计** - 解耦的组件通信
6. **可扩展性** - 插件系统支持无限扩展

这些设计使 OpenCode 成为构建 AI 编程助手的优秀参考实现。
