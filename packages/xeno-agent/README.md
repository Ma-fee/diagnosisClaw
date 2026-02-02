# Xeno-Agent

基于 AgentPool + Pydantic-AI 的一等公民 Agentic Framework，专为工业设备故障诊断场景设计的多智能体系统。提供丰富的工具集和 SaaS 版诊断智能体配置，支持配置文件驱动的快速迭代开发。

## 核心特性

- **多智能体协作**：支持故障专家、设备专家、材料助手等专业化智能体
- **配置文件驱动**：基于 YAML 的声明式配置，方便快速迭代和实验
- **协议桥接**：通过 ACP、OpenCode 等协议无缝集成多种开发工具和 IDE
- **MCP 集成**：原生支持 Model Context Protocol，可连接外部工具和服务
- **可观测性**：内置日志追踪和 Phoenix 可观测性集成
- **现代工具链**：使用 uv + pytest 管理，支持 Python 3.13+

## 快速开始

### 环境要求

- Python 3.13+
- uv（推荐的 Python 包管理器）
- direnv（推荐的环境变量管理工具）
- OpenCode（可选，用于 OpenCode 服务器模式）

### 安装

**重要说明**：本项目依赖 `packages/agentpool`，这是一个 Git submodule。由于 AgentPool 正在加速迭代，当前仓库使用的是衍生版本。在 clone 仓库后，必须初始化 submodule。

#### 初始化 Git Submodule

```bash
# 克隆仓库并初始化 submodule
git clone <repository-url>
cd iroot-llm
git submodule update --init --recursive
```

#### 方法一：直接在项目目录运行

```bash
# 确保 submodule 已初始化
git submodule update --init --recursive

# 进入 xeno-agent 目录
cd packages/xeno-agent

# 使用 uv 同步依赖
uv sync

# 配置环境变量（复制示例文件并根据实际情况修改）
cp .envrc.example .envrc
# 编辑 .envrc 文件，修改 API 密钥和模型配置
vi .envrc  # 或使用其他编辑器

# 如果使用 direnv，加载环境变量
direnv allow
```

#### 方法二：从项目根目录运行

```bash
# 确保 submodule 已初始化
git submodule update --init --recursive

# 配置环境变量（在根目录）
export UV_PYTHON='packages/xeno-agent'

# 配置 LLM API（复制示例文件并根据实际情况修改）
cp packages/xeno-agent/.envrc.example packages/xeno-agent/.envrc
# 编辑 packages/xeno-agent/.envrc 文件
vi packages/xeno-agent/.envrc

# 安装 direnv（macOS/Linux）
brew install direnv  # macOS
sudo apt install direnv  # Ubuntu/Debian
# 安装后需要配置 shell，请参考 direnv 官方文档

# 同步依赖
uv sync --package packages/xeno-agent
```

### 运行方式

Xeno-Agent 提供三种使用方式：命令行、ACP、OpenCode

**重要说明**：
- 所有命令都需要在 `packages/xeno-agent` 目录下运行，或者
- 在 `iroot-llm` 目录下配置环境变量 `export UV_PYTHON='packages/xeno-agent'`
- 确保环境变量已加载（如果使用 direnv，执行 `direnv allow` 后会自动加载）

#### 1. 命令行模式

直接通过命令行运行智能体：

```bash
# 在 packages/xeno-agent 目录下运行
cd packages/xeno-agent

# 基本用法
uv run agentpool run --config config/diag-agent.yaml fault_expert "测试下任务委派能力，例如『直接检索下Sy215c 挖掘机冒黑烟故障诊断相关资料』。这是一个功能测试任务"

# 使用其他智能体
uv run agentpool run --config config/diag-agent.yaml qa_assistant "什么是挖掘机的液压系统？"

# 设备专家分析
uv run agentpool run --config config/diag-agent.yaml equipment_expert "分析这张设备图片" --image /path/to/image.jpg
```

#### 2. ACP 模式（Agent Communication Protocol）

通过 ACP 协议暴露智能体，支持 Zed、Toad 等 IDE 集成：

```bash
# 在 packages/xeno-agent 目录下运行
cd packages/xeno-agent

# 启动 ACP 服务器（使用 diag-agent.yaml 配置）
uv run agentpool serve-acp config/diag-agent.yaml

# 或指定特定智能体
uv run agentpool serve-acp config/diag-agent.yaml --agent fault_expert
```

然后在支持 ACP 的 IDE 中配置连接到本地的 ACP 服务器。

