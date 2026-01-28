# AgentPool Hook 机制调研

## 概述

AgentPool 的 hook 机制提供了一种灵活的方式来拦截和自定义 agent 在关键生命周期节点的行为。Hook 可以用于安全控制、日志记录、权限验证、质量检查等多种场景。

## 核心架构

### HookEvent 模型

Hook 基于事件模型，支持 4 种生命周期事件：

| 事件类型 | 触发时机 | 阻止能力 |
|---------|---------|---------|
| `pre_run` | agent 执行前，处理 prompt 之前 | ✅ 可以阻止执行 |
| `post_run` | agent 执行完成后 | ❌ 仅观察 |
| `pre_tool_use` | 工具调用前 | ✅ 可以阻止或修改输入 |
| `post_tool_use` | 工具调用完成后 | ❌ 仅观察，可注入上下文 |

### 核心数据结构

**HookInput** - 传递给 hook 的上下文数据：

```python
from typing import TypedDict

class HookInput(TypedDict):
    # 通用字段
    event: str              # HookEvent 类型
    agent_name: str         # Agent 名称
    session_id: str | None   # 会话 ID

    # Run 事件专用
    prompt: str | None      # 用户提示词 (pre_run/post_run)
    result: str | None      # 运行结果 (post_run)

    # 工具事件专用
    tool_name: str | None   # 工具名称
    tool_input: dict | None # 工具输入参数
    tool_output: Any | None # 工具输出 (post_tool_use)
    duration_ms: float | None  # 执行耗时 (post_tool_use)
```

**HookResult** - hook 的返回值：

```python
from typing import TypedDict

class HookResult(TypedDict):
    decision: str           # 决策: "allow" | "deny" | "ask"
    reason: str | None      # 决策原因
    modified_input: dict | None  # 修改后的工具输入 (仅 pre_tool_use)
    additional_context: str | None  # 注入的附加上下文
    continue_: bool         # 是否继续执行
```

**决策类型说明：**

| 决策 | 说明 | 使用场景 |
|-----|------|---------|
| `allow` | 允许继续执行 | 默认行为 |
| `deny` | 阻止执行 | 安全拦截、权限拒绝 |
| `ask` | 请求用户确认 | 交互式场景 |

## Hook 类型

### 1. CommandHook（命令钩子）

执行 shell 命令，通过 stdin 接收 JSON 输入，通过 stdout 返回 JSON 输出。

**配置示例：**

```yaml
agents:
  my_agent:
    type: native
    model: openai:gpt-4o
    hooks:
      pre_tool_use:
        - type: command
          command: python $PROJECT_DIR/hooks/validate.py
          matcher: "Bash|Write"
          timeout: 30.0
          env:
            LOG_LEVEL: debug
            ALLOWED_PATHS: /tmp,/home/user
```

**脚本示例（validate.py）：**

```python
#!/usr/bin/env python3
import json
import sys
import os

# 从 stdin 读取输入
data = json.load(sys.stdin)
event = data["event"]
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

# 验证逻辑
if event == "pre_tool_use" and tool_name == "bash":
    command = tool_input.get("command", "")
    if "rm -rf" in command:
        print(json.dumps({
            "decision": "deny",
            "reason": "不允许删除命令"
        }))
        sys.exit(2)  # exit code 2 表示拒绝

    # 验证路径
    if "/etc/" in command:
        print(json.dumps({
            "decision": "deny",
            "reason": "不允许访问 /etc/ 目录"
        }))
        sys.exit(2)

# 允许执行
print(json.dumps({"decision": "allow"}))
sys.exit(0)  # exit code 0 表示允许
```

**退出码约定：**

| 退出码 | 含义 |
|-------|------|
| 0 | 允许（stdout 应包含 JSON 格式的 HookResult） |
| 2 | 拒绝（stderr 作为拒绝原因） |
| 其他 | 错误（记录日志，不阻塞） |

### 2. CallableHook（可调用钩子）

执行 Python 函数或方法，通过导入路径或直接引用指定。

**配置示例：**

```yaml
agents:
  my_agent:
    type: native
    hooks:
      pre_run:
        - type: callable
          import_path: myproject.hooks.auth_check
          arguments:
            strict_mode: true
            max_tokens: 10000

      post_tool_use:
        - type: callable
          import_path: myproject.metrics.track_usage
          arguments:
            metrics_endpoint: https://metrics.example.com
          enabled: true
```

