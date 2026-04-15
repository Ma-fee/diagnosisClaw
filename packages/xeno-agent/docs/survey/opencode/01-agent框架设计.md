# Agent 框架设计

## 核心理念

OpenCode 的 Agent 系统采用**多模式、分层权限**的设计，支持多个独立 Agent 在同一系统中协同工作。

## Agent 类型

### 按运行模式分类

```typescript
type AgentMode = "primary" | "subagent" | "all";
```

- **primary**: 主代理 - 用户直接交互的 Agent (build, plan)
- **subagent**: 子代理 - LLM 通过工具调用的专门 Agent (general, explore)
- **all**: 通用代理 - 既可作为主代理也可作为子代理

### 按可见性分类

- **visible**: 对用户可见，可选择切换
- **hidden**: 内部使用，不暴露给用户 (compaction, title, summary)

### 按来源分类

- **native**: 内置 Agent - 硬编码在系统中
- **custom**: 自定义 Agent - 通过配置文件定义

## Agent 定义结构

### TypeScript 接口

```typescript
namespace Agent {
  interface Info {
    name: string; // Agent 标识符
    description?: string; // 用途描述（subagent 必须有）
    mode: "subagent" | "primary" | "all";
    native?: boolean; // 是否内置
    hidden?: boolean; // 是否隐藏

    // LLM 参数
    topP?: number;
    temperature?: number;
    steps?: number; // 最大推理步数

    // 外观
    color?: string; // 界面颜色标识

    // 核心配置
    permission: PermissionNext.Ruleset; // 权限规则集
    model?: {
      modelID: string;
      providerID: string;
    };
    prompt?: string; // 系统提示词
    options: Record<string, any>; // 扩展选项
  }
}
```

## 内置 Agent 详解

### 1. build Agent

**定位**: 默认的开发 Agent，具有完整权限

```typescript
{
  name: "build",
  mode: "primary",
  permission: {
    "*": "allow",                    // 默认允许所有工具
    "question": "allow",             // 可以询问用户
    "plan_enter": "allow",          // 可以切换到 plan 模式
    "doom_loop": "ask",             // 死循环检测需询问
    "external_directory": {
      "*": "ask",                    // 访问外部目录需询问
      [Truncate.DIR]: "allow",      // 临时目录允许
    },
    "read": {
      "*": "allow",
      "*.env": "ask",                // 读取环境变量需询问
      "*.env.*": "ask",
    }
  }
}
```

**特点**:

- 完全的文件读写权限
- 可执行 bash 命令
- 可调用所有工具
- 可询问用户获取信息

### 2. plan Agent

**定位**: 只读分析 Agent，用于代码探索和规划

```typescript
{
  name: "plan",
  mode: "primary",
  permission: {
    "*": "allow",                    // 基础工具允许
    "question": "allow",             // 可以询问
    "plan_exit": "allow",           // 可以退出 plan 模式
    "edit": {
      "*": "deny",                   // 默认拒绝编辑
      ".opencode/plans/*.md": "allow"  // 仅允许编辑计划文档
    },
    "external_directory": {
      "$DATA/plans/*": "allow"       // 允许访问计划目录
    }
  }
}
```

**特点**:

- 只能编辑 `.opencode/plans/` 下的规划文档
- 不能修改源代码
- 适合探索不熟悉的代码库

### 3. general Agent (Subagent)

**定位**: 通用任务子代理

```typescript
{
  name: "general",
  mode: "subagent",
  description: "General-purpose agent for researching complex questions and executing multi-step tasks.",
  permission: {
    "*": "allow",
    "todoread": "deny",              // 不能访问父 session 的 todo
    "todowrite": "deny"
  }
}
```

**特点**:

- 继承大部分权限
- 无法访问父会话的 todo 列表
- 适合并行执行多个独立任务

### 4. explore Agent (Subagent)

**定位**: 代码搜索专用 Agent

```typescript
{
  name: "explore",
  mode: "subagent",
  description: "Fast agent specialized for exploring codebases...",
  prompt: PROMPT_EXPLORE,            // 专门的系统提示词
  permission: {
    "*": "deny",                     // 默认拒绝所有
    "grep": "allow",                 // 只允许搜索工具
    "glob": "allow",
    "list": "allow",
    "bash": "allow",
    "webfetch": "allow",
    "websearch": "allow",
    "codesearch": "allow",
    "read": "allow",
  }
}
```

**特点**:

- 权限最小化 - 只能搜索不能修改
- 专门的系统提示词指导搜索策略
- 支持 thoroughness 参数 (quick/medium/very thorough)

### 5. 隐藏 Agent

**compaction**: 上下文压缩 Agent

