"""Command Line Interface for MCP Firewall."""

import argparse
import logging
import sys
import tkinter as tk
from typing import List

from mcp_firewall.config import (
    DEFAULT_IPC_HOST,
    DEFAULT_IPC_PORT,
    DEFAULT_HTTP_PROXY_HOST,
    DEFAULT_HTTP_PROXY_PORT,
    DEFAULT_REQUEST_TIMEOUT,
)
from mcp_firewall.claude_config import ClaudeConfigManager
from mcp_firewall.daemon.approval_manager import ApprovalManager
from mcp_firewall.daemon.ipc_server import IPCServer
from mcp_firewall.interceptors.stdio_wrapper import StdioInterceptor
from mcp_firewall.interceptors.http_proxy import HTTPProxyServer
from mcp_firewall.models import MCPRequest, ApprovalDecision
from mcp_firewall.ui.popup import ConfirmationModal
from mcp_firewall.ui.dashboard import MonitoringDashboard

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s]: %(message)s")
logger = logging.getLogger("mcp_firewall")


def run_daemon_command(args):
    """Run the MCP Firewall central daemon with GUI confirmation modal."""
    logger.info("Starting MCP Firewall Central Daemon...")

    root = tk.Tk()
    manager = ApprovalManager()

    modal = ConfirmationModal(
        root=root,
        on_decision=manager.resolve_decision,
        default_timeout=args.timeout,
    )

    dashboard = None
    if getattr(args, "dashboard", False):
        dash_window = tk.Toplevel(root)
        dashboard = MonitoringDashboard(root=dash_window)

    def on_queued(request: MCPRequest):
        # Schedule UI update in Tkinter main thread
        root.after(0, lambda: modal.add_request(request))
        if dashboard:
            root.after(0, lambda: dashboard.record_request(request))

    def on_decision(decision: ApprovalDecision):
        if dashboard:
            root.after(0, lambda: dashboard.update_decision(decision.request_id, decision.status))

    manager.set_queue_callback(on_queued)
    manager.set_decision_callback(on_decision)

    # Start IPC Server
    ipc_server = IPCServer(
        approval_manager=manager,
        host=args.host,
        port=args.port,
    )
    ipc_server.start()

    logger.info(f"[ACTIVE] MCP Firewall Daemon is ACTIVE on {args.host}:{args.port}")
    logger.info("Ready to intercept Claude Desktop and Claude Web requests.")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        ipc_server.stop()
        logger.info("MCP Firewall Daemon terminated.")


def run_wrap_command(args, remaining_args: List[str]):
    """Run stdio interceptor wrapper around target MCP server."""
    if not remaining_args:
        logger.error("Error: No target command specified after '--'. Example: mcp-firewall wrap --server-name test -- python server.py")
        sys.exit(1)

    interceptor = StdioInterceptor(
        server_name=args.server_name,
        target_command=remaining_args,
        timeout=args.timeout,
    )
    interceptor.start()


def run_proxy_command(args):
    """Run the HTTP/SSE proxy for Claude Web."""
    logger.info(f"Starting MCP HTTP/SSE Proxy on {args.host}:{args.port}...")
    proxy = HTTPProxyServer(
        host=args.host,
        port=args.port,
        upstream_url=args.upstream,
        server_name=args.server_name,
        timeout=args.timeout,
    )
    try:
        proxy.start(blocking=True)
    except KeyboardInterrupt:
        proxy.stop()
        logger.info("HTTP Proxy stopped.")


def run_claude_status_command(args):
    """Check Claude Desktop configuration status."""
    mgr = ClaudeConfigManager()
    path = mgr.config_path
    print(f"\n[INFO] Claude Desktop Config Path: {path}")
    if not mgr.exists():
        print("  [WARN] Config file not found. Claude Desktop may not be configured yet.")
        return

    servers = mgr.list_servers()
    if not servers:
        print("  [INFO] No MCP servers currently configured in Claude Desktop.")
        return

    print(f"\nConfigured Servers ({len(servers)} total):")
    print("-" * 65)
    for s in servers:
        status_badge = "[PROTECTED]" if s["is_protected"] else "[UNPROTECTED]"
        print(f"  * {s['name']:<18} | {status_badge:<14} | Command: {s['command']}")
    print("-" * 65 + "\n")