**函数实现示例：**

```python
# myproject/hooks.py
from typing import Any

def auth_check(
    prompt: str,
    agent_name: str,
    strict_mode: bool = False,
    max_tokens: int = 10000,
    **kwargs
) -> dict:
    """权限检查 hook"""
    # 检查敏感操作
    forbidden_patterns = ["delete", "drop", "truncate"]

    if strict_mode:
        forbidden_patterns.extend(["alter", "update", "insert"])

    for pattern in forbidden_patterns:
        if pattern in prompt.lower():
            return {
                "decision": "deny",
                "reason": f"严格模式：不允许 {pattern} 操作"
            }

    # 检查 token 数量
    token_estimate = len(prompt.split())
    if token_estimate > max_tokens:
        return {
            "decision": "deny",
            "reason": f"超过最大 token 限制: {token_estimate} > {max_tokens}"
        }

    return {"decision": "allow"}


def track_usage(
    tool_name: str,
    tool_output: Any,
    duration_ms: float,
    metrics_endpoint: str,
    **kwargs
) -> dict:
    """记录工具使用指标"""
    import requests

    try:
        requests.post(
            f"{metrics_endpoint}/api/metrics",
            json={
                "tool": tool_name,
                "duration_ms": duration_ms,
                "output_length": len(str(tool_output)),
                "timestamp": datetime.now().isoformat()
            },
            timeout=5
        )
    except Exception as e:
        print(f"Failed to send metrics: {e}", file=sys.stderr)

    return {"decision": "allow"}
```

**支持的返回类型：**

```python
# 返回字典
def hook1(**kwargs) -> dict:
    return {"decision": "allow"}

# 返回字符串（会被包装成 decision）
def hook2(**kwargs) -> str:
    return "allow"  # 等价于 {"decision": "allow"}

# 返回布尔值（True=allow, False=deny）
def hook3(**kwargs) -> bool:
    return True

# 返回 None（默认 allow）
def hook4(**kwargs) -> None:
    pass
```

### 3. PromptHook（提示词钩子）

使用 LLM 评估行为，支持结构化输出和占位符替换。

**配置示例：**

```yaml
agents:
  my_agent:
    type: native
    model: openai:gpt-4o
    hooks:
      pre_tool_use:
        - type: prompt
          prompt: |
            评估此操作的安全性和合理性：

            **工具**: $TOOL_NAME
            **输入**: $TOOL_INPUT

            考虑以下因素：
            1. 是否包含恶意代码或命令？
            2. 是否尝试访问受限资源？
            3. 是否符合使用场景？

            返回 JSON 格式的评估结果。
          matcher: "Bash|Write|Read"
          model: openai:gpt-4o-mini
          response_format: json

      post_run:
        - type: prompt
          prompt: |
            分析以下对话，检查是否有需要改进的地方：

            **用户输入**: $PROMPT
            **Agent 回复**: $RESULT

            如果发现问题，提出建议。
          model: openai:gpt-4o-mini
```

**支持的占位符：**

| 占位符 | 说明 | 可用事件 |
|-------|------|---------|
| `$INPUT` | 完整的 hook 输入（JSON） | 所有事件 |
| `$TOOL_NAME` | 工具名称 | 工具事件 |
| `$TOOL_INPUT` | 工具输入参数（JSON） | 工具事件 |
| `$TOOL_OUTPUT` | 工具输出 | post_tool_use |
| `$AGENT_NAME` | Agent 名称 | 所有事件 |
| `$PROMPT` | 用户提示词 | pre_run/post_run |
| `$RESULT` | 运行结果 | post_run |
| `$EVENT` | Hook 事件名称 | 所有事件 |

**默认模型：** `openai:gpt-4o-mini`

## 自定义 Hook

### 1. 创建 Hook 类