#### 3. OpenCode 模式

启动 OpenCode 兼容的服务器：

```bash
# 在 packages/xeno-agent 目录下运行
cd packages/xeno-agent

# 启动 OpenCode 服务器（默认端口 7162，使用 diag-agent.yaml 配置）
uv run agentpool serve-opencode --config config/diag-agent.yaml --port 7162

# 在另一个终端连接
opencode attach http://127.0.0.1:7162
```

## 项目结构

```
xeno-agent/
├── config/                 # 配置文件目录
│   └── diag-agent.yaml     # 诊断智能体主配置文件
├── src/xeno_agent/        # 源代码
│   ├── agentpool/          # AgentPool 集成和资源提供者
│   ├── tools/              # 自定义工具实现
│   └── utils/              # 工具函数
├── tests/                 # 测试目录
│   ├── unit/              # 单元测试
│   └── integration/        # 集成测试
├── examples/               # 使用示例
├── docs/                  # 文档和 RFC
├── .envrc.example         # 环境变量配置示例
└── pyproject.toml         # 项目配置
```

## 智能体类型

### fault_expert（故障专家）

负责系统性故障分析和解决方案制定：

- **核心职责**：
  - 故障现象澄清与信息收集
  - 假设生成与诊断规划
  - 智能体协调与任务委派
  - 综合诊断报告生成

- **协作策略**：
  - 需要技术资料/手册？ → 委派给 `material_assistant`
  - 需要图纸/设备分析？ → 委派给 `equipment_expert`
  - 需要动手操作指导？ → 直接与 `equipment_expert` 交互

### equipment_expert（设备专家）

双重模式智能体（Worker + Active）：

- **Worker 模式**（作为工具被调用）：
  - 分析设备图像、面板、图纸
  - 提供作业标准书（SOP）内容
  - 执行技术文档分析
  - 返回结构化结果

- **Active 模式**（作为主智能体被调用）：
  - 指导用户完成拆卸流程
  - 提供交互式测试和测量说明
  - 提供修复指导和监督
  - 直接用户交互和确认

### material_assistant（材料助手）

深度技术信息检索和文档研究专家：

- **能力**：
  - 文献和技术资料检索
  - 文档深度分析
  - 数据库查询（通过 MCP）
  - 技术信息综合

### qa_assistant（问答助手）

网关智能体，负责用户意图识别和请求路由：

- **职责**：
  - 用户意图识别
  - 简单查询直接回答
  - 复杂问题路由到专家智能体
  - 设备参数和基本原理解答

## 配置说明

### 主配置文件（diag-agent.yaml）

配置文件包含以下主要部分：

```yaml
# 默认智能体
default_agent: fault_expert

# 存储配置
storage:
  title_generation_model: null  # 禁用自动标题生成

# 可观测性配置
observability:
  enabled: true
  provider:
    type: custom
    endpoint: "http://phoenix.ai.rootcloud.info/v1/traces"

# 模型变体
model_variants:
  litellm_chat:
    type: string
    identifier: "litellm:svc/glm-4.7"

# MCP 服务器
mcp_servers:
  - type: streamable-http
    url: http://10.147.254.3:7006/mcp
    enabled_tools: ["search_database"]

# 智能体定义
agents:
  fault_expert:
    type: native
    model: "openai-chat:svc/glm-4.7"
    system_prompt:
      - *citation_capability
      - *image_capability
      # ... 更多能力定义
    tools:
      - *question_tool
      - type: skills
      - type: custom
        import_path: xeno_agent.agentpool.resource_providers.XenoDelegationProvider
```

### 环境变量

项目使用 `.envrc` 文件来管理环境变量（推荐使用 direnv）：

```bash
# .envrc 文件内容示例（从 .envrc.example 复制并修改）
# LLM API 配置 - 请根据实际情况修改以下配置
export OPENAI_API_BASE="http://your-api-endpoint/v1"
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_MODEL_NAME="openai/svc/glm-4.6"
export DEFAULT_LLM_MODEL="openai/svc/glm-4.6"
export UV_PACKAGE=packages/xeno_agent

# 可选的模型配置（取消注释使用）
# export OPENAI_MODEL_NAME="openai/svc/kimi-k2"
# export DEFAULT_LLM_MODEL="openai/svc/kimi-k2"
```

**配置步骤**：

