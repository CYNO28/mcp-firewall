"""Simulates Claude Desktop invoking tools on an MCP server."""

import json
import subprocess
import sys
import time
from typing import Any, Dict, Optional


class MockClaudeDesktop:
    """Spawns an MCP server (wrapped or raw) and sends JSON-RPC tool calls."""

    def __init__(self, command: list):
        self.command = command
        self.proc: Optional[subprocess.Popen] = None
        self.request_id = 1

    def start(self):
        self.proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding="utf-8",
        )
        # Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Claude Desktop Simulator", "version": "1.0"},
            },
        }
        self.send_raw(init_req)
        init_resp = self.read_response()
        return init_resp

    def _next_id(self) -> int:
        req_id = self.request_id
        self.request_id += 1
        return req_id

    def send_raw(self, data: dict):
        line = json.dumps(data) + "\n"
        self.proc.stdin.write(line)
        self.proc.stdin.flush()

    def read_response(self) -> dict:
        line = self.proc.stdout.readline()
        if not line:
            return {}
        try:
            return json.loads(line.strip())
        except Exception:
            return {"raw": line}

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> dict:
        req_id = self._next_id()
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        self.send_raw(req)
        return self.read_response()

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
