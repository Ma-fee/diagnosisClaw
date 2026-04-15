# Scripts README

本目录用于本地联调与辅助脚本。

## 文件说明

- `start_local_stack.sh`
  - 一键启动本地联调栈（Phoenix / Scratchpad / RAG MCP / Xeno OpenCode）。
  - 会生成本地运行时 manifest，并写入 `.runtime/local-stack` 下的日志与 pid。

- `local_stack_ctl.sh`
  - 可拆分控制本地联调栈，支持分别启动/停止各服务。
  - 推荐用于调试单个服务启动失败的场景。

- `migrate_to_agentpool.py`
  - 迁移相关辅助脚本。

## `local_stack_ctl.sh` 用法

在仓库根目录执行：

### 启动（4个）

```bash
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-phoenix
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-scratchpad
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-rag
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-agent
```

### 启动时在当前终端持续看日志（可选）

在任一 `start-*` 命令后加 `--follow-log`：

```bash
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-phoenix --follow-log
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-scratchpad --follow-log
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-rag --follow-log
bash packages/xeno-agent/scripts/local_stack_ctl.sh start-agent --follow-log
```

说明：
- 会先启动对应服务，然后自动执行该服务日志的 `tail -f`。
- 退出日志跟随可按 `Ctrl+C`，不会停止已启动的服务。

### 停止（4个）

```bash
bash packages/xeno-agent/scripts/local_stack_ctl.sh stop-phoenix
bash packages/xeno-agent/scripts/local_stack_ctl.sh stop-scratchpad
bash packages/xeno-agent/scripts/local_stack_ctl.sh stop-rag
bash packages/xeno-agent/scripts/local_stack_ctl.sh stop-agent
```

### 状态查看

```bash
bash packages/xeno-agent/scripts/local_stack_ctl.sh status
```

## 默认端口

- Phoenix: `6606`
- Scratchpad: `8891`（path: `/mcp`）
- RAG MCP: `8788`（transport: `sse`）
- Xeno OpenCode: `7163`

## 日志与 PID

默认写入：`packages/xeno-agent/.runtime/local-stack/`

- 日志：`logs/*.log`
- PID：`pids/*.pid`

常用排查命令：

```bash
# 查看 agent 日志
tail -f packages/xeno-agent/.runtime/local-stack/logs/xeno_opencode.log

# 查看 rag 日志
tail -f packages/xeno-agent/.runtime/local-stack/logs/rag_mcp.log
```

## 环境变量覆盖（可选）

`local_stack_ctl.sh` 支持通过环境变量覆盖默认配置，例如：

- `PHOENIX_HOST`, `PHOENIX_PORT`
- `SCRATCHPAD_HOST`, `SCRATCHPAD_PORT`, `SCRATCHPAD_PATH`
- `RAG_HOST`, `RAG_PORT`, `RAG_TRANSPORT`
- `OPENCODE_HOST`, `OPENCODE_PORT`
- `RUNTIME_ROOT`, `RAG_DIR`, `SCRATCHPAD_DIR`

示例：

```bash
OPENCODE_PORT=7263 bash packages/xeno-agent/scripts/local_stack_ctl.sh start-agent
```