```python
# myproject/hooks.py
from agentpool.hooks.base import Hook, HookEvent, HookInput, HookResult
from typing import Any
import re

class SecurityHook(Hook):
    """安全检查 Hook"""

    def __init__(
        self,
        event: HookEvent,
        blocked_patterns: list[str],
        allowed_paths: list[str] | None = None,
        **kwargs
    ):
        super().__init__(event=event, **kwargs)
        self.blocked_patterns = [re.compile(p) for p in blocked_patterns]
        self.allowed_paths = set(allowed_paths or [])

    async def execute(self, input_data: HookInput) -> HookResult:
        """执行 hook 逻辑"""

        # pre_run: 检查 prompt
        if input_data["event"] == "pre_run":
            prompt = input_data.get("prompt", "")
            for pattern in self.blocked_patterns:
                if pattern.search(prompt):
                    return HookResult(
                        decision="deny",
                        reason=f"包含禁止的模式: {pattern.pattern}"
                    )

        # pre_tool_use: 检查工具输入
        elif input_data["event"] == "pre_tool_use":
            tool_name = input_data.get("tool_name", "")
            tool_input = input_data.get("tool_input", {})

            # 检查路径访问
            if "path" in tool_input:
                path = tool_input["path"]
                if not self._is_path_allowed(path):
                    return HookResult(
                        decision="deny",
                        reason=f"路径 {path} 不在允许列表中"
                    )

            # 检查文件操作
            if tool_name in ["Write", "Edit"]:
                for pattern in self.blocked_patterns:
                    if pattern.search(str(tool_input)):
                        return HookResult(
                            decision="deny",
                            reason=f"写入内容包含禁止的模式"
                        )

        return HookResult(decision="allow")

    def _is_path_allowed(self, path: str) -> bool:
        """检查路径是否允许"""
        # 检查是否在允许的路径下
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        return False
```

### 2. 注册配置模型

```python
# src/agentpool_config/hooks.py
from pydantic import Field
from typing import Literal

class SecurityHookConfig(BaseHookConfig):
    """安全检查 Hook 配置"""

    type: Literal["security"] = Field("security", init=False)

    blocked_patterns: list[str] = Field(
        title="禁止的模式列表（正则表达式）",
        default_factory=list
    )

    allowed_paths: list[str] = Field(
        title="允许的路径列表",
        default_factory=list
    )

    def get_hook(self, event: HookEvent) -> Hook:
        """创建 Hook 实例"""
        from agentpool.hooks import SecurityHook

        return SecurityHook(
            event=event,
            blocked_patterns=self.blocked_patterns,
            allowed_paths=self.allowed_paths,
            matcher=self.matcher,
            timeout=self.timeout,
            enabled=self.enabled,
        )
```

### 3. 更新 HookConfig 联合类型

```python
# src/agentpool_config/hooks.py（末尾）

# 在 HookConfig 联合类型中添加新的 hook 类型
HookConfig = Annotated[
    CommandHookConfig |
    CallableHookConfig |
    PromptHookConfig |
    SecurityHookConfig,  # 添加自定义 hook
    Field(discriminator="type"),
]
```

### 4. 使用自定义 Hook

**YAML 配置：**

```yaml
agents:
  secure_agent:
    type: native
    model: openai:gpt-4o
    hooks:
      pre_run:
        - type: security
          blocked_patterns:
            - "rm\s+-rf"
            - "drop\s+table"
            - "truncate\s+table"
          enabled: true

      pre_tool_use:
        - type: security
          blocked_patterns:
            - "rm\s+-rf"
            - "/etc/"
            - "/var/"
          allowed_paths:
            - "/tmp/"
            - "/home/user/"
            - "/workspace/"
          matcher: "Bash|Write|Edit|Read"
          timeout: 30.0
```

**程序化配置：**

```python
from agentpool import Agent
from agentpool.hooks import AgentHooks
from myproject.hooks import SecurityHook

hooks = AgentHooks(
    pre_run=[
        SecurityHook(
            event="pre_run",
            blocked_patterns=["delete", "drop", "truncate"],
            enabled=True
        )
    ],
    pre_tool_use=[
        SecurityHook(
            event="pre_tool_use",
            blocked_patterns=["rm -rf", "/etc/"],
            allowed_paths=["/tmp/", "/home/user/"],
            matcher="Bash|Write",
            timeout=30.0
        )
    ]
)

agent = Agent(model="openai:gpt-4o", hooks=hooks)
```

## Hook 容器与执行

### AgentHooks 容器

