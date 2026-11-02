"""Checks an installed package, outside pytest. CI runs it against the built wheel.

Usage: python tests/smoke_installed.py EXPECTED_VERSION
"""

import sys
import json
import threading
import subprocess
from pathlib import Path


MCP_TOOLS = {"analyze_behavior", "detect_deepfake", "get_result", "list_processes"}
MCP_TIMEOUT_SECONDS = 60
INITIALIZE_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "smoke-test", "version": "0"},
}


def check_imports(expected_version):
    import behavioralsignals
    from behavioralsignals import Client  # noqa: F401
    from behavioralsignals.generated import api_pb2, api_pb2_grpc  # noqa: F401

    location = behavioralsignals.__file__
    assert "site-packages" in location, f"not the installed package: {location}"
    assert behavioralsignals.__version__ == expected_version, behavioralsignals.__version__


def send(server, message):
    server.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
    server.stdin.flush()


def receive(server, request_id):
    line = server.stdout.readline()
    assert line, "the MCP server closed stdout or timed out"
    response = json.loads(line)
    assert response.get("id") == request_id, response
    assert "result" in response, response
    return response["result"]


def list_mcp_tools(server):
    send(server, {"id": 1, "method": "initialize", "params": INITIALIZE_PARAMS})
    receive(server, 1)
    send(server, {"method": "notifications/initialized"})
    send(server, {"id": 2, "method": "tools/list"})
    return {tool["name"] for tool in receive(server, 2)["tools"]}


def check_mcp_server():
    command = Path(sys.executable).parent / "behavioralsignals-mcp"
    with subprocess.Popen(
        [command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as server:
        # A server that hangs would block the reads forever: killing it ends them.
        timer = threading.Timer(MCP_TIMEOUT_SECONDS, server.kill)
        timer.start()
        try:
            tools = list_mcp_tools(server)
            server.stdin.close()
            extra_output = server.stdout.read()
            exit_code = server.wait()
        finally:
            timer.cancel()
            server.kill()
    assert tools == MCP_TOOLS, tools
    assert not extra_output, f"the MCP server wrote to stdout: {extra_output}"
    assert exit_code == 0, f"the MCP server exited with {exit_code}"


if __name__ == "__main__":
    check_imports(sys.argv[1])
    check_mcp_server()
    print("Installed package OK")
