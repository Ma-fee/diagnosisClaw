# Agent Orchestration Discussion Notes

## 日期

- 2026-04-06

## 背景

当前诊断链路的目标形态是：

- `technical_assistant` 作为唯一对外入口
- `fault_expert` 作为内部诊断 worker
- OpenCode / ACP / AgentPool 作为承载前端会话与编排执行的基础设施

讨论围绕以下问题展开：

- 子代理被委派后，如何继续向用户追问
- 前端是否需要切换当前对话身份
- 如果不切换身份，如何由父代理代问
- ACP 服务化后有哪些调用方式
- 不同产品如何处理类似问题
- worker 的 session / memory 是否会被复用

## 已确认结论

### 1. OpenCode 当前更适合单一 user-facing agent

在现有 OpenCode server 模型下，前端通常只稳定绑定一个当前主 agent。

- 用户自然对话的对象是当前主 agent
- 被 `new_task` / `subagent` 委派的 worker 更像内部任务流
- worker 输出会以子任务事件形式回到父流，而不是变成新的当前聊天身份

因此，`technical_assistant -> fault_expert` 之后，如果 `fault_expert` 直接调用 `ask_followup_question`，语义会错位：

- UI 上能出现 pending question
- 但用户的当前对话主体仍然是 `technical_assistant`
- 系统会表现成“worker 在直接问用户”，而前端其实没有真正切换到 worker 会话

### 2. 推荐采用 parent-mediated follow-up

当前阶段更推荐保留：

- `technical_assistant` 为唯一 user-facing agent
- `fault_expert` 为内部 worker

worker 不直接问用户，而是返回结构化的 `needs_user_input`，由父代理统一代问。

推荐流程：

1. 用户消息进入 `technical_assistant`
2. `technical_assistant` 调用 `new_task(mode="fault_expert", ...)`
3. `fault_expert` 若信息不足，不直接 `ask_followup_question`
4. `fault_expert` 返回 `needs_user_input`
5. `technical_assistant` 调用 `ask_followup_question`
6. 用户回答后，`technical_assistant` 再次调用 `new_task(mode="fault_expert", ...)`

这条路线的优点：

- 前端零改动
- 会话所有权清晰
- 行为可控
- 最符合当前 OpenCode / AgentPool 边界

### 3. 不建议让 worker 直接持有用户追问工具

对 `fault_expert` 这类内部 worker，`ask_followup_question` 不应继续暴露。

更合理的约束是：

- 只有 parent / user-facing agent 可以直接调用用户交互工具
- worker 只能通过专门的工具或结构化返回值请求补充信息

为此，已形成的设计方向是：

- 新增 worker-only 工具 `need_more_info`
- `new_task` 返回 JSON envelope
- envelope 至少支持两种状态：
  - `completed`
  - `needs_user_input`

详细设计见：

- `docs/superpowers/specs/2026-04-06-parent-mediated-followup-design.md`

### 4. 重复 `new_task(mode="fault_expert")` 通常会复用 worker 历史

当前实现下，多次重新委派同一 worker，并不天然等于“全新子会话”。

更接近的真实行为是：

- `new_task` 为事件层生成了 child session id
- 但实际执行 `node.run_stream(...)` 时没有把它作为真实 worker session 强制隔离
- 底层 agent 如果已有 `session_id` / `conversation`，通常会继续沿用

因此：

- 重新调用 `new_task(mode="fault_expert", ...)`，大概率还是原来的 worker 上下文
- 这意味着 worker memory / history 默认会被隐式复用
- 如果规格不写清楚，后续实现容易误以为“再次调用 = 新 worker 会话”

这个问题已记录为：

- `packages/bug-records/003-worker-session-memory-reuse.md`

### 5. `diag-agent-v5.yaml` 是当前风险最高的配置

`packages/xeno-agent/config/diag-agent-v5.yaml` 当前具备以下组合：

- `technical_assistant` 是默认入口
- `technical_assistant` 持有 `ask_followup_question` 和 `new_task`
- `fault_expert` 也持有 `ask_followup_question` 和 `new_task`

这会同时触发两类问题：

- worker 直接问用户的边界问题
- 多轮委派时 worker 历史隐式复用的问题

相关 bug 记录：

- `packages/bug-records/002-subagent-user-elicitation-boundary.md`
- `packages/bug-records/003-worker-session-memory-reuse.md`

### 6. `diag-agent-v2.yaml` / `diag-agent-v3.yaml` / `agentpool.yaml` 也可能遇到类似问题

结论分层如下：

- `diag-agent-v2.yaml` / `diag-agent-v3.yaml`
  - 当前直接暴露给 worker 的用户追问工具风险较低
  - 但如果未来把用户追问工具暴露给被委派 worker，仍会复现同类问题
  - 同时，worker session/history 复用问题原则上仍存在