```python
from dataclasses import dataclass
from typing import Sequence

@dataclass
class AgentHooks:
    """Agent hooks 容器"""
    pre_run: Sequence[Hook] = field(default_factory=list)
    post_run: Sequence[Hook] = field(default_factory=list)
    pre_tool_use: Sequence[Hook] = field(default_factory=list)
    post_tool_use: Sequence[Hook] = field(default_factory=list)

    async def run_pre_run_hooks(
        self,
        agent_name: str,
        prompt: str,
        session_id: str | None = None
    ) -> dict:
        """执行 pre_run hooks"""
        ...

    async def run_post_run_hooks(
        self,
        agent_name: str,
        prompt: str,
        result: str,
        session_id: str | None = None
    ) -> dict:
        """执行 post_run hooks"""
        ...

    async def run_pre_tool_hooks(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict,
        session_id: str | None = None
    ) -> dict:
        """执行 pre_tool_use hooks"""
        ...

    async def run_post_tool_hooks(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: dict,
        tool_output: Any,
        duration_ms: float,
        session_id: str | None = None
    ) -> dict:
        """执行 post_tool_use hooks"""
        ...
```

### Hook 执行流程

**决策优先级：**

```
deny > ask > allow
```

如果多个 hook 返回不同的决策，优先级最高的生效。

**结果合并规则：**

1. **modified_input**：多个 hook 的修改会被合并（后面的覆盖前面的）
2. **additional_context**：所有 hook 的上下文会被连接起来
3. **continue_**：任何一个 hook 返回 False，整体为 False

**并行执行：**

```python
async def _run_hooks(self, hooks: Sequence[Hook], input_data: HookInput) -> HookResult:
    """并行执行 hooks"""
    import asyncio

    # 并行执行所有 hooks
    results = await asyncio.gather(
        *[hook.execute(input_data) for hook in hooks],
        return_exceptions=True
    )

    # 合并结果
    combined = self._combine_results(results)
    return combined
```

## 集成点

### 1. 与 BaseAgent 集成

```python
# src/agentpool/agents/base_agent.py

async def run_stream(self, message: str, ...):
    """Agent 主执行流程"""

    # 1. Pre-run hooks
    if self.hooks:
        pre_run_result = await self.hooks.run_pre_run_hooks(
            agent_name=self.name,
            prompt=message,
            session_id=self.session_id,
        )

        if pre_run_result.get("decision") == "deny":
            reason = pre_run_result.get("reason", "Unknown reason")
            raise RuntimeError(f"Run blocked: {reason}")

        # 注入附加上下文
        if additional := pre_run_result.get("additional_context"):
            message = f"{message}\n\n{additional}"

    # 2. 执行 agent 逻辑
    # ... agent processing ...

    # 3. Post-run hooks
    if self.hooks:
        await self.hooks.run_post_run_hooks(
            agent_name=self.name,
            prompt=message,
            result=final_message.content,
            session_id=self.session_id,
        )

    return final_message
```

### 2. 与工具集成

```python
# src/agentpool/agents/native_agent/tool_wrapping.py

async def wrap_tool(tool: Tool, hooks: AgentHooks, ...):
    """包装工具执行，集成 hooks"""

    # 1. Pre-tool hooks
    if hooks:
        pre_result = await hooks.run_pre_tool_hooks(
            agent_name=agent_ctx.node_name,
            tool_name=tool.name,
            tool_input=tool_input,
            session_id=None,
        )

        decision = pre_result.get("decision", "allow")

        if decision == "deny":
            reason = pre_result.get("reason", "Unknown reason")
            raise ToolSkippedError(f"Tool {tool.name} blocked: {reason}")

        # 应用修改后的输入
        if modified_input := pre_result.get("modified_input"):
            kwargs.update(modified_input)

    # 2. 执行工具
    result = await tool(**kwargs)

    # 3. Post-tool hooks
    if hooks:
        post_result = await hooks.run_post_tool_hooks(
            agent_name=agent_ctx.node_name,
            tool_name=tool.name,
            tool_input=tool_input,
            tool_output=result,
            duration_ms=duration,
            session_id=None,
        )

        # 注入附加上下文
        if additional := post_result.get("additional_context"):
            result = _inject_additional_context(result, additional)

    return result
```

### 3. 与不同 Agent 类型集成

