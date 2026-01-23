# acp_cli 故障排除摘要

## 问题分析

`uv run -m xeno_agent.pydantic_ai.acp_cli` 在当前环境中执行时遇到以下问题：

1. **stdio_streams() 失败**: `KeyError: '0 is not registered'`
   - 原因：`acp.stdio.stdio_streams()` 试图在非交互式 stdio 环境中注册 stdin/stdout 时失败

2. **类型检查错误**: `TypeError: AgentSideConnection requires asyncio StreamWriter/Reader`
   - 原因：若流创建成功，acp 库的内部类型检查与 `stdio_streams()` 返回的流对象不匹配

3. **上下文泄漏**: `RuntimeError: Attempted to exit cancel scope in a different task`
   - 原因：MCPServerStreamableHTTP 在不同任务中清理时的已知限制

---

## 根本原因

**agent-client-protocol (acp)** 库期望在其控制的事件循环 context 中正确运行，特别是在:
- 真实的交互式终端（stdin/stdout 可用且未被其他进程占用）
- 没有其他 asyncio 选择器冲突的环境

---

## 解决方案选项

### 选项 1：在真实终端中运行（最推荐）** ✅

从真实的终端交互式地运行（而非像 tmux/screen 或 piped 来源 的环境）：

```bash
# 在真实终端中直接运行
uv run -m xeno_agent.pydantic_ai.acp_cli fault_diagnosis
```

#### 为什么应该有效：
- stdin 和 stdout 直接连接到真正的终端
- 没有其他进程侵犯文件描述符
- acp.stdio.stdio_streams() 可以正确注册流

---

### 选项 2：采用原生 pydantic-ai CLI（无需 acp）

创建不依赖 `acp` 库的简化版本。请参阅下方实现。

**优点**：
- 不依赖 `acp` 的流处理
- 可在更大范围的环境中工作
- 避免类型检查问题

**缺点**：
- 不严格遵循 ACP 协议（但功能等效）
- 需要维护额外代码

---

### 选项 3：向 acp 项目报告问题

如果您确定需要在当前环境中使用 `acp.run_agent()`，请报告该问题：

- 仓库：[agent-client-protocol](https://github.com/anthropics/agent-client-protocol)（或其官方位置）
- 问题：在非交互式 stdio 环境中 `stdio_streams()` 失败
- 错误：`KeyError: '0 is not registered'`

复现：
```python
from acp.stdio import stdio_streams
import asyncio

async def reproduce():
    # 从非交互式环境或竞争条件中运行
    input_stream, output_stream = await stdio_streams()
    
asyncio.run(reproduce())
```

---

## 简化版 CLI 实现（不用 acp）

如果选项 2 可接受，以下是最小化版本：

```python
#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from xeno_agent.pydantic_ai.config_loader import YAMLConfigLoader
from xeno_agent.pydantic_ai.factory import AgentFactory
from xeno_agent.pydantic_ai.runtime import LocalAgentRuntime

def setup_logging(log_file: Path | None, log_level: str):
    level = getattr(logging, log_level.upper(), logging.INFO)
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", handlers=handlers, force=True)

async def simple_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("flow_id")
    parser.add_argument("--model", default="openai:svc/glm-4.7")
    parser.add_argument("--skip-mcp-tools", action="store_true")
    parser.add_argument("--mcp-timeout", type=float, default=30.0)
    args = parser.parse_args()

    setup_logging(None, "INFO")

    loader = YAMLConfigLoader(base_path=Path(__file__).parents[3] / "config")
    factory = AgentFactory(config_loader=loader, model=args.model)
    flow_config = loader.load_flow_config(args.flow_id)

    runtime = LocalAgentRuntime(factory, flow_config)
    await runtime.tool_manager.initialize(skip_mcp=args.skip_mcp_tools, mcp_timeout=args.mcp_timeout)

    print("\n=== Xeno Agent CLI (Native pydantic-ai) ===")
    print(f"Flow: {args.flow_id} | Model: {args.model}")
    print("\nType a message (empty line to exit)\n")

    agent = await factory.create(args.flow_id, flow_config, tool_manager=runtime.tool_manager)
    try:
        while True:
            try:
                prompt = input("> ")
                if not prompt.strip():
                    break
                result = await agent.run(prompt)
                print(f"\n{result.final_response() or '(no response)'}\n")
            except (EOFError, KeyboardInterrupt):
                break
    finally:
        await runtime.tool_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(simple_cli())
```

---

## 总结

| 方案 | 易用性 | 需要更改 | 推荐度 |
|------|---------|----------|---------|
| **选项 1：真实终端** | ⭐⭐⭐⭐⭐ | 🟢 无 | ⭐⭐⭐⭐⭐ |
| **选项 2：原生 CLI** | ⭐⭐⭐⭐ | 🟡 需创建新文件 | ⭐⭐⭐⭐ |
| **选项 3：报告问题** | ⭐ | 🔴 长期 | ⭐⭐ |

**推荐**：首先在真实终端中运行（选项 1），如果失败则采用简化版 CLI（选项 2）。
