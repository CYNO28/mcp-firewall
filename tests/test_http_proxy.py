"""Unit tests for HTTP/SSE Proxy."""

import json
import threading
import time
import urllib.request
from unittest.mock import MagicMock

from mcp_firewall.interceptors.http_proxy import HTTPProxyServer, MCPProxyRequestHandler
from mcp_firewall.models import ApprovalDecision, RequestStatus


def test_http_proxy_health_check():
    test_port = 18765
    proxy = HTTPProxyServer(host="127.0.0.1", port=test_port)

    thread = threading.Thread(target=lambda: proxy.start(blocking=True), daemon=True)
    thread.start()
    time.sleep(0.5)

    try:
        url = f"http://127.0.0.1:{test_port}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data.get("status") == "ok"
    finally:
        proxy.stop()


def test_http_proxy_block_tool_call():
    test_port = 18766
    proxy = HTTPProxyServer(host="127.0.0.1", port=test_port)

    # Mock IPC client to return BLOCKED
    mock_client = MagicMock()
    mock_client.request_approval.return_value = ApprovalDecision(
        request_id="http-block-1",
        status=RequestStatus.BLOCKED,
        reason="Blocked by policy",
    )
    MCPProxyRequestHandler.ipc_client = mock_client

    thread = threading.Thread(target=lambda: proxy.start(blocking=True), daemon=True)
    thread.start()
    time.sleep(0.5)

    try:
        url = f"http://127.0.0.1:{test_port}/message"
        payload = {
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {"name": "rm_rf", "arguments": {}},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["id"] == 101
            assert data["result"]["isError"] is True
            assert "Blocked by policy" in data["result"]["content"][0]["text"]
    finally:
        proxy.stop()