| Agent 类型 | Hook 支持 | 说明 |
|-----------|----------|------|
| NativeAgent | 完整支持（4 种事件） | 通过 `hooks` 配置 |
| ClaudeCodeAgent | Pre/post tool hooks | 通过 SDK 转换 |
| ACPAgent | 通过配置 | 标准钩子接口 |
| AGUIAgent | 通过配置 | 标准钩子接口 |
| CodexAgent | 通过配置 | 标准钩子接口 |

## 高级功能

### 1. Matcher 模式匹配

使用正则表达式匹配工具名称：

```yaml
hooks:
  pre_tool_use:
    - type: callable
      import_path: myproject.hooks.security_check
      matcher: "Bash"  # 仅匹配 Bash 工具

    - type: prompt
      prompt: "验证文件操作安全性"
      matcher: "Write|Edit|Read"  # 匹配多个工具

    - type: callable
      import_path: myproject.hooks.mcp_check
      matcher: "mcp__.*"  # 匹配所有 MCP 工具

    - type: callable
      import_path: myproject.hooks.log_all
      matcher: "*"  # 匹配所有工具
```

### 2. 条件过滤

使用 `hook_conditions` 提供更细粒度的控制：

```yaml
hooks:
  pre_tool_use:
    - type: callable
      import_path: myproject.hooks.check_duration
      conditions:
        - type: duration
          operator: ">"
          value: 5000  # 仅在工具耗时超过 5 秒时触发

        - type: argument
          argument_name: "path"
          operator: "contains"
          value: "/etc/"  # 仅在 path 参数包含 /etc/ 时触发

    - type: prompt
      prompt: "验证大文件操作"
      conditions:
        - type: output_size
          operator: ">"
          value: 10000000  # 仅在输出大于 10MB 时触发

        - type: jinja2
          condition: "{{ tool_input.get('extension') in ['exe', 'sh'] }}"
```

**可用的条件类型：**

| 条件类型 | 说明 | 示例 |
|---------|------|-----|
| `tool_name` | 匹配工具名称 | `tool_name: "Bash"` |
| `argument` | 检查工具参数 | `argument: {"name": "path", "operator": "contains", "value": "/tmp/"}` |
| `argument_exists` | 检查参数是否存在 | `argument_exists: "dry_run"` |
| `duration` | 检查执行耗时 | `duration: {"operator": ">", "value": 1000}` |
| `output` | 检查输出内容 | `output: {"operator": "contains", "value": "error"}` |
| `output_size` | 检查输出大小 | `output_size: {"operator": ">", "value": 1000000}` |
| `prompt` | 检查提示词内容 | `prompt: {"operator": "contains", "value": "secret"}` |
| `jinja2` | Jinja2 模板条件 | `condition: "{{ tool_input.get('max_retries', 0) > 3 }}"` |
| `and` / `or` / `not` | 逻辑组合 | `and: [condition1, condition2]` |

### 3. Hook 链与组合

多个 hook 可以协同工作：

```yaml
agents:
  my_agent:
    hooks:
      # 第一层：基础验证
      pre_tool_use:
        - type: callable
          import_path: myproject.hooks.basic_auth

      # 第二层：内容检查
        - type: prompt
          prompt: "检查内容安全性"
          model: openai:gpt-4o-mini

      # 第三层：特定工具验证
        - type: command
          command: ./hooks/validate-write.sh
          matcher: "Write"
```

### 4. Hook 上下文注入

**修改工具输入（pre_tool_use）：**

```python
def add_defaults(tool_name: str, tool_input: dict, **kwargs) -> dict:
    """为工具参数添加默认值"""
    defaults = {
        "bash": {"timeout": 30, "capture_output": True},
        "read": {"limit": 1000},
        "write": {"create_dirs": True}
    }

    if tool_name in defaults:
        modified = defaults[tool_name].copy()
        modified.update(tool_input)
        return {
            "decision": "allow",
            "modified_input": modified
        }

    return {"decision": "allow"}
```

**注入附加上下文（post_tool_use）：**

```python
def add_explanation(tool_name: str, tool_output: str, **kwargs) -> dict:
    """为工具输出添加解释"""
    explanations = {
        "bash": "\n\n💡 提示：Shell 命令已执行，请检查退出码和输出。",
        "grep": "\n\n💡 提示：Grep 搜索结果可能需要进一步分析。",
        "read": "\n\n💡 提示：文件已读取，内容长度为 {len(tool_output)} 字符。"
    }

    explanation = explanations.get(tool_name, "")
    return {
        "decision": "allow",
        "additional_context": explanation
    }
```

