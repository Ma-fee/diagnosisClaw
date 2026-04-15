# BUG-002: Delegated subagent can emit user questions that the OpenCode frontend cannot naturally route

## 基本信息

- **发现时间**: 2026-04-06
- **严重程度**: 高
- **影响范围**:
  - OpenCode / opencode server 场景
  - 任何“主代理对外 + 子代理内部委派”的配置
  - 典型受影响配置: `packages/xeno-agent/config/diag-agent-v5.yaml`, `packages/xeno-agent/config/agentpool.yaml`

## 现象

在 OpenCode 前端中，用户通常只能和当前主代理对话。

当主代理通过 `new_task` 或 `subagent` 机制委派 `fault_expert` 等子代理后，如果子代理调用了 `ask_followup_question`，服务端会正常创建 pending question 并向前端广播问题事件，但交互语义是错位的：

- 前端的可见会话仍然属于主代理；
- 子代理不是一个真正的当前对话主体；
- 用户虽然能看到问题，但无法以“正在和子代理对话”的方式自然继续会话；
- 系统边界变成“worker 直接向用户提问”，而不是“parent 统一拥有用户交互权”。

## 复现路径

1. 使用 `technical_assistant` 作为主入口。
2. `technical_assistant` 通过 `new_task(mode="fault_expert", ...)` 委派诊断。
3. `fault_expert` 调用 `ask_followup_question` 请求更多信息。
4. OpenCode 前端显示问题，但用户的当前会话主体仍然是 `technical_assistant`。
5. 系统表现为“子代理在问用户，但前端只允许和主代理对话”。

## 根本原因

### 1. 子代理执行流只是父流中的包装事件

`new_task` 在执行目标 agent 时，使用的是：

```python
stream = node.run_stream(formatted_prompt, deps=new_deps)
```

同时将子代理输出包装为 `SubAgentEvent` 发回父流，而不是切换当前会话主体。

相关代码:
- `packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`

### 2. OpenCode 服务只有一个当前 user-facing agent

OpenCode server 在运行时绑定的是单个 `state.agent`，会话创建、消息处理、输入 provider 都围绕这个 agent 组织。
即使 `/agent` 路由能列出多个 agent，也只是把当前 agent 标为 `primary`，其他标为 `subagent`，并没有真正的会话级 agent 切换机制。

相关代码:
- `packages/agentpool/src/agentpool_server/opencode_server/routes/agent_routes.py`
- `packages/agentpool/src/agentpool_server/opencode_server/routes/session_routes.py`
- `packages/agentpool/src/agentpool_server/opencode_server/state.py`

### 3. `ask_followup_question` 是直接面向 UI 的 elicitation 工具

`ask_followup_question` 最终调用 `ctx.handle_elicitation(...)`，直接走当前 `InputProvider` 的用户交互链路。
它天然假设调用方就是当前 user-facing agent。

相关代码:
- `packages/xeno-agent/src/xeno_agent/tools/ask_followup_question.py`
- `packages/agentpool/src/agentpool/ui/base.py`
- `packages/agentpool/src/agentpool_server/opencode_server/input_provider.py`

## 影响配置分析

### 明确受影响

#### `diag-agent-v5.yaml`

- `technical_assistant` 是默认入口
- `fault_expert` 通过 `new_task` 被内部委派
- `fault_expert` 同时持有 `ask_followup_question`

这会直接触发“worker 直接问用户”的边界问题。

#### `agentpool.yaml`

- `qa_assistant` 使用 `type: subagent` 调起 `fault_expert`
- `fault_expert` 仍持有 `ask_followup_question`

虽然配置术语不同，但本质仍然是子代理/子任务流，不是 OpenCode 当前会话身份切换，因此也会遇到同类问题。

### 风险较低但原则上仍需注意

#### `diag-agent-v2.yaml` / `diag-agent-v3.yaml`

这两份配置中当前只有 `technical_assistant` 持有 `question_for_user`，未看到被委派 worker 直接持有用户提问工具，因此不容易触发这个 bug。

但只要未来把 `ask_followup_question` 或 `question_for_user` 暴露给内部 worker，问题会再次出现。

## 临时规避方案

1. 只允许主代理持有用户提问工具。
2. 禁止被委派 worker 直接使用 `ask_followup_question`。
3. 由 worker 返回结构化阻塞结果给 parent，再由 parent 统一向用户提问。

## 推荐修复方向

采用 parent-mediated follow-up 模式：

1. 子代理不直接问用户。
2. 子代理通过 worker-only 工具或结构化返回值声明 `needs_user_input`。
3. 主代理收到后调用 `ask_followup_question` 或 `question_for_user`。
4. 用户回答后，主代理重新委派子代理继续诊断。

对应设计文档:
- `docs/superpowers/specs/2026-04-06-parent-mediated-followup-design.md`

## 验收标准

- 在 OpenCode 前端中，所有 pending question 都由当前主代理发起。
- 子代理不再直接触发 UI 侧用户提问。
- 用户无需理解或接触内部 worker 身份即可完成诊断补充信息输入。
