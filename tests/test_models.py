"""Unit tests for data models."""

from mcp_firewall.models import (
    MCPRequest,
    ApprovalDecision,
    RequestStatus,
    ClientType,
)


def test_mcp_request_serialization():
    req = MCPRequest(
        server_name="filesystem",
        tool_name="read_file",
        arguments={"path": "test.txt"},
        client_type=ClientType.CLAUDE_DESKTOP_STDIO,
        raw_id=1,
    )
    d = req.to_dict()
    assert d["server_name"] == "filesystem"
    assert d["tool_name"] == "read_file"
    assert d["status"] == "PENDING"
    assert d["client_type"] == "Claude Desktop (stdio)"

    restored = MCPRequest.from_dict(d)
    assert restored.server_name == req.server_name
    assert restored.tool_name == req.tool_name
    assert restored.status == RequestStatus.PENDING
    assert restored.client_type == ClientType.CLAUDE_DESKTOP_STDIO


def test_approval_decision_serialization():
    decision = ApprovalDecision(
        request_id="req-12345",
        status=RequestStatus.ALLOWED,
        reason="Approved by user",
    )
    d = decision.to_dict()
    assert d["request_id"] == "req-12345"
    assert d["status"] == "ALLOWED"

    restored = ApprovalDecision.from_dict(d)
    assert restored.request_id == "req-12345"
    assert restored.status == RequestStatus.ALLOWED
