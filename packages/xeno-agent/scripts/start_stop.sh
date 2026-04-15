#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XENO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$XENO_DIR/../.." && pwd)"
AGENTPOOL_DIR="$REPO_ROOT/packages/agentpool"
RAG_DIR="/Users/admin/Downloads/rag_mcp/.worktrees/phase4-runtime-merge"
SCRATCHPAD_DIR="/Users/admin/Downloads/scratchpad/.worktrees/overlay-fs-integration-spec"
SCRATCHPAD_PROJECT_DIR="$SCRATCHPAD_DIR/packages/mcp-scratchpad"
BASE_MANIFEST="$XENO_DIR/config/diag-agent-v5.yaml"

PHOENIX_HOST="${PHOENIX_HOST:-127.0.0.1}"
PHOENIX_PORT="${PHOENIX_PORT:-6606}"
SCRATCHPAD_HOST="${SCRATCHPAD_HOST:-127.0.0.1}"
SCRATCHPAD_PORT="${SCRATCHPAD_PORT:-8891}"
SCRATCHPAD_PATH="${SCRATCHPAD_PATH:-/mcp}"
RAG_HOST="${RAG_HOST:-127.0.0.1}"
RAG_PORT="${RAG_PORT:-8788}"
RAG_TRANSPORT="${RAG_TRANSPORT:-sse}"
OPENCODE_HOST="${OPENCODE_HOST:-127.0.0.1}"
OPENCODE_PORT="${OPENCODE_PORT:-7163}"

RUNTIME_ROOT="${RUNTIME_ROOT:-$XENO_DIR/.runtime/local-stack}"
LOG_DIR="$RUNTIME_ROOT/logs"
PID_DIR="$RUNTIME_ROOT/pids"
SCRATCHPAD_RUNTIME="$RUNTIME_ROOT/scratchpad"
MANIFEST_PATH="$RUNTIME_ROOT/diag-agent-v5.local.yaml"

mkdir -p \
  "$LOG_DIR" \
  "$PID_DIR" \
  "$SCRATCHPAD_RUNTIME/workspace" \
  "$SCRATCHPAD_RUNTIME/shared-memory/users" \
  "$SCRATCHPAD_RUNTIME/shared-memory/agents" \
  "$SCRATCHPAD_RUNTIME/shared-memory/teams" \
  "$SCRATCHPAD_RUNTIME/shared-memory/shared"

if [[ ! -d "$RAG_DIR" ]]; then
  echo "rag_mcp worktree not found: $RAG_DIR" >&2
  exit 1
fi

if [[ ! -d "$SCRATCHPAD_DIR" ]]; then
  echo "scratchpad worktree not found: $SCRATCHPAD_DIR" >&2
  exit 1
fi

if [[ ! -d "$SCRATCHPAD_PROJECT_DIR" ]]; then
  echo "scratchpad project not found: $SCRATCHPAD_PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -f "$RAG_DIR/.env" ]]; then
  echo "rag_mcp .env not found: $RAG_DIR/.env" >&2
  exit 1
fi

if [[ ! -f "$BASE_MANIFEST" ]]; then
  echo "Base manifest not found: $BASE_MANIFEST" >&2
  exit 1
fi

if [[ ! -f "$XENO_DIR/.envrc" ]]; then
  echo "xeno-agent .envrc not found: $XENO_DIR/.envrc" >&2
  exit 1
fi

if command -v lsof >/dev/null 2>&1; then
  for port in "$PHOENIX_PORT" "$SCRATCHPAD_PORT" "$RAG_PORT" "$OPENCODE_PORT"; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      echo "Port already in use: $port" >&2
      exit 1
    fi
  done
fi

MANIFEST_PATH="$MANIFEST_PATH" \
BASE_MANIFEST="$BASE_MANIFEST" \
PHOENIX_HOST="$PHOENIX_HOST" \
PHOENIX_PORT="$PHOENIX_PORT" \
SCRATCHPAD_HOST="$SCRATCHPAD_HOST" \
SCRATCHPAD_PORT="$SCRATCHPAD_PORT" \
SCRATCHPAD_PATH="$SCRATCHPAD_PATH" \
RAG_HOST="$RAG_HOST" \
RAG_PORT="$RAG_PORT" \
RAG_TRANSPORT="$RAG_TRANSPORT" \
python3 - <<'PY'
import os
from pathlib import Path

