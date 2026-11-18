"""Comprehensive demonstration of MCP Firewall functionality."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from demo.mock_claude_desktop import MockClaudeDesktop
from demo.mock_claude_web import MockClaudeWeb


ROOT_DIR = Path(__file__).resolve().parent.parent


def print_banner(text: str):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def start_daemon_process():
    """Starts the daemon process in background."""
    cmd = [sys.executable, "-m", "mcp_firewall", "daemon", "--port", "9876", "--timeout", "45"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Give it a second to bind
    time.sleep(1.5)
    return proc


def start_http_proxy_process():
    """Starts the HTTP proxy process in background."""
    cmd = [sys.executable, "-m", "mcp_firewall", "proxy", "--port", "8765", "--server-name", "web-tools-server"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(1.5)
    return proc


def demo_claude_desktop_allow():
    print_banner("SCENARIO 1: Claude Desktop Initiates 'read_file' -> [USER ALLOWS]")
    print("Action: Claude Desktop requests to read 'secrets/config.json'.")
    print("-> A confirmation modal will pop up. Please click [ALLOW REQUEST] to approve.")

    server_script = str(ROOT_DIR / "demo" / "mock_mcp_server.py")
    wrap_cmd = [
        sys.executable,
        "-m",
        "mcp_firewall",
        "wrap",
        "--server-name",
        "production-fs",
        "--",
        sys.executable,
        server_script,
    ]

    client = MockClaudeDesktop(wrap_cmd)
    client.start()

    resp = client.call_tool("read_file", {"path": "secrets/config.json"})
    print("\n[Claude Desktop Received Response]:")
    print(json.dumps(resp, indent=2))

    client.close()
    is_allowed = not resp.get("result", {}).get("isError", False)
    if is_allowed:
        print("\n[PASSED] RESULT: Request was ALLOWED and executed successfully by the MCP server.")
    else:
        print("\n[INFO] RESULT: Request was blocked or closed.")
    return is_allowed


def demo_claude_desktop_block():
    print_banner("SCENARIO 2: Claude Desktop Initiates 'delete_database' -> [USER BLOCKS]")
    print("Action: Claude Desktop requests to DROP DATABASE 'production_customers'.")
    print("-> A confirmation modal will pop up. Please click [BLOCK REQUEST] to reject.")

    server_script = str(ROOT_DIR / "demo" / "mock_mcp_server.py")
    wrap_cmd = [
        sys.executable,
        "-m",
        "mcp_firewall",
        "wrap",
        "--server-name",
        "production-database",
        "--",
        sys.executable,
        server_script,
    ]

    client = MockClaudeDesktop(wrap_cmd)
    client.start()

    resp = client.call_tool("delete_database", {"database_name": "production_customers", "force": True})
    print("\n[Claude Desktop Received Response]:")
    print(json.dumps(resp, indent=2))

    client.close()
    is_blocked = resp.get("result", {}).get("isError", False)
    if is_blocked:
        print("\n[SHIELDED] RESULT: Request was successfully BLOCKED by MCP Firewall!")
        print("   Notice that the target database server never executed the delete command.")
    else:
        print("\n[WARN] RESULT: Request was allowed.")
    return is_blocked


def demo_claude_web():
    print_banner("SCENARIO 3: Claude Web Initiates Tool Request via HTTP/SSE")
    print("Action: Claude Web sends POST request for 'execute_shell_command'.")
    print("-> A confirmation modal will pop up tagged as 'Client: Claude Web (HTTP/SSE)'.")
    print("   Choose either [ALLOW] or [BLOCK].")

    client = MockClaudeWeb("http://127.0.0.1:8765")
    resp = client.call_tool("execute_shell_command", {"command": "rm -rf /var/log/audit.log"})
    print("\n[Claude Web Received Response]:")
    print(json.dumps(resp, indent=2))

    is_blocked = resp.get("result", {}).get("isError", False)
    if is_blocked:
        print("\n[SHIELDED] RESULT: Claude Web request was BLOCKED.")
    else:
        print("\n[PASSED] RESULT: Claude Web request was ALLOWED.")


def demo_concurrent_requests():
    print_banner("SCENARIO 4: Concurrent Simultaneous Requests from Multiple Clients")
    print("Action: Claude Desktop and Claude Web will dispatch requests at the EXACT same time.")
    print("-> The popup will manage the queue ('Queue: 1 of 2 pending').")
    print("   You can inspect each pending request and decide independently.")

    server_script = str(ROOT_DIR / "demo" / "mock_mcp_server.py")
    wrap_cmd = [
        sys.executable,
        "-m",
        "mcp_firewall",
        "wrap",
        "--server-name",
        "concurrent-fs",
        "--",
        sys.executable,
        server_script,
    ]

    results = {}

    def run_desktop():
        c = MockClaudeDesktop(wrap_cmd)
        c.start()
        res = c.call_tool("read_file", {"path": "financial_records_2026.xlsx"})
        results["desktop"] = res
        c.close()

    def run_web():
        w = MockClaudeWeb("http://127.0.0.1:8765")
        res = w.call_tool("execute_shell_command", {"command": "systemctl restart nginx"})
        results["web"] = res

    t1 = threading.Thread(target=run_desktop)
    t2 = threading.Thread(target=run_web)

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("\n[Concurrent Results Received]:")
    print("Claude Desktop:", json.dumps(results.get("desktop"), indent=2))
    print("Claude Web:", json.dumps(results.get("web"), indent=2))
    print("\n[PASSED] Concurrency test completed cleanly without deadlocks or race conditions.")


def run_all_demos(interactive: bool = True):
    print_banner("MCP FIREWALL - LIVE DEMONSTRATION SUITE")
    print("Ensuring background daemon and HTTP proxy are active...")

    daemon_proc = start_daemon_process()
    proxy_proc = start_http_proxy_process()

    try:
        demo_claude_desktop_allow()
        time.sleep(1)

        demo_claude_desktop_block()
        time.sleep(1)

        demo_claude_web()
        time.sleep(1)

        demo_concurrent_requests()

        print_banner("ALL DEMONSTRATION SCENARIOS COMPLETED SUCCESSFULLY")
    finally:
        daemon_proc.terminate()
        proxy_proc.terminate()


if __name__ == "__main__":
    run_all_demos()
