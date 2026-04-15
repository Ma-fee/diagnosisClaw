# 0002 Prompt分层与角色约束：为什么你的模型行为可控

## 核心设计
你的 prompt 不是一段大 system prompt，而是“能力层 + 角色层”两级组合。

1. 能力层（capabilities）：如 citation、search、markdown、layout、image、mermaid。
2. 角色层（roles）：technical_assistant、fault_expert、equipment_expert、material_assistant。
3. 在 agent 配置中按需叠加，形成每个角色的最小能力集。

## 设计收益
1. 复用：引用规范、检索规范可跨角色复用。
2. 可演进：只改 capability 模板即可影响多个角色。
3. 降耦：角色 prompt 关注“职责”，能力 prompt 关注“输出约束”。

## 典型细节
### 1) technical_assistant 的强约束交互
- 明确写了“需要用户输入时，必须调用 question tool，禁止直接发问等待”。
- 提供了 self-check 清单，减少模型漏调工具。

### 2) fault_expert 的诊断流程约束
- 先澄清信息，再产出诊断规划，再进入多轮执行与报告收敛。
- 强调交互式确认、置信度驱动与流程动态调整。

### 3) material_assistant 的证据导向
- 引用规范要求很细，强调可追溯来源、可点击引用、不可伪造。
- 搜索策略要求先规划后检索再迭代 refinement。

## 面试官高频问题
### Q1：你怎么防止 prompt 互相打架？
建议回答：
- 先按“能力 -> 角色”顺序注入，能力是底层规范，角色是任务约束。
- 角色只补充职责，不重复改写通用规范。
- 通过工具 schema 做第二层兜底，避免只靠 prompt 软约束。

### Q2：为什么要把 citation 单独做 capability？
建议回答：
- 因为它是横切关注点，不只研究 agent 需要，故障报告和参数解释都需要。
- 单独抽离后，审计和升级成本最低。

### Q3：如果要支持中英双语，你怎么做？
建议回答：
- 角色 prompt 使用变量 `LANG` 注入。
- 语言策略在角色层控制，能力层保持与语言无关的结构约束。

## Trade-off
1. Prompt越细粒度，治理越强，但配置复杂度会上升。
2. 纯 prompt 约束实现快，但鲁棒性不如“prompt + schema + provider 代码”三层。

## 简历表述
- 设计能力层/角色层双层 Prompt 架构，将引用、检索、版式、图示等横切能力模块化复用，并通过角色职责约束实现多Agent行为治理，显著降低提示词耦合与回归风险。