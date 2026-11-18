"""Unit tests for ApprovalManager concurrency and decision lifecycle."""

import threading
import time
from mcp_firewall.daemon.approval_manager import ApprovalManager
from mcp_firewall.models import MCPRequest, ApprovalDecision, RequestStatus


def test_submit_and_resolve_allowed():
    manager = ApprovalManager()
    req = MCPRequest(server_name="test_srv", tool_name="safe_tool", arguments={"a": 1})

    def auto_approve():
        time.sleep(0.1)
        decision = ApprovalDecision(request_id=req.request_id, status=RequestStatus.ALLOWED, reason="Approved in test")
        manager.resolve_decision(decision)

    t = threading.Thread(target=auto_approve)
    t.start()

    res = manager.submit_request(req, timeout=2.0)
    t.join()

    assert res.status == RequestStatus.ALLOWED
    assert res.request_id == req.request_id
    assert req.status == RequestStatus.ALLOWED


def test_submit_and_resolve_blocked():
    manager = ApprovalManager()
    req = MCPRequest(server_name="test_srv", tool_name="danger_tool", arguments={"drop": True})

    def auto_block():
        time.sleep(0.1)
        decision = ApprovalDecision(request_id=req.request_id, status=RequestStatus.BLOCKED, reason="Blocked in test")
        manager.resolve_decision(decision)

    t = threading.Thread(target=auto_block)
    t.start()

    res = manager.submit_request(req, timeout=2.0)
    t.join()

    assert res.status == RequestStatus.BLOCKED
    assert req.status == RequestStatus.BLOCKED


def test_submit_timeout():
    manager = ApprovalManager()
    req = MCPRequest(server_name="test_srv", tool_name="timeout_tool")

    # No one approves, wait for timeout of 0.2s
    start = time.time()
    res = manager.submit_request(req, timeout=0.2)
    elapsed = time.time() - start

    assert res.status == RequestStatus.TIMEOUT
    assert req.status == RequestStatus.TIMEOUT
    assert elapsed >= 0.15


def test_concurrent_requests():
    manager = ApprovalManager()
    req1 = MCPRequest(server_name="srv1", tool_name="tool1")
    req2 = MCPRequest(server_name="srv2", tool_name="tool2")
    results = {}

    def submit1():
        results["r1"] = manager.submit_request(req1, timeout=3.0)

    def submit2():
        results["r2"] = manager.submit_request(req2, timeout=3.0)

    t1 = threading.Thread(target=submit1)
    t2 = threading.Thread(target=submit2)
    t1.start()
    t2.start()

    time.sleep(0.1)
    manager.resolve_decision(ApprovalDecision(request_id=req1.request_id, status=RequestStatus.ALLOWED))
    manager.resolve_decision(ApprovalDecision(request_id=req2.request_id, status=RequestStatus.BLOCKED))

    t1.join()
    t2.join()

    assert results["r1"].status == RequestStatus.ALLOWED
    assert results["r2"].status == RequestStatus.BLOCKED
