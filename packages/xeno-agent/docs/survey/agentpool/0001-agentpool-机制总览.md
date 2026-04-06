# 0001 AgentPool 机制总览（调研起始）

## 1. 目的

本文作为 AgentPool 机制调研的起始文档，先建立“全景地图”，后续按编号逐篇深入。

- 本文定位：总览
- 后续定位：专题深挖（每篇一个机制域）

## 2. 调研范围

基于 configuration 文档体系进行机制梳理，覆盖：

- 配置与继承
- 节点与编排
- 工具与外部集成
- 消息流与控制
- 状态、存储与可观测

## 3. 机制地图（一级）

AgentPool 现有机制可归纳为以下 14 类：

1. 配置分层合并机制（多来源加载与覆盖）
2. 文件继承机制（INHERIT）
3. 节点机制（Native/ACP/AG-UI/Claude/Codex/Team）
4. 工具集机制（Toolsets）
5. 连接与消息路由机制（Connections）
6. 条件控制机制（filter/stop/exit）
7. 生命周期钩子机制（Hooks）
8. 事件驱动机制（Event Sources + Handlers）
9. 会话与历史处理机制（Session）
10. 知识与资源双通道机制（Knowledge vs Resources）
11. 结构化输出机制（Responses）
12. 模型与执行环境机制（Model + Execution Environment）
13. MCP 集成机制（MCP Servers）
14. 存储与可观测机制（Storage + Observability）

## 4. 逐一调研建议拆分（拟定）

建议按以下顺序继续，保证从“基础配置”到“运行控制”再到“运维治理”：

1. 0002 配置分层与继承（index + inheritance）
2. 0003 节点体系与团队编排（node-types）
3. 0004 工具集与能力装配（toolsets）
4. 0005 连接、条件与消息流控制（connections + conditions）
5. 0006 事件、钩子与自动化触发（event-sources + events + hooks）
6. 0007 会话、知识、资源与上下文策略（session + knowledge + resources）
7. 0008 结构化输出、模型、执行环境（responses + model + execution-environments）
8. 0009 MCP、存储、可观测与生产治理（mcp + storage + observability）

## 5. 当前项目配置映射（快速观察）

在当前配置中，已明显启用：

- 多 Agent 机制
- 文件型 system_prompt 机制
- file_access + skills + custom provider 工具机制
- 自定义 observability 上报机制

说明：该部分仅作快速定位，详细映射将在专题文档中逐项展开。

## 6. 输出规范（后续文档）

后续每篇建议统一结构：

1. 机制定义
2. 核心组件
3. 配置字段与最小示例
4. 运行时行为
5. 常见风险与边界
6. 在当前项目中的落点
7. 可执行改进建议

---

维护说明：

- 本文为调研基线，后续若机制分类变化，以本文为准同步修订。
- 每篇专题完成后，应在本文补充“完成状态”和链接。
