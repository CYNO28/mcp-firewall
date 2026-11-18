"""Data models for MCP requests, decisions, and system status."""

from dataclasses import dataclass, field, asdict
from enum import Enum
import time
import uuid
from typing import Any, Dict, Optional


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class ClientType(str, Enum):
    CLAUDE_DESKTOP_STDIO = "Claude Desktop (stdio)"
    CLAUDE_WEB_HTTP = "Claude Web (HTTP/SSE)"
    CLAUDE_DESKTOP_SSE = "Claude Desktop (SSE)"
    GENERIC_MCP = "Generic MCP Client"


@dataclass
class MCPRequest:
    """Represents an intercepted MCP communication request."""
    server_name: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    client_type: ClientType = ClientType.CLAUDE_DESKTOP_STDIO
    raw_id: Any = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    status: RequestStatus = RequestStatus.PENDING
    decision_reason: Optional[str] = None
    origin_ip: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["client_type"] = self.client_type.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPRequest":
        clean = dict(data)
        if "status" in clean and isinstance(clean["status"], str):
            clean["status"] = RequestStatus(clean["status"])
        if "client_type" in clean and isinstance(clean["client_type"], str):
            clean["client_type"] = ClientType(clean["client_type"])
        return cls(**clean)


@dataclass
class ApprovalDecision:
    """Represents the user's confirmation decision for an MCP request."""
    request_id: str
    status: RequestStatus
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalDecision":
        return cls(
            request_id=data["request_id"],
            status=RequestStatus(data["status"]) if isinstance(data["status"], str) else data["status"],
            reason=data.get("reason", ""),
            timestamp=data.get("timestamp", time.time()),
        )
