# 0002 AgentPool 工具集成机制清单

## 1. 目的

本文只回答一个问题：AgentPool 在“工具集成”层面有哪些机制。

暂不展开实现细节、配置细节和优缺点对比，后续再拆分专题。

## 2. 工具集成机制总清单

从 configuration/toolsets 与代码实现视角看，工具集成机制可归纳为以下 12 类：

1. 内置工具集机制
2. 文件系统工具集成机制（file_access）
3. 资源虚拟文件系统机制（vfs）
4. 执行与进程工具机制（execution）
5. 代码能力工具机制（code）
6. 技能装配机制（skills）
7. 子代理委托机制（subagent）
8. 工作者代理机制（workers）
9. 外部 API 规范驱动机制（openapi）
10. 外部平台聚合机制（composio）
11. Python 入口点动态发现机制（entry-points）
12. 自定义工具集导入机制（custom/import-tools）

## 3. 机制分组视图（便于后续拆分）

### A. 本地能力型

- file_access
- vfs
- execution
- code

### B. 协作编排型

- skills
- subagent
- workers

### C. 外部生态接入型

- openapi
- composio
- entry-points
- custom/import-tools

### D. 交互形态增强型

- code-mode
- remote-code-mode

说明：code-mode 与 remote-code-mode 更偏“工具交互与调用形态包装”，可作为独立专题分析。

## 4. 每类机制的最小定义（用于后续目录拆分）

1. 内置工具集机制
- 平台直接提供的标准工具能力集合，开箱即用。

2. 文件系统工具集成机制
- 基于统一文件访问抽象，将读写检索编辑等能力暴露为工具。

3. 资源虚拟文件系统机制
- 将资源层抽象为可浏览/可读取的统一视图，降低资源访问耦合。

4. 执行与进程工具机制
- 提供命令执行、后台进程管理和输出采集能力。

5. 代码能力工具机制
- 提供格式化、结构化搜索、诊断等面向代码的工具。

6. 技能装配机制
- 通过技能库加载“方法模板”并在运行时组合调用。

7. 子代理委托机制
- 通过任务下发实现“当前 agent 调用其他 agent/team”。

8. 工作者代理机制
- 将特定 worker 暴露为稳定工具接口，便于分工协作。

9. OpenAPI 规范驱动机制
- 从 API 规范自动生成工具，降低手写适配成本。

10. 外部平台聚合机制
- 通过第三方平台统一接入多类 SaaS/服务工具。

11. 入口点动态发现机制
- 通过 Python entry point 发现并加载扩展工具。

12. 自定义导入机制
- 通过 import_path 将本地函数/类快速包装为工具。

## 5. 建议的后续拆分顺序

1. 0003 file_access 与 vfs
2. 0004 execution 与 code
3. 0005 skills、subagent、workers
4. 0006 openapi 与 composio
5. 0007 entry-points、custom、import-tools
6. 0008 code-mode 与 remote-code-mode

## 6. 备注

- 本文是清单文档，后续每篇专题统一采用：机制定义、配置最小样例、运行时行为、边界与风险、当前项目可落地点。
