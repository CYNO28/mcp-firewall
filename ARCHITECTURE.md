# MCP Firewall — Architecture & Design

This document explains how MCP Firewall monitors and intercepts Model Context Protocol (MCP) communication between Claude (Desktop & Web) and local or remote MCP servers.

---

## 1. High-Level Flow

Instead of inspecting raw network packets, MCP Firewall operates directly on **JSON-RPC 2.0 messages** exchanged over `stdio` or HTTP/SSE. It sits as a proxy between Claude and the target MCP server:

```
[ Claude Desktop ]               [ Claude Web ]
        │ (stdio)                       │ (HTTP / SSE)
        ▼                               ▼
 [ stdio_wrapper.py ]            [ http_proxy.py ]
        │                               │
        └──────────────┬────────────────┘
                       │ Local IPC (127.0.0.1:9876)
                       ▼
            [ Approval Daemon & GUI ]
             - Always-on-top popup modal
             - Real-time activity dashboard
             - 60s default-deny timer
                       │
         ┌─────────────┴─────────────┐
      [ALLOW]                     [BLOCK]
         │                           │
         ▼                           ▼
 Forwarded to target         Dropped (0 bytes sent).
 MCP server for execution.   Synthetic MCP error returned
                             to Claude: isError = true
```

---

## 2. Core Components

The codebase is organized into four distinct parts:

1. **Stdio Interceptor (`mcp_firewall/interceptors/stdio_wrapper.py`)**:
   - Claude Desktop launches MCP servers as child processes and talks to them over `stdin` and `stdout`.
   - The wrapper runs as an intermediary process around the server (`python -m mcp_firewall wrap --server-name <NAME> -- <target-command>`).
   - Discovery calls (`initialize`, `tools/list`, `resources/list`, ping) pass through directly so initial handshake and capability discovery work without interruption.
   - When a `"method": "tools/call"` arrives, the wrapper pauses reading on `stdin`, packages the parameters, and sends an approval request to the daemon over a local TCP socket.

2. **HTTP / SSE Reverse Proxy (`mcp_firewall/interceptors/http_proxy.py`)**:
   - Web-based clients connect to remote MCP servers using Server-Sent Events (SSE) for server-to-client streaming and HTTP POST for requests.
   - The reverse proxy listens on `127.0.0.1:8765`, accepts incoming `/sse` connections, and intercepts `POST /message` calls.
   - Non-tool calls pass through to upstream. Any `tools/call` payload is held pending user approval before forwarding.

3. **Approval Engine & Daemon (`mcp_firewall/daemon/`)**:
   - `ipc_server.py`: Listens on `127.0.0.1:9876` for requests coming from any running stdio wrappers or HTTP proxies.
   - `approval_manager.py`: Thread-safe manager that assigns a UUID to each incoming request, queues it, and blocks the calling worker thread with a `threading.Event()`.
   - `ipc_client.py`: Used by wrappers/proxies to submit requests. If the background daemon isn't running, it can automatically spawn it or fall back to a self-contained dialog.

4. **User Interface (`mcp_firewall/ui/`)**:
   - `popup.py`: Native Tkinter confirmation dialog. Marked `-topmost True` so it appears above other active windows. Shows client origin, server, tool name, and formatted JSON parameters.
   - `dashboard.py`: Monitoring window showing total requests, allowed, blocked, and a live history table.

---

## 3. How Requests Are Handled

### When the User Clicks [ALLOW]
1. The UI sets the decision status to `ALLOWED` and unblocks the waiting interceptor thread.
2. The raw request string is written directly to the MCP server's `stdin` (or forwarded upstream via HTTP).
3. The server executes the tool and outputs the real result, which is passed back to Claude.

### When the User Clicks [BLOCK] (or on Timeout)
1. The request payload is immediately dropped. **Zero bytes reach the target server.**
2. The firewall synthesizes a valid MCP response with `"isError": true`:
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {
       "content": [
         {
           "type": "text",
           "text": "[MCP FIREWALL BLOCKED]: User rejected execution of tool 'delete_file'."
         }
       ],
       "isError": true
     }
   }
   ```
3. Returning an MCP-compliant error result allows Claude's conversation to stay intact without crashing or hanging the session.

---

## 4. Concurrency & Multi-Client Queueing

If Claude Desktop calls multiple tools in parallel, or if both Claude Desktop and Claude Web fire requests simultaneously:
- Each incoming request is handled in its own worker thread and added to the pending queue with a distinct UUID.
- The confirmation modal displays a queue counter (e.g. `Queue: 1 of 3 pending`) with `[◀ Previous]` and `[Next ▶]` buttons.
- The user can inspect parameters and render decisions independently for each request without deadlocks.

---

## 5. Security & Fail-Safe Design

- **Fail-Closed (Default-Deny)**: If the confirmation modal times out (default 60 seconds) or the user closes the window, the request is automatically blocked.
- **Selective Interception**: Non-sensitive discovery calls (`tools/list`, `initialize`) are allowed through automatically to avoid notification fatigue while strictly protecting tool execution.
- **Persistent Audit Logging**: Every intercepted request, client type, timestamp, payload, and final decision is logged to `~/.mcp_firewall/audit_log.jsonl`.
