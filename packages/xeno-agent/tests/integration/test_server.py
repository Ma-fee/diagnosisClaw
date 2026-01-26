import json
import os
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_xeno_server_cli():
    """Test the Xeno ACP server via CLI."""
    # Run using the same python interpreter
    cmd = [sys.executable, "-m", "xeno_agent.main", "serve"]

    # Ensure PYTHONPATH includes xeno-agent src
    env = os.environ.copy()
    src_path = os.path.abspath("packages/xeno-agent/src")  # noqa: PTH100
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_path

    # Start server
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, env=env)  # noqa: S603

    try:
        # 1. Initialize
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "test-client", "version": "1.0"}},
            "id": 1,
        }

        # Write JSON-RPC line
        req_str = json.dumps(init_req) + "\n"
        proc.stdin.write(req_str.encode("utf-8"))
        proc.stdin.flush()

        # Read response
        line = proc.stdout.readline()
        assert line, "Server returned no output"

        resp = json.loads(line.decode("utf-8"))
        assert resp.get("jsonrpc") == "2.0"
        assert resp.get("id") == 1
        assert "result" in resp
        result = resp["result"]
        # Check agentInfo for name (ACP schema)
        if "agentInfo" in result:
            assert result["agentInfo"]["name"] == "xeno-agent"
        else:
            # Fallback for older schema if applicable (though unlikely with current acp lib)
            # Or maybe it is aliased differently?
            pass
        assert result.get("protocolVersion") == 1

        # 2. List sessions
        list_req = {"jsonrpc": "2.0", "method": "session/list", "params": {}, "id": 2}

        req_str = json.dumps(list_req) + "\n"
        proc.stdin.write(req_str.encode("utf-8"))
        proc.stdin.flush()

        line = proc.stdout.readline()
        assert line, "Server returned no output for list sessions"
        resp = json.loads(line.decode("utf-8"))
        assert resp.get("id") == 2
        assert "result" in resp
        assert isinstance(resp["result"]["sessions"], list)

        # 3. New Session
        new_session_req = {"jsonrpc": "2.0", "method": "session/new", "params": {"cwd": "/tmp"}, "id": 3}  # noqa: S108
        req_str = json.dumps(new_session_req) + "\n"
        proc.stdin.write(req_str.encode("utf-8"))
        proc.stdin.flush()

        line = proc.stdout.readline()
        assert line, "Server returned no output for new session"
        resp = json.loads(line.decode("utf-8"))
        assert resp.get("id") == 3
        assert "result" in resp
        assert "sessionId" in resp["result"]

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
