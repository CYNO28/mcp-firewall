"""HTTP and Server-Sent Events (SSE) Reverse Proxy for Claude Web MCP communication."""

import json
import logging
import socketserver
import urllib.request
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from mcp_firewall.config import (
    DEFAULT_HTTP_PROXY_HOST,
    DEFAULT_HTTP_PROXY_PORT,
    DEFAULT_REQUEST_TIMEOUT,
)
from mcp_firewall.daemon.ipc_client import IPCClient
from mcp_firewall.models import MCPRequest, ClientType, RequestStatus
from mcp_firewall.protocol import (
    parse_jsonrpc,
    is_tool_call,
    extract_tool_call_details,
    create_block_response,
)

logger = logging.getLogger("mcp_firewall.http_proxy")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for handling concurrent Claude Web requests."""
    daemon_threads = True


class MCPProxyRequestHandler(BaseHTTPRequestHandler):
    """Handles and intercepts HTTP/SSE requests from Claude Web."""

    ipc_client: IPCClient = IPCClient()
    upstream_url: Optional[str] = None
    server_name: str = "claude-web-gateway"
    timeout: int = DEFAULT_REQUEST_TIMEOUT

    def log_message(self, format, *args):
        # Override to keep terminal clean unless debugging
        logger.debug(f"{self.address_string()} - {format % args}")

    def do_OPTIONS(self):
        """Handle CORS preflight requests from browser/web clients."""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def do_GET(self):
        """Handle SSE stream connection or health check."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok", "service": "mcp-firewall-http-proxy"}\n')
            return

        if not self.upstream_url:
            # Standalone mode: Provide a standard MCP SSE announcement endpoint
            if parsed.path in ("/sse", "/"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._send_cors_headers()
                self.end_headers()

                # Tell client where to POST messages
                endpoint_event = "event: endpoint\ndata: /message\n\n"
                self.wfile.write(endpoint_event.encode("utf-8"))
                self.wfile.flush()
                return

            self.send_error(404, "Not Found")
            return

        # Upstream proxy mode: Relay GET request to upstream server (e.g. /sse)
        target = urllib.parse.urljoin(self.upstream_url, self.path)
        try:
            req = urllib.request.Request(target, headers={k: v for k, v in self.headers.items() if k.lower() != "host"})
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for header, val in resp.getheaders():
                    self.send_header(header, val)
                self._send_cors_headers()
                self.end_headers()

                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception as e:
            self.send_error(502, f"Bad Gateway: {e}")

    def do_POST(self):
        """Intercept outgoing MCP JSON-RPC requests from Claude Web."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8", errors="replace")

        message = parse_jsonrpc(body)

        if message and is_tool_call(message):
            # Intercept tool call!
            tool_name, arguments, raw_id = extract_tool_call_details(message)

            mcp_req = MCPRequest(
                server_name=self.server_name,
                tool_name=tool_name,
                arguments=arguments,
                client_type=ClientType.CLAUDE_WEB_HTTP,
                raw_id=raw_id,
                origin_ip=self.client_address[0],
            )

            decision = self.ipc_client.request_approval(mcp_req, timeout=float(self.timeout))

            if decision.status != RequestStatus.ALLOWED:
                # Block! Synthesize MCP response
                block_resp = create_block_response(
                    raw_id=raw_id,
                    tool_name=tool_name,
                    reason=decision.reason,
                )
                resp_bytes = json.dumps(block_resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(resp_bytes)
                return

        # If allowed and upstream URL is configured, forward to upstream MCP server
        if self.upstream_url:
            target = urllib.parse.urljoin(self.upstream_url, self.path)
            try:
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
                headers["Content-Type"] = "application/json"
                req = urllib.request.Request(target, data=body.encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req) as resp:
                    resp_body = resp.read()
                    self.send_response(resp.status)
                    for h, val in resp.getheaders():
                        if h.lower() != "content-length":
                            self.send_header(h, val)
                    self.send_header("Content-Length", str(len(resp_body)))
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(resp_body)
                return
            except Exception as e:
                self.send_error(502, f"Bad Gateway forwarding to upstream MCP: {e}")
                return

        # Standalone mock response if no upstream is connected (for test harness)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        success_resp = {
            "jsonrpc": "2.0",
            "id": message.get("id") if message else 1,
            "result": {
                "content": [{"type": "text", "text": "Tool executed successfully (allowed by user)."}],
                "isError": False,
            },
        }
        self.wfile.write(json.dumps(success_resp).encode("utf-8"))


class HTTPProxyServer:
    """Wrapper to run the HTTP/SSE proxy server."""

    def __init__(
        self,
        host: str = DEFAULT_HTTP_PROXY_HOST,
        port: int = DEFAULT_HTTP_PROXY_PORT,
        upstream_url: Optional[str] = None,
        server_name: str = "claude-web-gateway",
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.server: Optional[ThreadedHTTPServer] = None

        # Configure handler class attributes
        MCPProxyRequestHandler.upstream_url = upstream_url
        MCPProxyRequestHandler.server_name = server_name
        MCPProxyRequestHandler.timeout = timeout

    def start(self, blocking: bool = True):
        self.server = ThreadedHTTPServer((self.host, self.port), MCPProxyRequestHandler)
        logger.info(f"MCP HTTP/SSE Proxy running at http://{self.host}:{self.port}")
        if blocking:
            try:
                self.server.serve_forever()
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
