"""Unit and integration tests for Stdio Interceptor."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_firewall.interceptors.stdio_wrapper import StdioInterceptor
from mcp_firewall.models import ApprovalDecision, RequestStatus


def test_stdio_handle_tool_call_allowed():
    interceptor = StdioInterceptor(
        server_name="test_fs",
        target_command=[sys.executable, "-c", "print('hello')"],
        timeout=10,
    )
    interceptor.client = MagicMock()
    interceptor.client.request_approval.return_value = ApprovalDecision(
        request_id="test-1",
        status=RequestStatus.ALLOWED,
        reason="OK",
    )

    interceptor._send_to_target = MagicMock()
    interceptor._send_to_client = MagicMock()

    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "read_file", "arguments": {"path": "a.txt"}},
    }
    raw_line = json.dumps(msg) + "\n"

    interceptor._handle_tool_call(msg, raw_line)

    # Should forward to target
    interceptor._send_to_target.assert_called_once_with(raw_line)
    interceptor._send_to_client.assert_not_called()


def test_stdio_handle_tool_call_blocked():
    interceptor = StdioInterceptor(
        server_name="test_fs",
        target_command=[sys.executable, "-c", "print('hello')"],
        timeout=10,
    )
    interceptor.client = MagicMock()
    interceptor.client.request_approval.return_value = ApprovalDecision(
        request_id="test-2",
        status=RequestStatus.BLOCKED,
        reason="Permission denied by user",
    )

    interceptor._send_to_target = MagicMock()
    interceptor._send_to_client = MagicMock()

    msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "delete_file", "arguments": {"path": "a.txt"}},
    }
    raw_line = json.dumps(msg) + "\n"

    interceptor._handle_tool_call(msg, raw_line)

    # Must NOT send to target
    interceptor._send_to_target.assert_not_called()

    # Must send block response to client
    interceptor._send_to_client.assert_called_once()
    sent_text = interceptor._send_to_client.call_args[0][0]
    sent_json = json.loads(sent_text)
    assert sent_json["id"] == 2
    assert sent_json["result"]["isError"] is True
    assert "Permission denied by user" in sent_json["result"]["content"][0]["text"]
