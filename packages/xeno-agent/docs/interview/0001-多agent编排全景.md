# 0001 多Agent编排全景：你这套系统到底怎么跑起来

## 一句话项目定位
xeno-agent 是一个面向设备故障诊断场景的多智能体编排系统：用 `technical_assistant` 做入口路由，用 `fault_expert` 做诊断总控，用 `equipment_expert` 做实操指导，用 `material_assistant` 做深度资料检索与结构化输出。

## 架构骨架（可直接口述）
1. `technical_assistant` 作为默认入口，负责意图识别与升级路由。
2. 故障类问题升级到 `fault_expert`，由它主导假设生成、诊断计划与多轮执行。
3. `fault_expert` 在需要时委派给 `equipment_expert`（现场操作指导）或 `material_assistant`（资料研究）。
4. 全过程通过计划工具维护 todo 状态，通过可观测事件输出子会话链路。

## 关键配置证据
- 默认入口：`default_agent: technical_assistant`（diag-agent-v5）
- 四个核心 agent：technical/fault/equipment/material（diag-agent-v5）
- 启用 observability，协议为 OTLP HTTP protobuf（diag-agent-v5）

## 机制细节
### 1) 入口路由 + 能力分工
- `technical_assistant` 说明里明确“先处理常规技术问答，检测到故障再升级系统化诊断”。
- `fault_expert` 说明里强调“主诊断者 + 协调其他专家”。
- `equipment_expert` 说明里区分 worker 模式与 active 模式。
- `material_assistant` 说明里强调“研究型任务、结构化输出、避免纯报告空转”。

### 2) 委派深度控制
- 代码定义 `MAX_DELEGATION_DEPTH = 5`，防止无限递归委派。
- 超限直接报错，属于系统稳定性护栏。

### 3) 动态模式暴露
- `new_task` 的 `prepare_new_task` 会动态把可用 mode 追加到 tool 描述里。
- 这意味着 agent 不需要硬编码“能委派给谁”，由运行时 pool 反射当前可用节点。

### 4) 子会话可追踪
- 每次委派生成 `child_session_id`，并发射 `SpawnSessionStart`。
- 子事件通过 `SubAgentEvent` 包装回传，保留父子链路。

## 面试官会问什么
### Q1：你为什么不是单Agent，而是四个Agent？
建议回答：
- 单Agent在“信息采集、计划生成、实操指导、报告归档”四种认知模式间频繁切换，容易上下文污染。
- 多Agent把角色边界前移到配置层，可测试性更高、可替换性更好。
- 配合委派深度限制与事件链路，复杂度可控。

### Q2：多Agent是不是增加了通信开销？
建议回答：
- 是的，延迟会增加，但通过“仅在复杂任务委派”的策略控制触发频率。
- 对高风险故障场景，更看重可解释性、分工清晰和可追踪，而不是最低时延。

### Q3：如果我要你继续扩展到 8 个 agent，你怎么避免失控？
建议回答：
1. 明确每个 agent 的输入输出契约。
2. 给每类委派定义触发条件和禁止条件。
3. 强制 `expected_output`，减少子任务自由发挥。
4. 通过 observability 看委派链深度、失败率、回退率。

## Trade-off（你可以主动讲）
1. 可维护性 vs 运行时成本：分工清晰提升维护性，但会带来编排开销。
2. 灵活性 vs 可预测性：动态模式发现提高灵活性，但要靠 schema + 深度限制约束行为。
3. 自动化 vs 人在回路：诊断效率略降，但安全性与正确性显著提升。

## 简历表述（可直接贴）
- 设计并实现面向设备故障诊断的多Agent编排系统（入口路由 + 专家协作 + 可观测链路），构建 technical/fault/equipment/material 四类角色分工，支持有界委派（max depth=5）与子会话追踪，提升复杂诊断任务的可解释性与稳定性。