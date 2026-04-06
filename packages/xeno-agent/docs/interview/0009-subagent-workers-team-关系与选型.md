# 0009 subagent、workers、team 关系与选型

## 背景
本次讨论聚焦三个概念在多智能体系统中的职责边界：`subagent`、`workers`、`team`，以及在诊断场景中的协同模式。

## 一句话定义
- `team`：执行单元（可由多个 agent 组成的协作节点）。
- `workers`：暴露方式（把某些节点挂成主 agent 的可调用工具）。
- `subagent`：通用委派机制（运行时把任务动态分发给 agent 或 team）。

## 关键结论

### 1. workers 是“固定快捷拨号”
- 通常会生成类似 `ask_xxx` 的工具。
- 适合目标明确、调用路径稳定的场景。
- 主 agent 自己负责多次调用与结果收敛。

### 2. subagent 是“通用调度台”
- 可在运行时选择目标节点（单 agent 或 team）。
- 支持同步/流式，也可异步后台任务。
- 适合复杂任务编排和动态路由。

### 3. team 是“被调度对象”而不是工具机制
- team 本身可以承接任务并内部协作。
- 可以被 subagent 调用，也可以被 workers 暴露为一个快捷入口。

## “workers 只有一个 agent”时与 subagent 的区别
- 能力上会有重叠：都可以把任务交给一个专家 agent。
- 仍有本质差异：
  - workers：预绑定、固定入口、偏快捷调用。
  - subagent：通用入口、目标可变、编排能力更强。

## 诊断场景示例（液压系统故障）

### 路径 A：主 agent -> subagent -> diagnosis_team
1. 主 agent 下发整包任务给 team。
2. team 内部自动分工（查手册 + 看图判位 + 汇总）。
3. team 返回综合报告给主 agent。
4. 主 agent 对外解释并确认下一步。

特点：主 agent 负担更小，适合复杂问题；链路较长。

### 路径 B：主 agent -> workers（多个快捷工具）
1. 主 agent 先调用 `ask_material_assistant` 拿标准值。
2. 再调用 `ask_equipment_expert` 拿现场检查顺序。
3. 主 agent 自行消解冲突并形成结论。

特点：过程可控、可解释性强；主 agent 认知负担更高。

## 实践建议
- 简单高频问题：优先 workers。
- 复杂多约束问题：优先 subagent + team。
- 生产常见策略：并存。
  - 先 workers 快速探测证据。
  - 证据冲突或链路复杂时升级到 team。
  - 最终统一由主 agent 输出结论和行动建议。

## 访谈可复述要点
- “team 是执行单元，workers 是入口形态，subagent 是调度机制。”
- “一个 worker 像固定直拨，subagent 像总机调度。”
- “复杂任务交 team 省主 agent 心智，精细控制走 workers。”
