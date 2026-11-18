# Architecture & Technical Design: MCP Firewall

## 1. Executive Summary

**MCP Firewall** is an application-level security gateway and authorization proxy designed to monitor, inspect, and enforce human-in-the-loop approvals on Model Context Protocol (MCP) tool executions originating from **Claude Desktop** and **Claude Web**.

Unlike conventional network firewalls that inspect raw IP packets, MCP Firewall operates directly at the **JSON-RPC 2.0 / MCP Protocol layer**. It acts as a transparent, bidirectional intermediary that holds pending tool calls in a suspended state while displaying an always-on-top confirmation modal to the user. Only when the user explicitly grants permission is the payload released to the underlying MCP server. If denied or if the request times out, execution is halted immediately and an MCP-compliant error response is synthesized, ensuring that target systems remain untouched and the LLM conversation proceeds smoothly.

---

## 2. High-Level Architecture Diagram

```
+---------------------------------------------------------------------------------------+
|                                    CLIENT LAYER                                       |
|                                                                                       |
|   +--------------------------+                         +--------------------------+   |
|   |      Claude Desktop      |                         |        Claude Web        |   |
|   |  (Local Electron App)    |                         |  (Browser / Web Client)  |   |
|   +------------+-------------+                         +------------+-------------+   |
+----------------|----------------------------------------------------|-----------------+
                 | stdio (JSON-RPC)                                   | HTTP POST / SSE
                 v                                                    v
+---------------------------------------------------------------------------------------+
|                                INTERCEPTION LAYER                                     |
|                                                                                       |
|   +--------------------------+                         +--------------------------+   |
|   |  Stdio Wrapper Proxy     |                         |   HTTP / SSE Reverse     |   |
|   |  (mcp_firewall.wrap)     |                         |         Proxy            |   |
|   +------------+-------------+                         +------------+-------------+   |
+----------------|----------------------------------------------------|-----------------+
                 |                                                    |
                 +-----------------------+----------------------------+
                                         | Local IPC (TCP Socket / Loopback)
                                         v
+---------------------------------------------------------------------------------------+
|                             CORE ENGINE & DAEMON LAYER                                |
|                                                                                       |
|   +-------------------------------------------------------------------------------+   |
|   |                         Approval Manager (Thread-Safe)                        |   |
|   |   - Request Registry (UUID)                                                   |   |
|   |   - Threading Synchronization (threading.Event)                               |   |
|   |   - Persistent Audit Log (JSONL)                                              |   |
|   |   - Timeout Scheduler (Default-Deny Policy)                                   |   |
|   +------------------------------------+------------------------------------------+   |
|                                        | Scheduled UI Updates                         |
|                                        v                                              |
|   +-------------------------------------------------------------------------------+   |
|   |                  Always-On-Top GUI Confirmation Modal (Tkinter)               |   |
|   |   - Topmost Window Priority (Win32 Foreground Bring-to-Front)                 |   |
|   |   - Client & Server Badging                                                   |   |
|   |   - Formatted Payload Inspector                                               |   |
|   |   - Multi-Request Queue Navigator                                             |   |
|   |   - [ALLOW] vs. [BLOCK] Action Handlers                                       |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
                 | (If ALLOWED: released)          | (If BLOCKED: dropped)
                 v                                 x
+------------------------------------+             +------------------------------------+
|        TARGET MCP SERVER           |             |       SYNTHETIC ERROR RETURN       |
|  - Filesystem (@modelcontext...)   |             |  Returns CallToolResult with:      |
|  - Database, Git, Shell, Custom    |             |  - isError: true                   |
|  - Tool executes on host           |             |  - Rejection explanation for LLM   |
+------------------------------------+             +------------------------------------+
```

---

## 3. Communication Interception Mechanisms

### 3.1 Claude Desktop: Stdio Interception
Claude Desktop manages local MCP servers by spawning them as child processes and communicating across standard input (`stdin`) and standard output (`stdout`) using newline-delimited JSON-RPC 2.0 messages.

#### Interception Approach:
MCP Firewall wraps the target server command transparently:
```bash
python -m mcp_firewall wrap --server-name filesystem -- npx -y @modelcontextprotocol/server-filesystem C:\Users
```