def run_claude_protect_command(args):
    """Wrap configured servers with MCP Firewall in claude_desktop_config.json."""
    mgr = ClaudeConfigManager()
    if not mgr.exists():
        print(f"Error: Claude Desktop configuration not found at {mgr.config_path}")
        return

    if args.server:
        if mgr.protect_server(args.server):
            print(f"[OK] Server '{args.server}' is now protected by MCP Firewall.")
        else:
            print(f"Server '{args.server}' not found in configuration.")
    else:
        protected, total = mgr.protect_all()
        print(f"[OK] Protected {protected} of {total} servers in Claude Desktop.")


def run_claude_unprotect_command(args):
    """Restore original configuration in claude_desktop_config.json."""
    mgr = ClaudeConfigManager()
    if not mgr.exists():
        print("Claude Desktop configuration not found.")
        return

    if args.server:
        if mgr.unprotect_server(args.server):
            print(f"[OK] Restored server '{args.server}' to original settings.")
        else:
            print(f"Server '{args.server}' not found.")
    else:
        restored, total = mgr.unprotect_all()
        print(f"[OK] Restored {restored} of {total} servers to original settings.")


def main():
    parser = argparse.ArgumentParser(
        prog="mcp-firewall",
        description="MCP Firewall - Real-time authorization & monitoring for Claude Desktop and Claude Web MCP requests",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run the central authorization daemon & confirmation UI")
    daemon_parser.add_argument("--host", default=DEFAULT_IPC_HOST, help="IPC bind host")
    daemon_parser.add_argument("--port", type=int, default=DEFAULT_IPC_PORT, help="IPC bind port")
    daemon_parser.add_argument("--timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT, help="Request confirmation timeout (seconds)")
    daemon_parser.add_argument("--dashboard", action="store_true", help="Also display the activity monitor dashboard")
    daemon_parser.add_argument("--background", action="store_true", help="Internal flag for background spawn")

    # Command: wrap
    wrap_parser = subparsers.add_parser("wrap", help="Wrap an MCP server's stdio streams (used by Claude Desktop)")
    wrap_parser.add_argument("--server-name", default="unnamed-server", help="Name of the MCP server")
    wrap_parser.add_argument("--timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT, help="Timeout in seconds")

    # Command: proxy
    proxy_parser = subparsers.add_parser("proxy", help="Run HTTP/SSE reverse proxy for Claude Web")
    proxy_parser.add_argument("--host", default=DEFAULT_HTTP_PROXY_HOST, help="Proxy listen host")
    proxy_parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PROXY_PORT, help="Proxy listen port")
    proxy_parser.add_argument("--upstream", default=None, help="Upstream MCP server URL (e.g. http://127.0.0.1:3000)")
    proxy_parser.add_argument("--server-name", default="claude-web-gateway", help="Server name")
    proxy_parser.add_argument("--timeout", type=int, default=DEFAULT_REQUEST_TIMEOUT, help="Timeout in seconds")

    # Command: claude-status
    subparsers.add_parser("claude-status", help="Inspect Claude Desktop MCP configuration")

    # Command: claude-protect
    prot_parser = subparsers.add_parser("claude-protect", help="Wrap Claude Desktop MCP servers with MCP Firewall")
    prot_parser.add_argument("--server", help="Specific server name to protect (omitting protects all)")

    # Command: claude-unprotect
    unprot_parser = subparsers.add_parser("claude-unprotect", help="Restore Claude Desktop MCP servers to original commands")
    unprot_parser.add_argument("--server", help="Specific server name to restore (omitting restores all)")

    # Parse args, splitting for 'wrap' target command
    if "wrap" in sys.argv:
        wrap_idx = sys.argv.index("wrap")
        if "--" in sys.argv[wrap_idx:]:
            dash_idx = sys.argv.index("--", wrap_idx)
            parsed_args = parser.parse_args(sys.argv[1:dash_idx])
            remaining_args = sys.argv[dash_idx + 1:]
            run_wrap_command(parsed_args, remaining_args)
            return

    args = parser.parse_args()

    if args.command == "daemon":
        run_daemon_command(args)
    elif args.command == "wrap":
        # If no '--' was given
        print("Usage: mcp-firewall wrap --server-name <NAME> -- <command> [args...]")
    elif args.command == "proxy":
        run_proxy_command(args)
    elif args.command == "claude-status":
        run_claude_status_command(args)
    elif args.command == "claude-protect":
        run_claude_protect_command(args)
    elif args.command == "claude-unprotect":
        run_claude_unprotect_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