- 无工具权限
- 专门提示词引导压缩任务

**title**: 生成会话标题

- 无工具权限
- temperature=0.5 保证创造性

**summary**: 生成会话摘要

- 无工具权限

## Agent 加载机制

### 加载流程

```
1. 初始化内置 Agent (build, plan, general, explore等)
   ↓
2. 应用默认权限规则集
   ↓
3. 加载用户配置 (config.agent)
   ↓
4. 合并权限规则 (内置 + 用户)
   ↓
5. 处理 disable 标记
   ↓
6. 确保 Truncate.DIR 总是允许
```

### 配置合并策略

```typescript
// 1. 默认权限
const defaults = {
  "*": "allow",
  doom_loop: "ask",
  external_directory: { "*": "ask" },
  question: "deny",
};

// 2. Agent 特定权限
const agentRules = {
  question: "allow", // build 允许询问
};

// 3. 用户自定义权限
const userRules = config.permission;

// 4. 最终权限 = merge(defaults, agentRules, userRules)
const finalPermission = PermissionNext.merge(defaults, agentRules, userRules);
```

**合并顺序**: 后面的规则覆盖前面的

## 自定义 Agent

### 通过配置文件定义

```jsonc
// opencode.jsonc
{
  "agent": {
    "reviewer": {
      "name": "Code Reviewer",
      "description": "Specialized in code review",
      "mode": "subagent",
      "prompt": "You are an expert code reviewer...",
      "temperature": 0.3,
      "model": "anthropic:claude-opus",
      "permission": {
        "*": "deny",
        "read": "allow",
        "grep": "allow",
        "glob": "allow",
      },
      "options": {
        "checkStyle": true,
        "checkSecurity": true,
      },
    },
  },
}
```

### 禁用内置 Agent

```jsonc
{
  "agent": {
    "explore": {
      "disable": true,
    },
  },
}
```

## Agent 生成 (AI-Powered)

支持通过自然语言描述生成 Agent 配置：

```typescript
const result = await Agent.generate({
  description:
    "Create a security-focused agent that only reviews code for vulnerabilities",
  model: { providerID: "anthropic", modelID: "claude-opus" },
});
// => {
//   identifier: "security_reviewer",
//   whenToUse: "When you need to...",
//   systemPrompt: "You are a security expert..."
// }
```

**实现要点**:

- 使用 LLM 的 generateObject API
- 提供已存在的 Agent 列表避免冲突
- temperature=0.3 保证稳定性

## 权限与 Agent 的关系

每个 Agent 都有独立的权限规则集 (Ruleset)，详见 [03-权限系统设计.md]。

**关键设计**:

- Agent 不能修改自己的权限
- 权限在 Agent 初始化时固化
- 用户配置可以覆盖内置权限

## 默认 Agent 选择

```typescript
async function defaultAgent() {
  // 1. 优先使用 config.default_agent
  if (config.default_agent) {
    const agent = agents[config.default_agent];
    // 检查：不能是 subagent，不能是 hidden
    return agent.name;
  }

  // 2. 否则选择第一个 visible primary agent
  const primaryVisible = agents.find(
    (a) => a.mode !== "subagent" && a.hidden !== true,
  );
  return primaryVisible.name;
}
```

## 设计亮点

### 1. 权限隔离

每个 Agent 在独立的权限沙箱中运行，互不影响。

### 2. 渐进式权限

从严格到宽松：

- explore (最严格) - 只读搜索
- plan - 只读 + 有限写入
- build (最宽松) - 完全访问

### 3. 专业化分工

不同 Agent 专注不同任务：

- explore → 快速搜索
- general → 通用任务
- compaction → 压缩上下文

### 4. 可扩展性

- 通过配置轻松添加新 Agent
- 支持 AI 生成 Agent 配置
- 插件可以注册新 Agent 类型

## 实现细节

### Instance.state 模式

```typescript
const state = Instance.state(async () => {
  // 初始化逻辑
  const agents = { ... }
  return agents
})

// 使用时
const agent = await Agent.get("build")
```

**优势**:

- 按需加载配置
- 自动缓存结果
- 线程安全

### 模板字符串加载

```typescript
import PROMPT_EXPLORE from "./prompt/explore.txt";
```

Bun 支持直接导入文本文件作为字符串，简化 prompt 管理。

## 参考实现

**文件位置**: `packages/opencode/src/agent/agent.ts`

**关键函数**:

- `Agent.get(name)` - 获取 Agent 配置
- `Agent.list()` - 列出所有 Agent
- `Agent.defaultAgent()` - 获取默认 Agent
- `Agent.generate()` - AI 生成 Agent 配置
