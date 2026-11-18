"""Stdio Interceptor Wrapper for Claude Desktop MCP servers."""

import os
import sys
import subprocess
import threading
import logging
from typing import List

from mcp_firewall.config import DEFAULT_REQUEST_TIMEOUT
from mcp_firewall.daemon.ipc_client import IPCClient
from mcp_firewall.models import MCPRequest, ClientType, RequestStatus
from mcp_firewall.protocol import (
    parse_jsonrpc,
    is_tool_call,
    extract_tool_call_details,
    create_block_response,
    serialize_jsonrpc,
)

logger = logging.getLogger("mcp_firewall.stdio_wrapper")


class StdioInterceptor:
    """
    Transparent bidirectional proxy wrapping an MCP server's stdio streams.
    Intercepts tools/call messages from Claude Desktop and requires user confirmation.
    """

    def __init__(
        self,
        server_name: str,
        target_command: List[str],
        timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.server_name = server_name
        self.target_command = target_command
        self.timeout = timeout
        self.client = IPCClient()
        self.target_proc: subprocess.Popen = None
        self._running = True

    def start(self):
        """Start the target MCP server and run the interception loops."""
        try:
            self.target_proc = subprocess.Popen(
                self.target_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line-buffered
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            sys.stderr.write(f"[MCP-Firewall] Failed to spawn target server {self.target_command}: {e}\n")
            sys.stderr.flush()
            sys.exit(1)

        # Thread to read target stdout and forward to sys.stdout
        stdout_thread = threading.Thread(
            target=self._forward_target_stdout,
            daemon=True,
            name="ForwardTargetStdout",
        )
        stdout_thread.start()

        # Thread to forward target stderr to sys.stderr
        stderr_thread = threading.Thread(
            target=self._forward_target_stderr,
            daemon=True,
            name="ForwardTargetStderr",
        )
        stderr_thread.start()

        # Main thread reads sys.stdin (from Claude Desktop) and intercepts
        self._read_client_stdin()

    def _read_client_stdin(self):
        """Read requests from Claude Desktop on sys.stdin."""
        try:
            for line in sys.stdin:
                if not line:
                    break

                message = parse_jsonrpc(line)
                if message and is_tool_call(message):
                    # Intercept this tool call!
                    self._handle_tool_call(message, raw_line=line)
                else:
                    # Pass-through all other protocol messages directly
                    self._send_to_target(line)

        except (KeyboardInterrupt, BrokenPipeError):
            pass
        finally:
            self._cleanup()

    def _handle_tool_call(self, message: dict, raw_line: str):
        """Evaluate and authorize a tools/call request."""
        tool_name, arguments, raw_id = extract_tool_call_details(message)

        req = MCPRequest(
            server_name=self.server_name,
            tool_name=tool_name,
            arguments=arguments,
            client_type=ClientType.CLAUDE_DESKTOP_STDIO,
            raw_id=raw_id,
        )

        decision = self.client.request_approval(req, timeout=float(self.timeout))

        if decision.status == RequestStatus.ALLOWED:
            # Release and forward to actual MCP server
            self._send_to_target(raw_line)
        else:
            # Block! Do NOT send to target server.
            # Synthesize an MCP error result so Claude knows it was rejected.
            block_resp = create_block_response(
                raw_id=raw_id,
                tool_name=tool_name,
                reason=decision.reason,
            )
            self._send_to_client(serialize_jsonrpc(block_resp))

    def _send_to_target(self, text: str):
        """Send message to target MCP server's stdin."""
        if self.target_proc and self.target_proc.stdin:
            try:
                self.target_proc.stdin.write(text)
                self.target_proc.stdin.flush()
            except Exception as e:
                logger.error(f"Error writing to target stdin: {e}")

    def _send_to_client(self, text: str):
        """Send message back to Claude Desktop's stdout."""
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error writing to client stdout: {e}")

    def _forward_target_stdout(self):
        """Forward all output from MCP server to Claude Desktop."""
        try:
            for line in self.target_proc.stdout:
                if not line:
                    break
                self._send_to_client(line)
        except Exception:
            pass

    def _forward_target_stderr(self):
        """Forward MCP server stderr logs to Claude Desktop stderr."""
        try:
            for line in self.target_proc.stderr:
                if not line:
                    break
                sys.stderr.write(line)
                sys.stderr.flush()
        except Exception:
            pass

    def _cleanup(self):
        """Terminate target server on exit."""
        self._running = False
        if self.target_proc:
            try:
                self.target_proc.terminate()
                self.target_proc.wait(timeout=2)
            except Exception:
                try:
                    self.target_proc.kill()
                except Exception:
                    pass
