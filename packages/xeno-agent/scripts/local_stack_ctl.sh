# 确保 manifest 文件已生成
python3 -c "
import os
from pathlib import Path

manifest = Path(os.environ.get('MANIFEST_PATH', '$RUNTIME_ROOT/diag-agent-v5.local.yaml'))
base = Path('$BASE_MANIFEST').read_text()
# 替换端点配置...
manifest.write_text(base)
"

# 启动 Agent
cd "$XENO_DIR"
UV_NO_SYNC=1 uv run --project "$XENO_DIR" agentpool serve-opencode "$MANIFEST_PATH" --host 127.0.0.1 --port 7163
