# Draft: Agent Framework SDK RFC

## 会话信息
- 开始时间: 2026-01-21
- 目标: 设计并构建 agent framework SDK（基于 PydanticAI）
- 输出: RFC 需求文档 + 架构设计文档

## 用户已有材料
- ✅ 生产系统设计: RFC 001 - 工程机械故障诊断 Agent 系统
- ✅ 框架调研: OpenCode、Oh My OpenCode、DCP、PydanticAI
- ✅ 现有实现: xeno-agent/crewai（将被忽略，全新起步）
- ✅ RFC 005: PydanticAI 实现设计（参考）

## 需求收集 (进行中)

### 已确认的需求
- [ ] 待用户确认

### 技术决策
- [ ] 待讨论

### 研究发现

### OpenCode 架构核心特点
- **多模式 Agent**: primary(主代理) / subagent(子代理) / all(通用)
- **分层权限**: explore(只读) → plan(分析) → build(完全访问)
- **配置驱动**: Agent = Prompt + Permission Policy + Model Config
- **技术栈**: TypeScript + Bun + Zod + Vercel AI SDK
- **扩展机制**: Hook 系统(6个Hook点) + 插件系统

### 调研框架对比
| 框架 | 定位 | 核心特性 |
|-----|------|---------|
| OpenCode | 单一Agent基础框架 | 轻量级配置驱动、权限系统、工具抽象 |
| Oh My OpenCode | 多Agent编排插件 | Manager-Worker模型、30+ Hooks、动态Prompt |
| DCP | 上下文修剪插件 | 双层修剪(自动+LLM)、三轮保护 |

## 关键研究发现

### 项目现状分析

#### 1. 现有代码库状态
- **当前架构**: 基于 CrewAI 的 Agent 系统
- **核心模块**: `src/xeno_agent/crewai/` 包含完整的 Flow/Signal/Agent/Tool 实现
- **配置管理**: YAML 配置 + python-dotenv 环境变量
- **未使用**: ❌ Pydantic Settings（仅使用 BaseModel 验证）
- **项目管理**: 使用 uv

#### 2. 已有 RFC 005 规划
📄 **文档位置**: `packages/xeno-agent/docs/rfc/005_pydantic_ai_implementation/`

**设计已完成**:
- Hook 系统详细设计（Agent/Tool/Message 级别）
- ACP 协议桥接设计
- 动态插件和 Skills 加载机制
- 5-Phase 实施路线图

**设计原则**:
1. 灵活的 Hook 系统（粒度控制、可组合性、异步友好）
2. ACP 协议透明（双向通信、Session 同步、工具生命周期）
3. 动态配置（热重载、命名空间隔离、YAML 驱动）
4. 类型安全（Pydantic 验证、强类型 Hooks、LSP 友好）

#### 3. PydanticAI 核心能力
- **核心抽象**: Agent[DepT, OutT], Tool, RunContext, Toolset, Graph
- **Hook 系统**: before_run/after_run, before_tool_call/after_tool_call, message.transform, on_error
- **Toolset 组合**: FunctionToolset, FilteredToolset, PrefixedToolset, CombinedToolset, WrapperToolset
- **依赖注入**: RunContext[MyDeps] 类型安全注入
- **MCP 集成**: 原生 MCPServerStdio 支持
- **vs LangChain**: 轻量库 vs 重框架、类型安全 vs 生态全面

### 待解答的问题
- [ ] "线上生产环境" 具体指什么系统？
- [ ] ACP 扩展在第一阶段的优先级？
- [ ] 配置文件格式偏好？
- [ ] 与现有 xeno-agent 代码的关系？

### 范围边界
- 包含: 待定
- 排除: 待定
