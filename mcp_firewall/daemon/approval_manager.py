import json
import threading
from typing import Callable, Dict, List, Optional

from mcp_firewall.config import AUDIT_LOG_FILE
from mcp_firewall.models import MCPRequest, ApprovalDecision, RequestStatus


class PendingItem:
    def __init__(self, request: MCPRequest):
        self.request = request
        self.decision: Optional[ApprovalDecision] = None
        self.event = threading.Event()


class ApprovalManager:
    def __init__(
        self,
        on_request_queued: Optional[Callable[[MCPRequest], None]] = None,
        on_decision_rendered: Optional[Callable[[ApprovalDecision], None]] = None,
    ):
        self.on_request_queued = on_request_queued
        self.on_decision_rendered = on_decision_rendered
        self._lock = threading.Lock()
        self._pending: Dict[str, PendingItem] = {}
        self._history: List[MCPRequest] = []
        self._load_recent_history()

    def set_queue_callback(self, callback: Callable[[MCPRequest], None]):
        self.on_request_queued = callback

    def set_decision_callback(self, callback: Callable[[ApprovalDecision], None]):
        self.on_decision_rendered = callback

    def _load_recent_history(self):
        if not AUDIT_LOG_FILE.exists():
            return
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()[-100:]
                for line in lines:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._history.append(MCPRequest.from_dict(data))
        except Exception:
            pass

    def _append_audit_log(self, request: MCPRequest):
        try:
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(request.to_dict()) + "\n")
        except Exception:
            pass

    def submit_request(self, request: MCPRequest, timeout: float = 60.0) -> ApprovalDecision:
        with self._lock:
            for past_req in reversed(self._history[-10:]):
                if (
                    past_req.server_name == request.server_name
                    and past_req.tool_name == request.tool_name
                    and past_req.arguments == request.arguments
                    and past_req.status in (RequestStatus.BLOCKED, RequestStatus.TIMEOUT)
                    and (request.timestamp - past_req.timestamp) < 10.0
                ):
                    decision = ApprovalDecision(
                        request_id=request.request_id,
                        status=RequestStatus.BLOCKED,
                        reason="Auto-blocked by recent rejection policy.",
                    )
                    request.status = RequestStatus.BLOCKED
                    request.decision_reason = decision.reason
                    self._history.append(request)
                    if self.on_decision_rendered:
                        self.on_decision_rendered(decision)
                    self._append_audit_log(request)
                    return decision

        item = PendingItem(request)

        with self._lock:
            self._pending[request.request_id] = item

        if self.on_request_queued:
            self.on_request_queued(request)

        wait_time = timeout if timeout > 0 else None
        signaled = item.event.wait(timeout=wait_time)

        with self._lock:
            self._pending.pop(request.request_id, None)

        if not signaled or not item.decision:
            decision = ApprovalDecision(
                request_id=request.request_id,
                status=RequestStatus.TIMEOUT,
                reason=f"Timed out after {timeout} seconds without user decision.",
            )
            request.status = RequestStatus.TIMEOUT
            request.decision_reason = decision.reason
            if self.on_decision_rendered:
                self.on_decision_rendered(decision)
        else:
            decision = item.decision
            request.status = decision.status
            request.decision_reason = decision.reason

        with self._lock:
            self._history.append(request)

        self._append_audit_log(request)
        return decision

    def resolve_decision(self, decision: ApprovalDecision):
        with self._lock:
            item = self._pending.get(decision.request_id)
            if item:
                item.decision = decision
                item.event.set()
        if self.on_decision_rendered:
            self.on_decision_rendered(decision)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            total = len(self._history)
            allowed = sum(1 for r in self._history if r.status == RequestStatus.ALLOWED)
            blocked = sum(1 for r in self._history if r.status in (RequestStatus.BLOCKED, RequestStatus.TIMEOUT))
            return {
                "total": total,
                "allowed": allowed,
                "blocked": blocked,
                "pending": len(self._pending),
            }

    def get_history(self) -> List[MCPRequest]:
        with self._lock:
            return list(self._history)
