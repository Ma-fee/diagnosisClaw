# BUG-003: Repeated `new_task` calls reuse worker session and conversation history implicitly

## 基本信息

- **发现时间**: 2026-04-06
- **严重程度**: 中到高
- **影响范围**:
  - 任何通过 `new_task` / `subagent` / task-style delegation 反复调用同一 worker 的场景
  - 典型关注配置: `packages/xeno-agent/config/diag-agent-v5.yaml`, `packages/xeno-agent/config/diag-agent-v2.yaml`, `packages/xeno-agent/config/diag-agent-v3.yaml`, `packages/xeno-agent/config/agentpool.yaml`

## 现象

当父代理多次调用同一个 worker agent，例如：

1. `technical_assistant` 第一次调用 `new_task(mode="fault_expert", ...)`
2. `fault_expert` 输出结论或请求补充信息
3. 用户回答后，`technical_assistant` 再次调用 `new_task(mode="fault_expert", ...)`

第二次运行默认不是一个“全新的 worker 会话”，而是继续使用同一个 `fault_expert` 实例，并沿用该实例内部已有的 `session_id` 和 `conversation` 历史。

这意味着：

- worker 会记住前一次隐式上下文；
- 修复逻辑如果依赖“重新调用 = 全新子会话”，会产生偏差；
- 多轮委派时可能出现历史污染；
- 如果 session 边界不清晰，未来可能存在跨诊断串味风险。

## 根本原因

### 1. `new_task` 没有把 child session id 传给实际执行流

`new_task` 会为事件层生成一个 `child_session_id`：

```python
child_session_id = str(uuid4())
```

但这个 ID 只用于 `SpawnSessionStart` / `SubAgentEvent` 的可观测性和导航，并没有作为 `run_stream()` 的真实 `session_id` 传给 worker：

```python
stream = node.run_stream(formatted_prompt, deps=new_deps)
```

相关代码:
- `packages/xeno-agent/src/xeno_agent/agentpool/resource_providers/delegation_provider.py`

### 2. `BaseAgent.run_stream()` 会复用现有 `self.session_id`

`BaseAgent.run_stream()` 的语义是：

- 若 `self.session_id is None`，初始化一个新的 session；
- 若已有 `self.session_id`，默认继续沿用；
- 除非显式传入新的 `session_id` 并覆盖它。

相关代码:
- `packages/agentpool/src/agentpool/agents/base_agent.py`

### 3. 默认 `store_history=True`

流结束后，用户消息和最终回复会写回 agent 自己的 `conversation`：

```python
if store_history:
    await self.log_message(final_message)
    conversation.add_chat_messages([user_msg, final_message])
```

因此同一个 worker agent 的历史会在多次调用之间自然累积。

相关代码:
- `packages/agentpool/src/agentpool/agents/base_agent.py`

## 影响配置分析

### `diag-agent-v5.yaml`

风险最高。
该配置明确打算让 `technical_assistant` 多次委派 `fault_expert` 进行故障诊断补充与恢复，如果实现 parent-mediated follow-up 但未定义 worker session 语义，就会默认落到“隐式记忆复用”。

### `diag-agent-v2.yaml` / `diag-agent-v3.yaml`

当前配置只暴露了 `technical_assistant` 和 `material_assistant`，交互边界问题较轻，但只要同一 worker 被多次委派，仍然会出现相同的记忆复用行为。

### `agentpool.yaml`

无论是 `fault_expert` 还是 `equipment_expert`，只要通过 `subagent` / worker 式调用反复运行，也会沿用相同的底层 agent 实例历史。

## 风险

1. **隐式状态污染**
   实现者可能以为“再次委派 = 新会话”，但实际不是。

2. **调试困难**
   某些诊断结论来源于先前隐式历史，而不是当前 prompt 中可见上下文。

3. **规格歧义**
   如果设计文档没有明确 worker session 语义，不同实现者会得出不同结论。

4. **跨任务串味**
   在边界不严格的情况下，长期运行的 worker 可能把不相关任务历史混入后续推理。

## 临时规避方案

1. 不把正确性建立在 worker 的隐式内部记忆上。
2. 每次重新委派时，在 prompt 中显式注入：
   - 原始问题
   - 上轮结论
   - 用户新补充的信息
   - 下一步恢复上下文
3. 将“显式上下文足以恢复流程”作为主设计原则。

## 推荐修复方向

二选一，并在规格中写死：

### 方案 A: 明确保留 worker 内部记忆

- 规定同一父会话中多次 `new_task(mode="fault_expert")` 视为同一诊断 worker 的连续回合。
- 测试和提示词都按“可连续上下文”来设计。

### 方案 B: 明确每次 worker 重调都视为新会话

- 在 delegation 层显式传新的 `session_id` 给 worker；
- 或者通过 `store_history=False` / 隔离消息历史的方式避免隐式记忆积累；
- 同时要求 parent 每次把恢复所需上下文完整写入 prompt。

推荐优先考虑方案 B，因为它更可控、更易测试，也更符合 parent-mediated follow-up 的显式编排思想。

## 对设计文档的要求

相关设计和实现文档必须补充一节：

- **Worker Session Semantics**

需要明确回答：

1. 多次 `new_task(mode="fault_expert")` 是否应该复用同一 worker 会话？
2. 是否允许依赖 worker 的隐式历史作为恢复依据？
3. parent 在 resume 时必须传入哪些最小恢复上下文？

## 验收标准

- 实现文档中明确规定 worker session 语义。
- 测试覆盖“第一次委派 -> 用户补充 -> 第二次委派”的链路。
- 系统行为不再依赖未声明的隐式 worker 历史。
