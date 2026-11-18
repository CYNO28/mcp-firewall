"""IPC Client for communicating with the MCP Firewall Daemon."""

import json
import logging
import socket
import subprocess
import sys
import time
from typing import Optional

from mcp_firewall.config import DEFAULT_IPC_HOST, DEFAULT_IPC_PORT
from mcp_firewall.models import MCPRequest, ApprovalDecision, RequestStatus
from mcp_firewall.ui.popup import run_standalone_dialog

logger = logging.getLogger("mcp_firewall.ipc_client")


class IPCClient:
    """Client used by stdio wrapper and HTTP proxy to request authorization."""

    def __init__(self, host: str = DEFAULT_IPC_HOST, port: int = DEFAULT_IPC_PORT):
        self.host = host
        self.port = port

    def is_daemon_running(self) -> bool:
        """Check if daemon is reachable and responding."""
        try:
            with socket.create_connection((self.host, self.port), timeout=1.0) as sock:
                sock.sendall(b'{"cmd": "PING"}\n')
                file_obj = sock.makefile("r", encoding="utf-8")
                line = file_obj.readline()
                if line:
                    data = json.loads(line.strip())
                    return data.get("status") == "PONG"
        except Exception:
            return False
        return False

    def auto_spawn_daemon(self) -> bool:
        """Attempt to spawn daemon in the background if not running."""
        try:
            # Launch daemon using the current python executable
            cmd = [sys.executable, "-m", "mcp_firewall", "daemon", "--background"]
            subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True if sys.platform != "win32" else False,
            )
            # Give daemon up to 3 seconds to spin up
            for _ in range(30):
                time.sleep(0.1)
                if self.is_daemon_running():
                    return True
        except Exception as e:
            logger.warning(f"Could not auto-spawn daemon: {e}")
        return False

    def request_approval(self, request: MCPRequest, timeout: float = 60.0) -> ApprovalDecision:
        """
        Request user approval for an MCP request.
        Communicates with daemon or falls back to an embedded dialog.
        """
        # Ensure daemon is running
        if not self.is_daemon_running():
            self.auto_spawn_daemon()

        # Try IPC connection
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout + 5.0) as sock:
                payload = {
                    "cmd": "SUBMIT",
                    "request": request.to_dict(),
                    "timeout": timeout,
                }
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

                file_obj = sock.makefile("r", encoding="utf-8")
                line = file_obj.readline()
                if line:
                    resp = json.loads(line.strip())
                    if resp.get("status") == "DECISION":
                        return ApprovalDecision.from_dict(resp["decision"])
        except Exception as e:
            logger.warning(f"IPC communication error ({e}). Falling back to standalone modal.")

        # Fallback to standalone dialog
        try:
            return run_standalone_dialog(request, timeout=int(timeout))
        except Exception as e:
            logger.error(f"Fallback dialog failed: {e}. Defaulting to BLOCK for safety.")
            return ApprovalDecision(
                request_id=request.request_id,
                status=RequestStatus.BLOCKED,
                reason=f"Failed to display confirmation modal: {e}",
            )