## Hook 能力边界

### ✅ Hook 可以做的

| 能力 | 说明 |
|-----|------|
| 阻止 agent 执行 | pre_run hook 返回 `decision: "deny"` |
| 阻止工具调用 | pre_tool_use hook 返回 `decision: "deny"` |
| 修改工具输入 | pre_tool_use hook 返回 `modified_input` |
| 追加到工具输出 | post_tool_use hook 返回 `additional_context` |
| 记录日志和指标 | 在任何 hook 中 |
| 修改 agent 行为 | 通过上下文注入或提示词修改 |
| 并行执行多个 hook | 所有类型的 hook 都支持并行 |

### ❌ Hook 不能做的

| 限制 | 说明 |
|-----|------|
| 编辑历史消息 | 不能修改已经存在的对话历史 |
| 删除消息 | 不能从历史中删除消息 |
| 修改 agent 内部状态 | hook 是无状态的，不能持久化状态 |
| 阻止 post_run | post_run hooks 不能阻止执行 |
| 直接访问数据库 | hook 中需要自己实现数据库访问 |
| 跨会话通信 | hook 只能访问当前会话的信息 |

### ⚠️ 重要说明：Messages History

**Hook 不能直接编辑 messages history**，但可以通过 `additional_context` 向对话中注入信息，这些信息会成为对话历史的一部分。

**为什么不能编辑历史消息？**

1. **架构设计**：Hook 的设计意图是拦截和观察，而不是修改状态
2. **数据流**：Messages history 是从外部传入的，hook 没有权限修改
3. **安全性**：直接编辑历史消息可能导致对话完整性被破坏

**替代方案：**

```python
# 方案 1：使用 additional_context（推荐）
def add_correction(tool_output: str, **kwargs) -> dict:
    correction = get_correction(tool_output)
    return {
        "decision": "allow",
        "additional_context": f"\n\n⚠️ 注意：{correction}"
    }

# 方案 2：在 agent 外部后处理
async with Agent("config.yml") as pool:
    agent = pool.get_agent("my_agent")

    # 运行并保存历史
    history = []
    result = await agent.run("prompt", message_history=history)

    # 后处理历史（在 agent 外部）
    processed_history = []
    for msg in history:
        processed_msg = sanitize_message(msg)
        processed_history.append(processed_msg)
```

## 配置示例

### 完整的 YAML 配置示例

```yaml
agents:
  secure_agent:
    type: native
    model: openai:gpt-4o
    system_prompt: "你是一个安全的 AI 助手，遵循所有安全规则。"
    tools:
      - name: bash
        enabled: true
      - name: read
        enabled: true
      - name: write
        enabled: true

    hooks:
      # Pre-run: 权限验证
      pre_run:
        - type: callable
          import_path: myproject.auth.check_user_permission
          arguments:
            require_admin: true
          enabled: true

      # Pre-tool-use: 安全检查
      pre_tool_use:
        # LLM 安全评估
        - type: prompt
          prompt: |
            评估以下工具调用的安全性：

            工具: $TOOL_NAME
            输入: $TOOL_INPUT

            如果存在风险，返回 decision: "deny" 并说明原因。
          matcher: "Bash|Write|Edit"
          model: openai:gpt-4o-mini

        # 路径验证
        - type: command
          command: python $PROJECT_DIR/hooks/validate_paths.py
          matcher: "Read|Write"
          env:
            ALLOWED_PATHS: /tmp,/home/user,/workspace

        # 命令验证
        - type: callable
          import_path: myproject.security.validate_command
          matcher: "Bash"
          arguments:
            blocked_commands: ["rm -rf", "mkfs", "dd"]

      # Post-tool-use: 日志和监控
      post_tool_use:
        - type: callable
          import_path: myproject.metrics.track_tool_usage
          arguments:
            metrics_endpoint: https://metrics.example.com

        - type: callable
          import_path: myproject.logging.log_tool_call
          arguments:
            log_level: info

        # 性能监控
        - type: callable
          import_path: myproject.performance.check_duration
          conditions:
            - type: duration
              operator: ">"
              value: 10000  # 仅在耗时 > 10s 时触发

      # Post-run: 通知和总结
      post_run:
        - type: command
          command: ./scripts/notify-completion.sh
          env:
            WEBHOOK_URL: https://hooks.example.com/agent-completion

        - type: callable
          import_path: myproject.reporting.generate_summary
```