- `agentpool.yaml`
  - 只要 `fault_expert` 之类的内部 agent 能直接对用户提问，就会遇到同类边界问题
  - 即使配置写成 `type: subagent`，也不等于真正切换前端当前身份

## ACP 服务化相关结论

### 1. 可以把某个 agent 暴露成 ACP 服务

当前仓库已支持：

```bash
uv run agentpool serve-acp <config.yml> --agent <agent_name>
```

例如：

```bash
uv run agentpool serve-acp packages/xeno-agent/config/diag-agent-v5.yaml --agent technical_assistant
```

或者直接暴露 `fault_expert`：

```bash
uv run agentpool serve-acp packages/xeno-agent/config/diag-agent-v5.yaml --agent fault_expert
```

也支持 websocket 方式启动：

```bash
uv run agentpool serve-acp packages/xeno-agent/config/diag-agent-v5.yaml \
  --agent technical_assistant \
  --transport websocket \
  --ws-host 0.0.0.0 \
  --ws-port 8765
```

### 2. ACP 的主要调用方式有三类

#### 方式 A: 由支持 ACP 的 IDE / 客户端直接调用

例如 Zed 之类的 ACP client，把 `agentpool serve-acp ...` 配成 agent server。

#### 方式 B: 在 Python 中通过 `ACPAgent.from_config(...)` 调用

即：

- 代码启动一个 ACP 子进程
- 当前进程作为 ACP client 连过去
- 通过 `run()` / `run_stream()` 访问这个 agent

#### 方式 C: 把它注册成另一套 AgentPool 里的 `type: acp` 外部 agent

这样别的 orchestrator 可以把它当作一个外部 ACP agent 来委派。

### 3. ACP 解决的是协议接入，不自动解决 parent / worker 交互边界

即使把 `fault_expert` 做成 ACP 服务，也不代表：

- worker 就自动拥有用户对话权
- 当前前端会话就会自动切换到 worker
- worker 直接追问用户的问题就自然闭环

ACP 主要解决的是：

- agent 如何被调用
- agent 如何通过标准协议暴露给客户端或其他编排层

它不自动解决：

- 谁拥有当前用户会话
- worker 如何向 parent 申请补充信息
- 重新委派时 session / memory 是否隔离

## 与其他产品的对照理解

### 1. OpenCode 更接近“可切子会话”

基于已查到的资料，OpenCode 区分 `primary agents` 和 `subagents`，并支持 child sessions。
它更接近“前端承认子任务是可进入、可返回的真实子会话”。

这条路线可以解决“想直接回复 subagent”的问题，但前提是：

- UI 支持当前 active session 切换
- server 支持 child session 导航
- 子会话结束后能再返回父会话

### 2. Cline 更接近“父代理代问”

基于已查到的资料，Cline 的 subagents 更像独立上下文的研究 worker，最后把结果回给主会话。
这类设计里，真正向用户澄清的仍然是当前主对话主体，而不是 subagent 直接占用聊天框。

### 3. Claude Code / Kilo Code / Codex 的公开资料更接近“主入口 + 内部子任务”

基于目前查到的公开材料，较稳妥的判断是：

- 它们都支持某种形式的 subagent / multi-agent / orchestration
- 但没有足够公开证据表明“worker 可以直接无缝接管当前用户聊天身份”

因此更接近的工程理解是：

- 主 agent 对外
- 子 agent 对内
- 需要用户输入时，由主链路负责与用户交互

其中：

- `Codex` 这部分目前公开资料不足，关于“subagent 是否可直接问用户”未形成确定结论
- 对 `Claude Code` / `Kilo Code` 的判断也应视为当前公开资料下的保守归纳，而非其全部内部实现细节

## 当前工程建议

在现有 `agentpool + opencode server + diag-agent-v5` 架构下，优先顺序建议如下：

1. 先落地 parent-mediated follow-up
2. 从 worker 侧移除直接用户追问能力
3. 明确 worker session semantics
4. 不把正确性建立在 worker 隐式 memory 之上
5. 如未来确实需要“直接回复 subagent”，再评估做真实子会话切换

## 明天继续讨论时建议优先展开的主题

1. 是否明确把 worker session 语义定为“每次重调都新会话”
2. `need_more_info` 的字段最终定版
3. `new_task` 返回 envelope 的兼容策略
4. `technical_assistant` 如何解析 `needs_user_input`
5. 是否需要为 ACP 场景额外设计 agent handoff / child session 模式

## 关联文档

- `docs/superpowers/specs/2026-04-06-parent-mediated-followup-design.md`
- `packages/bug-records/002-subagent-user-elicitation-boundary.md`
- `packages/bug-records/003-worker-session-memory-reuse.md`