1. **Passthrough for Non-Sensitive Messages**:
   Protocol setup (`initialize`, `notifications/initialized`), discovery queries (`tools/list`, `resources/list`, `prompts/list`), and ping requests pass directly through to the target server without user interruption.
2. **Detection of Tool Invocations**:
   When a message with `"method": "tools/call"` arrives from Claude Desktop:
   - Reading on `sys.stdin` is paused for this request.
   - The tool name, parameters, and JSON-RPC ID are extracted into a structured `MCPRequest`.
   - The wrapper dispatches the request to the central Approval Daemon over a local IPC loopback socket (`127.0.0.1:9876`).
3. **Execution Gating**:
   - **Allowed**: The original raw line is written to the target MCP server's `stdin` and flushed. Output from the server's `stdout` is forwarded back to Claude Desktop.
   - **Blocked**: The payload is discarded. Zero bytes are written to the target server. A synthetic MCP tool call result with `"isError": true` is returned to Claude Desktop's `stdout`:
     ```json
     {
       "jsonrpc": "2.0",
       "id": 12,
       "result": {
         "content": [
           {
             "type": "text",
             "text": "[MCP FIREWALL BLOCKED]: User rejected the execution of tool 'delete_file'. The operation was NOT executed on the system."
           }
         ],
         "isError": true
       }
     }
     ```

### 3.2 Claude Web: HTTP and SSE Reverse Proxy
Claude Web (or web-based LLM clients) communicates with MCP servers via Server-Sent Events (SSE) for server-to-client streaming and HTTP POST requests for client-to-server JSON-RPC communication.

#### Interception Approach:
MCP Firewall runs a multi-threaded reverse proxy on `http://127.0.0.1:8765`:
1. **Endpoint Resolution**:
   - When the client connects with `GET /sse`, the proxy coordinates the event stream and returns an endpoint pointing to the proxy's `/message` path.
2. **POST Interception**:
   - Claude Web issues tool calls via `POST /message`.
   - The proxy parses the JSON payload. If `"method": "tools/call"` is detected, it creates an `MCPRequest` tagged with `ClientType.CLAUDE_WEB_HTTP` and submits it to the Approval Manager.
3. **Decision Enforcement**:
   - **Allowed**: The POST request is forwarded to the upstream MCP server, and the server's response is streamed back to Claude Web.
   - **Blocked**: The request never reaches the upstream server. The proxy responds with HTTP 200 containing the MCP error payload, informing Claude Web that the action was rejected.

---

## 4. Concurrency and Multi-Request Handling

A critical requirement is handling multiple simultaneous MCP requests without deadlocks or missed approvals.

1. **Thread-Safe Architecture**:
   - Each incoming connection (from stdio wrappers or HTTP worker threads) runs in an independent thread.
   - Requests are assigned a unique UUID and registered in a thread-safe dictionary guarded by `threading.Lock`.
   - Each pending request has its own `threading.Event()` primitive.
2. **UI Queue Navigation**:
   - When multiple requests arrive simultaneously (e.g., Claude Desktop calling tools in parallel, or Claude Desktop and Claude Web both firing requests), the Confirmation Modal dynamically displays:
     - A queue counter: `Queue: 1 of 3 pending`
     - Navigation controls (`[◀ Previous]` and `[Next ▶]`)
   - The user can review arguments for each request independently.
   - Resolving one request instantly shifts focus to the next waiting item in the queue.
3. **Zero Deadlock Guarantee**:
   - The GUI event loop runs purely in Tkinter's main thread, while IPC communication occurs on background worker threads.
   - UI updates are marshaled using `root.after(0, ...)`.

---

## 5. Security & Fail-Safe Model

| Threat / Failure Mode | Firewall Mitigation |
| :--- | :--- |
| **User Unattended / Inactivity** | Configurable countdown timer (default 60s). Defaults to **BLOCK** (fail-closed) upon timeout. |
| **Daemon Process Offline** | Stdio wrapper automatically spawns daemon, or falls back to an embedded standalone modal. Never fails open. |
| **Target Server Compromise** | Destructive payloads (`rm -rf`, `delete_database`) are intercepted prior to reaching server stdin or network port. |
| **Window Obscured by Other Apps** | Enforces OS topmost window flag (`-topmost True`) and Win32 `SetForegroundWindow` API priority. |
| **Auditability** | Every request, decision, timestamp, client, and payload is logged to persistent JSONL audit log. |
