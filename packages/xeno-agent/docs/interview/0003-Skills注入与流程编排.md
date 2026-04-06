# 0003 Skills注入与流程编排：不是“会调工具”，而是“会调方法论”

## 你的技能机制
你做的不是把 skill 当静态文档，而是把它变成“运行时注入的任务操作系统”。

## 关键实现点
1. `new_task_with_skills.yaml` 增加 `load_skills` 参数，且要求显式传空数组 `[]`。
2. `XenoDelegationProvider.new_task` 在委派时把 skill 指令拼到子任务 prompt 前部。
3. `_format_skills_instructions` 会把 skill 内容包装成 `<skill-instruction ...>` 块注入。
4. skill 不存在时直接抛 `ToolError`，避免 silent failure。

## 典型工作流（故障诊断）
1. 入口识别故障后，加载 `systematic-troubleshooting`。
2. 诊断规划阶段可委派并注入 `diagnosis-planning`。
3. 现场执行阶段，按用户需求注入 `equipment-operation-assistant`。
4. 收尾阶段用 `case-document` 或 `fault-case-report` 输出归档。

## 为什么这是亮点
- 传统多Agent常见问题是“子agent拿到任务但拿不到方法论”。
- 你通过 `load_skills` 让方法论随任务下发，实现“能力上下文可移植”。

## 面试官问题
### Q1：为什么不把所有技能都默认加载？
建议回答：
- 全量加载会导致上下文膨胀、注意力稀释、指令冲突上升。
- 按任务注入可控且可观测，成本更低。

### Q2：skill 版本升级怎么避免影响线上稳定性？
建议回答：
- 技能作为独立文件可灰度更新。
- 配置中按 agent/场景选择是否注入，支持渐进替换。
- 关键流程由工具 schema 与 provider 兜底，不依赖单点 prompt。

### Q3：如果 skill 内容写错怎么办？
建议回答：
1. 子任务输出格式由 `expected_output` 收敛。
2. 关键动作仍需工具参数校验。
3. 通过事件链路回放定位“是技能误导还是数据不足”。

## Trade-off
1. 动态注入提高灵活性，但需要更强的版本管理。
2. 方法论下发提升一致性，但会增加提示 token 成本。

## 简历表述
- 实现基于 `load_skills` 的运行时技能注入机制，将故障排查方法论随子任务动态下发，形成“任务分解 + 方法约束 + 结果收敛”的闭环编排能力。