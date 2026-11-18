"""Simulates Claude Web interacting with an MCP server via HTTP/SSE."""

import json
import urllib.request
import urllib.parse
from typing import Any, Dict


class MockClaudeWeb:
    """Sends JSON-RPC requests via HTTP/SSE to simulate Claude Web client."""

    def __init__(self, proxy_url: str = "http://127.0.0.1:8765"):
        self.proxy_url = proxy_url
        self.request_id = 1

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> dict:
        req_id = self.request_id
        self.request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        endpoint = f"{self.proxy_url}/message"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Claude-Web-Simulator/1.0",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
