"""Unit tests for JSON-RPC 2.0 and MCP protocol handling."""

import json
from mcp_firewall.protocol import (
    parse_jsonrpc,
    is_tool_call,
    extract_tool_call_details,
    create_block_response,
    serialize_jsonrpc,
)


def test_parse_jsonrpc_valid():
    raw = '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "test_tool", "arguments": {"x": 10}}}'
    msg = parse_jsonrpc(raw)
    assert msg is not None
    assert msg["id"] == 1
    assert msg["method"] == "tools/call"


def test_parse_jsonrpc_invalid():
    assert parse_jsonrpc("") is None
    assert parse_jsonrpc("not a json") is None
    assert parse_jsonrpc('{"not_jsonrpc": true}') is None


def test_is_tool_call():
    assert is_tool_call({"method": "tools/call"}) is True
    assert is_tool_call({"method": "tools/list"}) is False
    assert is_tool_call({"method": "initialize"}) is False


def test_extract_tool_call_details():
    msg = {
        "jsonrpc": "2.0",
        "id": "abc-123",
        "method": "tools/call",
        "params": {
            "name": "delete_database",
            "arguments": {"database": "prod", "drop": True},
        },
    }
    tool_name, arguments, raw_id = extract_tool_call_details(msg)
    assert tool_name == "delete_database"
    assert arguments == {"database": "prod", "drop": True}
    assert raw_id == "abc-123"


def test_create_block_response_mcp_format():
    resp = create_block_response(
        raw_id=42,
        tool_name="delete_database",
        reason="Security policy violation",
    )
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 42
    assert "result" in resp
    assert resp["result"]["isError"] is True
    assert len(resp["result"]["content"]) > 0
    text = resp["result"]["content"][0]["text"]
    assert "delete_database" in text
    assert "Security policy violation" in text


def test_create_block_response_protocol_error():
    resp = create_block_response(
        raw_id=99,
        tool_name="shell_exec",
        reason="Denied by user",
        use_protocol_error=True,
    )
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 99
    assert "error" in resp
    assert resp["error"]["code"] == -32000
    assert "shell_exec" in resp["error"]["message"]


def test_serialize_jsonrpc():
    msg = {"jsonrpc": "2.0", "id": 1, "result": "ok"}
    serialized = serialize_jsonrpc(msg)
    assert serialized.endswith("\n")
    assert json.loads(serialized)["result"] == "ok"