### 复杂条件配置示例

```yaml
hooks:
  pre_tool_use:
    # 仅对特定工具且满足特定条件时触发
    - type: callable
      import_path: myproject.hooks.advanced_check
      matcher: "Bash|Write"
      conditions:
        # 复合条件：AND
        - type: and
          conditions:
            - type: argument
              argument_name: "path"
              operator: "contains"
              value: "/etc/"

            - type: jinja2
              condition: "{{ not tool_input.get('dry_run', false) }}"

        # OR 条件
        - type: or
          conditions:
            - type: duration
              operator: ">"
              value: 5000

            - type: output_size
              operator: ">"
              value: 1000000

        # NOT 条件
        - type: not
          condition:
            type: argument
            argument_name: "user"
            operator: "equals"
            value: "admin"
```

## 测试和调试

### Hook 测试示例

```python
# tests/hooks/test_hooks.py
import pytest
from agentpool.hooks import CallableHook, AgentHooks
from agentpool.hooks.base import HookInput

@pytest.mark.asyncio
async def test_callable_hook_allow():
    """测试 CallableHook 允许决策"""
    def allow_hook(**kwargs) -> dict:
        return {"decision": "allow"}

    hook = CallableHook(event="pre_run", fn=allow_hook)
    result = await hook.execute(HookInput(
        event="pre_run",
        agent_name="test",
        prompt="test prompt"
    ))

    assert result["decision"] == "allow"


@pytest.mark.asyncio
async def test_callable_hook_deny():
    """测试 CallableHook 拒绝决策"""
    def deny_hook(prompt: str, **kwargs) -> dict:
        if "delete" in prompt.lower():
            return {
                "decision": "deny",
                "reason": "不允许删除操作"
            }
        return {"decision": "allow"}

    hook = CallableHook(event="pre_run", fn=deny_hook)

    # 允许的提示词
    result = await hook.execute(HookInput(
        event="pre_run",
        agent_name="test",
        prompt="read file"
    ))
    assert result["decision"] == "allow"

    # 拒绝的提示词
    result = await hook.execute(HookInput(
        event="pre_run",
        agent_name="test",
        prompt="delete file"
    ))
    assert result["decision"] == "deny"
    assert "删除" in result["reason"]


@pytest.mark.asyncio
async def test_modified_input():
    """测试修改工具输入"""
    def modify_hook(tool_input: dict, **kwargs) -> dict:
        modified = tool_input.copy()
        modified.setdefault("timeout", 30)
        modified.setdefault("verbose", True)
        return {
            "decision": "allow",
            "modified_input": modified
        }

    hook = CallableHook(event="pre_tool_use", fn=modify_hook)
    result = await hook.execute(HookInput(
        event="pre_tool_use",
        agent_name="test",
        tool_name="bash",
        tool_input={"command": "ls"}
    ))

    assert result["decision"] == "allow"
    assert result["modified_input"]["timeout"] == 30
    assert result["modified_input"]["verbose"] is True


@pytest.mark.asyncio
async def test_additional_context():
    """测试附加上下文注入"""
    def add_context_hook(tool_output: str, **kwargs) -> dict:
        return {
            "decision": "allow",
            "additional_context": "\n\n💡 提示：操作已完成。"
        }

    hook = CallableHook(event="post_tool_use", fn=add_context_hook)
    result = await hook.execute(HookInput(
        event="post_tool_use",
        agent_name="test",
        tool_name="read",
        tool_output="file content",
        duration_ms=100
    ))

    assert result["decision"] == "allow"
    assert "提示" in result["additional_context"]
```

### 调试技巧

1. **启用详细日志：**

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("agentpool.hooks")
```

2. **在 hook 中添加日志：**

```python
def my_hook(**kwargs) -> dict:
    logger.debug(f"Hook received input: {kwargs}")
    # ... hook logic ...
    logger.debug(f"Hook returning: {result}")
    return result
```

3. **测试 hook 配置：**

```python
from agentpool_config import load_manifest

manifest = load_manifest("config.yml")
agent_config = manifest.agents["my_agent"]
hooks = agent_config.hooks.get_agent_hooks()