1. 复制 `.envrc.example` 为 `.envrc`
2. 编辑 `.envrc` 文件，填写正确的 API 密钥和端点
3. 安装 direnv（如果尚未安装）：
   ```bash
   # macOS
   brew install direnv
   # Ubuntu/Debian
   sudo apt install direnv
   ```
4. 在 shell 中启用 direnv（参考 direnv 官方文档）
5. 在项目目录执行 `direnv allow` 自动加载环境变量

**不使用 direnv 的情况**：

如果不想使用 direnv，可以直接在 shell 中导出环境变量：

```bash
export OPENAI_API_BASE="http://your-api-endpoint/v1"
export OPENAI_API_KEY="your-api-key-here"
export OPENAI_MODEL_NAME="openai/svc/glm-4.6"
export DEFAULT_LLM_MODEL="openai/svc/glm-4.6"
```

## 开发

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行单元测试
uv run pytest -m unit

# 运行集成测试
uv run pytest -m integration

# 查看覆盖率
uv run pytest --cov=src/xeno_agent --cov-report=term-missing
```

### 代码质量

```bash
# 代码检查
uv run ruff check src/

# 代码格式化
uv run ruff format src/

# 类型检查
uv run mypy src/
```

## 日志查询

日志文件位置取决于操作系统：

- **macOS**：`~/Library/Logs/agentpool/`
- **Windows**：`%LOCALAPPDATA%\agentpool\agentpool\logs`（通常是 `C:\Users\<username>\AppData\Local\agentpool\agentpool\logs`）
- **Linux**：`~/.local/state/agentpool/logs`（或 `~/.local/share/agentpool/logs`）

日志文件格式：`agentpool_YYYYMMDD_HHMMSS_microseconds.log`

查看最新日志：

```bash
# macOS/Linux
tail -f ~/Library/Logs/agentpool/agentpool_$(ls -t ~/Library/Logs/agentpool/ | head -1)

# Windows (PowerShell)
Get-Content "$env:LOCALAPPDATA\agentpool\agentpool\logs\agentpool_*.log" -Tail 50 -Wait
```

## 架构设计

### 技术栈

- **核心框架**：AgentPool（多智能体编排）
- **AI 框架**：Pydantic-AI（类型安全的 AI 开发）
- **协议支持**：ACP、OpenCode、MCP
- **工具生态**：bash、read、grep、自定义工具
- **存储**：SQLAlchemy、文件系统
- **可观测性**：Phoenix、结构化日志

### 设计原则

1. **配置即代码**：所有智能体行为通过 YAML 配置定义
2. **协议桥接**：定义一次，通过多种协议暴露
3. **类型安全**：充分利用 Pydantic 的类型系统
4. **可扩展性**：支持自定义工具、资源提供者和智能体类型

## 扩展指南

### 添加新智能体

1. 在配置文件中添加智能体定义
2. 创建系统提示模板（Jinja2）
3. 配置工具和 MCP 服务器
4. 更新 `default_agent` 如需要

### 添加自定义工具

1. 在 `src/xeno_agent/tools/` 中创建工具实现
2. 在配置文件中注册工具
3. 为智能体添加工具引用

## 故障排查

### 常见问题

1. **模型连接失败**：检查环境变量和网络连接
2. **配置文件错误**：使用 YAML Schema 验证
3. **MCP 连接失败**：检查 MCP 服务器 URL 和工具权限
4. **日志文件过大**：配置自动轮转（默认 10MB，保留 5 个备份）

### 调试模式

```bash
# 启用详细日志
export OBSERVABILITY_ENABLED=true
uv run agentpool run --config config/diag-agent.yaml fault_expert "测试"
```

## 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/AmazingFeature`）
3. 提交更改（`git commit -m 'Add some AmazingFeature'`）
4. 推送到分支（`git push origin feature/AmazingFeature`）
5. 开启 Pull Request

## 许可证

[待定]

## 联系方式

- 项目维护者：yuchen.liu@irootech.com
- 问题反馈：[GitLab Issues](http://gitlab.irootech.com/yilab/llm/iroot-llm/-/issues)

## 相关资源

- [AgentPool 文档](https://phil65.github.io/agentpool/)
- [Pydantic-AI 文档](https://ai.pydantic.dev/)
- [ACP 协议](https://github.com/modelcontextprotocol/agents)
- [MCP 协议](https://modelcontextprotocol.io/)

---

**注意**：本项目正处于积极开发中，API 和配置格式可能会发生变化。建议使用最新版本并关注更新日志。
