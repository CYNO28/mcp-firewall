import json
import logging
import socket
import sys
import threading
from typing import Optional

from mcp_firewall.config import DEFAULT_IPC_HOST, DEFAULT_IPC_PORT
from mcp_firewall.daemon.approval_manager import ApprovalManager
from mcp_firewall.models import MCPRequest

logger = logging.getLogger("mcp_firewall.ipc_server")


class IPCServer:
    def __init__(
        self,
        approval_manager: ApprovalManager,
        host: str = DEFAULT_IPC_HOST,
        port: int = DEFAULT_IPC_PORT,
    ):
        self.approval_manager = approval_manager
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform != "win32":
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(50)
        self._running = True

        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="IPCServer-AcceptLoop")
        self._thread.start()
        logger.info(f"IPC Server listening on {self.host}:{self.port}")

    def stop(self):
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self._running:
            try:
                client_sock, addr = self.sock.accept()
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr),
                    daemon=True,
                    name=f"IPCClient-{addr}",
                )
                client_thread.start()
            except Exception:
                if not self._running:
                    break

    def _handle_client(self, client_sock: socket.socket, addr):
        try:
            client_sock.settimeout(120.0)
            file_obj = client_sock.makefile("r", encoding="utf-8")
            line = file_obj.readline()
            if not line:
                return

            payload = json.loads(line.strip())
            cmd = payload.get("cmd")

            if cmd == "PING":
                resp = {"status": "PONG", "version": "1.0.0"}
                client_sock.sendall((json.dumps(resp) + "\n").encode("utf-8"))

            elif cmd == "SUBMIT":
                req_data = payload.get("request", {})
                timeout = float(payload.get("timeout", 60.0))
                req = MCPRequest.from_dict(req_data)

                decision = self.approval_manager.submit_request(req, timeout=timeout)
                resp = {"status": "DECISION", "decision": decision.to_dict()}
                client_sock.sendall((json.dumps(resp) + "\n").encode("utf-8"))

            elif cmd == "GET_STATS":
                stats = self.approval_manager.get_stats()
                resp = {"status": "SUCCESS", "stats": stats}
                client_sock.sendall((json.dumps(resp) + "\n").encode("utf-8"))

            elif cmd == "SHUTDOWN":
                resp = {"status": "SHUTTING_DOWN"}
                client_sock.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                self.stop()

            else:
                resp = {"status": "ERROR", "message": f"Unknown command: {cmd}"}
                client_sock.sendall((json.dumps(resp) + "\n").encode("utf-8"))

        except Exception as e:
            logger.debug(f"IPC connection handling exception: {e}")
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