# 验证 hook 是否正确加载
assert len(hooks.pre_tool_use) > 0
assert all(hook.enabled for hook in hooks.pre_tool_use)
```

## 最佳实践

### 1. Hook 性能优化

```python
# ✅ 好：轻量级 hook
def fast_check(**kwargs) -> dict:
    """快速检查，不做复杂操作"""
    prompt = kwargs.get("prompt", "")
    if "delete" in prompt.lower():
        return {"decision": "deny"}
    return {"decision": "allow"}

# ❌ 避免：耗时操作
def slow_check(**kwargs) -> dict:
    """避免在 hook 中做耗时操作"""
    import time
    time.sleep(5)  # 阻塞 5 秒！
    return {"decision": "allow"}

# ✅ 推荐：异步操作
async def async_check(**kwargs) -> dict:
    """使用异步操作"""
    await asyncio.sleep(0.1)  # 非阻塞
    return {"decision": "allow"}
```

### 2. Hook 错误处理

```python
def safe_hook(**kwargs) -> dict:
    """安全处理 hook 中的错误"""
    try:
        # Hook 逻辑
        result = my_check_function(**kwargs)
        return {"decision": "allow", "data": result}
    except Exception as e:
        # 记录错误但不阻塞执行
        logger.error(f"Hook error: {e}")
        return {"decision": "allow"}  # 默认允许
```

### 3. Hook 组合策略

```yaml
hooks:
  pre_tool_use:
    # 第一层：快速过滤
    - type: callable
      import_path: myproject.hooks.quick_filter
      timeout: 1.0

    # 第二层：详细检查
    - type: prompt
      prompt: "详细安全评估"
      model: openai:gpt-4o-mini
      timeout: 10.0

    # 第三层：特定验证
    - type: command
      command: ./hooks/validate.sh
      timeout: 5.0
```

### 4. Hook 条件使用

```yaml
# ✅ 好：使用条件减少不必要的 hook 调用
hooks:
  post_tool_use:
    - type: callable
      import_path: myproject.hooks.performance_check
      conditions:
        - type: duration
          operator: ">"
          value: 10000  # 仅在耗时 > 10s 时检查

# ❌ 避免：无条件触发所有 hooks
hooks:
  post_tool_use:
    - type: callable
      import_path: myproject.hooks.performance_check  # 每次都触发
```

## 关键文件索引

| 文件路径 | 说明 |
|---------|------|
| `src/agentpool/hooks/base.py` | Hook 基类和核心数据结构 |
| `src/agentpool/hooks/agent_hooks.py` | AgentHooks 容器和 hook 执行逻辑 |
| `src/agentpool/hooks/command.py` | CommandHook 实现 |
| `src/agentpool/hooks/callable.py` | CallableHook 实现 |
| `src/agentpool/hooks/prompt.py` | PromptHook 实现 |
| `src/agentpool_config/hooks.py` | Hook 配置模型 |
| `src/agentpool_config/hook_conditions.py` | 条件过滤模型 |
| `src/agentpool/agents/base_agent.py` | Hook 在 agent 中的集成 |
| `src/agentpool/agents/native_agent/tool_wrapping.py` | Hook 在工具中的集成 |
| `src/agentpool/agents/*/hook_manager.py` | 各 agent 类型的 hook 管理器 |
| `docs/configuration/hooks.md` | 官方文档 |

## 总结

AgentPool 的 hook 机制提供了强大的拦截和自定义能力，支持：

- **4 种生命周期事件**：pre_run、post_run、pre_tool_use、post_tool_use
- **3 种内置 hook 类型**：CommandHook、CallableHook、PromptHook
- **自定义 hook**：通过继承 `Hook` 类并注册配置模型
- **灵活配置**：YAML 配置和程序化配置
- **高级功能**：模式匹配、条件过滤、上下文注入、并行执行

**适用场景：**
- 安全控制和权限验证
- 日志记录和指标追踪
- 性能监控和优化
- 内容审核和质量检查
- 工具输入/输出的后处理

**限制：**
- 不能直接编辑历史消息
- 不能持久化状态（hook 是无状态的）
- Post hooks 不能阻止执行（仅观察）

通过合理使用 hook，可以显著增强 agent 的可控性、安全性和可观测性。
