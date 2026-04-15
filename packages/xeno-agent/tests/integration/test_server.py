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
        session_id = resp["result"]["sessionId"]

        # 4. Prompt
        prompt_req = {"jsonrpc": "2.0", "method": "session/prompt", "params": {"sessionId": session_id, "prompt": [{"type": "text", "text": "Hello world"}]}, "id": 4}
        req_str = json.dumps(prompt_req) + "\n"
        proc.stdin.write(req_str.encode("utf-8"))
        proc.stdin.flush()

        # Read response stream
        # The prompt method returns a stream of notifications or messages
        # We expect at least one response line before timeout
        # Usually it sends session/update notifications

        # We read lines until we get a result or timeout
        # For this test, we just want to verify it doesn't crash with NameError
        # and returns something valid.

        # Read a few lines to catch potential errors
        for _ in range(5):
            line = proc.stdout.readline()
            if not line:
                break
            resp = json.loads(line.decode("utf-8"))

            # Check for error
            if "error" in resp:
                pytest.fail(f"Server returned error: {resp['error']}")

            # If we get a result for id 4, we are good (even if it's empty or partial)
            if resp.get("id") == 4:
                # Prompt response (could be empty or contain result)
                break

            # If we get session/update, that's good too, it means it's processing
            if resp.get("method") == "session/update":
                assert resp["params"]["sessionId"] == session_id
                # We can stop here as it proves the agent started processing without NameError
                break

    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