manifest = Path(os.environ["MANIFEST_PATH"])
base = Path(os.environ["BASE_MANIFEST"]).read_text(encoding="utf-8")
base = base.replace(
    'endpoint: "http://127.0.0.1:6006"',
    f'endpoint: "http://{os.environ["PHOENIX_HOST"]}:{os.environ["PHOENIX_PORT"]}"',
)
base = base.replace(
    'type: sse\n    name: scratchpad_fs',
    'type: streamable-http\n    name: scratchpad_fs',
)
base = base.replace(
    'url: "http://127.0.0.1:8890/mcp"',
    f'url: "http://{os.environ["SCRATCHPAD_HOST"]}:{os.environ["SCRATCHPAD_PORT"]}{os.environ["SCRATCHPAD_PATH"]}"',
)
base = base.replace(
    'url: "http://127.0.0.1:8787/sse"',
    f'url: "http://{os.environ["RAG_HOST"]}:{os.environ["RAG_PORT"]}/{os.environ["RAG_TRANSPORT"]}"',
)
manifest.write_text(base, encoding="utf-8")
print(manifest)
PY

start_bg() {
  local name="$1"
  local command="$2"
  local log_file="$LOG_DIR/$name.log"
  local pid_file="$PID_DIR/$name.pid"

  echo "Starting $name"
  nohup bash -lc "$command" >"$log_file" 2>&1 &
  local pid=$!
  echo "$pid" >"$pid_file"
  echo "  pid=$pid"
  echo "  log=$log_file"
}

start_bg \
  phoenix \
  "cd \"$AGENTPOOL_DIR\" && PHOENIX_HOST=\"$PHOENIX_HOST\" PHOENIX_PORT=\"$PHOENIX_PORT\" UV_NO_SYNC=1 uv run --project \"$AGENTPOOL_DIR\" phoenix serve"

start_bg \
  scratchpad \
  "cd \"$SCRATCHPAD_PROJECT_DIR\" && \
   MCP_SCRATCHPAD_BASE_DIR=\"$SCRATCHPAD_RUNTIME/files\" \
   SCRATCHPAD_WORKSPACE_DIR=\"$SCRATCHPAD_RUNTIME/workspace\" \
   SCRATCHPAD_SHARED_MEMORY_USERS_DIR=\"$SCRATCHPAD_RUNTIME/shared-memory/users\" \
   SCRATCHPAD_SHARED_MEMORY_AGENTS_DIR=\"$SCRATCHPAD_RUNTIME/shared-memory/agents\" \
   SCRATCHPAD_SHARED_MEMORY_TEAMS_DIR=\"$SCRATCHPAD_RUNTIME/shared-memory/teams\" \
   SCRATCHPAD_SHARED_MEMORY_SHARED_DIR=\"$SCRATCHPAD_RUNTIME/shared-memory/shared\" \
   \"$SCRATCHPAD_PROJECT_DIR/.venv/bin/python\" -m mcp_scratchpad.server -c \"$SCRATCHPAD_PROJECT_DIR/src/mcp_scratchpad/yaml/scratchpad.yaml\" --transport streamable-http --host \"$SCRATCHPAD_HOST\" --port \"$SCRATCHPAD_PORT\" --path \"$SCRATCHPAD_PATH\""

start_bg \
  rag_mcp \
  "cd \"$RAG_DIR\" && \
   set -a && source \"$RAG_DIR/.env\" && set +a && \
   MCP_TRANSPORT=\"$RAG_TRANSPORT\" HTTP_HOST=\"$RAG_HOST\" HTTP_PORT=\"$RAG_PORT\" UV_NO_SYNC=1 \
   uv run --project \"$RAG_DIR\" python \"$RAG_DIR/main.py\""

start_bg \
  xeno_opencode \
  "cd \"$XENO_DIR/config\" && \
   set -a && source \"$XENO_DIR/.envrc\" >/dev/null 2>&1 && set +a && \
   UV_NO_SYNC=1 \
   uv run --project \"$XENO_DIR\" agentpool serve-opencode \"$MANIFEST_PATH\" --host \"$OPENCODE_HOST\" --port \"$OPENCODE_PORT\""

cat <<EOF

Local stack started.

Phoenix:
  http://$PHOENIX_HOST:$PHOENIX_PORT

Scratchpad MCP:
  transport=streamable-http
  endpoint=http://$SCRATCHPAD_HOST:$SCRATCHPAD_PORT$SCRATCHPAD_PATH

RAG MCP:
  transport=$RAG_TRANSPORT
  endpoint=http://$RAG_HOST:$RAG_PORT/$RAG_TRANSPORT

Xeno OpenCode:
  http://$OPENCODE_HOST:$OPENCODE_PORT

Generated manifest:
  $MANIFEST_PATH

Runtime root:
  $RUNTIME_ROOT

Logs:
  $LOG_DIR

PID files:
  $PID_DIR

To stop:
  kill \$(cat "$PID_DIR"/*.pid)
EOF
