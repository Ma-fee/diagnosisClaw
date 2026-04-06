# 0004 Tools协议设计与HITL：你如何把“对话”变成“可执行交互”

## 工具层总体思路
你的工具不是“函数集合”，而是带行为约束的协议层：
1. `question_for_user`：多字段结构化问卷（XML -> JSON Schema -> MCP Elicit）。
2. `ask_followup_question`：单问题轻交互（suggest 选项 + 属性）。
3. `new_task` / `attempt_completion`：委派与收敛。
4. `update_todo_list`：增量计划状态管理。

## 关键设计细节
### 1) `question_for_user` 的结构化采集
- 输入 XML 问卷，可包含 enum/multi/input 三类问题。
- 内部转换成 ACP schema 调用 `handle_elicitation`。
- 返回 `ToolResult`，把答案放到 `metadata.answers`。

### 2) `ask_followup_question` 的轻量交互
- 通过 `<suggest ...>` 解析结构化选项。
- 支持 `type=input|fill` 与 `next_action`。
- 可把选项属性回传，支持后续自动动作。

### 3) 委派与完成的分离
- `new_task` 负责派工和上下文注入。
- `attempt_completion` 负责明确“任务完成信号”，便于系统收敛与事件捕获。

### 4) todo 增量更新而非全量覆盖
- `update_todo_list` 约定“只传新增或状态变化项”。
- 支持 `pos`（如 `1.1`）插入子任务和排序。

## 面试官问题
### Q1：为什么要两个提问工具？
建议回答：
- `question_for_user` 适合多字段表单场景，信息密度高。
- `ask_followup_question` 适合原子问题，交互更快。
- 双工具覆盖“重表单”和“轻追问”，避免一个工具过度泛化。

### Q2：为什么采用 XML 作为问卷 DSL？
建议回答：
- 对 LLM 生成友好，层次清晰。
- 与 suggest 标签天然匹配 UI 选项语义。
- 成本是解析复杂度上升，所以代码层做了统一解析和错误兜底。

### Q3：HITL 在你系统中如何落地？
建议回答：
- 不是口号，而是工具级硬约束：需要用户输入就必须走提问工具。
- 诊断 phase gate 必须用户确认后推进，避免模型自行跨阶段。

## Trade-off
1. 结构化工具提高可靠性，但降低“自由对话感”。
2. 强约束提升可审计性，但 prompt 与 schema 维护成本增加。

## 简历表述
- 设计并实现面向 HITL 的工具协议层（问卷采集/追问/委派/计划管理），将自然语言交互转化为结构化可执行流程，显著提升诊断流程的可控性与可追踪性。