# MCP Firewall

A lightweight, real-time security proxy and approval firewall for Anthropic's Model Context Protocol (MCP). It intercepts incoming tool calls from Claude Desktop and Claude Web, pauses execution, and prompts you with a confirmation modal before any tool action is allowed to run.

---

## Architecture Overview

```
Claude Client (Desktop / Web)
       │
       ▼
MCP Firewall Interceptor (stdio wrapper / SSE reverse proxy)
       │
       ├──► Local IPC (127.0.0.1:9876) ──► Central Daemon & Approval Modal
       │                                         │
       │                                         ▼
       │                                  Live Dashboard
       ▼
MCP Server (Underlying tools: filesystem, database, shell, etc.)
```

- **Zero-trust fail-closed design**: Tool calls are held in memory until you explicitly click **Allow**. If unanswered after 60 seconds, requests automatically block.
- **Bi-directional interception**: Handles stdio-based MCP servers (Claude Desktop) and HTTP/SSE servers (Claude Web).
- **Live GUI Dashboard**: Tracks all requests, arguments, execution status, and decisions in real time.

---

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/CYNO28/mcp-firewall.git
   cd mcp-firewall
   ```

2. **Set up the virtual environment**:
   - **Windows**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

---

## Running the Firewall

Choose whichever method fits your setup best:

### Option A: Direct Shortcut (Easiest for Windows)
You do not need to activate the virtual environment manually. The script automatically locates the project's Python environment:
```powershell
.\run           # Starts the Daemon + Live Security Dashboard
.\run status    # Checks daemon and Claude config status
```

### Option B: Standard Python Command
If your virtual environment is already activated (`(.venv)` in prompt):
```bash
python start.py         # Starts Daemon + Live Security Dashboard
python start.py status  # Checks status
```

### Option C: Using the Installed CLI
```bash
mcp-firewall start      # Starts Daemon + Live Security Dashboard
mcp-firewall status     # Checks status
mcp-firewall daemon     # Starts daemon without the dashboard GUI
```

---

## Protecting Claude Desktop

### Automatic Setup (Recommended)
Inspect your existing Claude Desktop configuration:
```bash
mcp-firewall claude-status
```

Wrap all configured servers with MCP Firewall in one command:
```bash
mcp-firewall claude-protect
```
*(To remove the firewall and restore original settings: `mcp-firewall claude-unprotect`)*

### Manual Configuration
You can also manually edit your `claude_desktop_config.json`:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add `mcp_firewall wrap --server-name <NAME> --` to your server definition:
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "python",
      "args": [
        "-m", "mcp_firewall", "wrap",
        "--server-name", "filesystem",
        "--",
        "npx", "-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\Username\\Documents"
      ]
    }
  }
}
```

---

## Protecting Claude Web (HTTP / SSE)

For remote web clients, run the reverse proxy pointing to your upstream server:
```bash
mcp-firewall proxy --port 8765 --upstream http://127.0.0.1:3000 --server-name web-tools
```

In Claude Web, configure your MCP server URL to:
```
http://127.0.0.1:8765/sse
```

When Claude Web triggers an MCP tool call, it routes through port 8765 where the firewall holds it for user approval before proxying it to port 3000.

---

## Testing with the Included Sample Server

The repository includes a ready-to-use sample MCP server (`mcp_server.py`) exposing 9 filesystem, shell, and database tools (`create_file`, `read_file`, `delete_file`, `list_directory`, `execute_shell_command`, `delete_database`, etc.).

To run it wrapped by the firewall:
```bash
mcp-firewall wrap --server-name secure-tools -- python mcp_server.py
```

---

## CLI Reference

| Command | Syntax | Description |
| :--- | :--- | :--- |
| `start` | `mcp-firewall start` | Starts daemon & live dashboard together |
| `status` | `mcp-firewall status` | Shows daemon health and Claude config |
| `daemon` | `mcp-firewall daemon [--dashboard]` | Runs the central IPC daemon and approval popup |
| `wrap` | `mcp-firewall wrap --server-name <N> -- <CMD>` | Wraps target MCP stdio process |
| `proxy` | `mcp-firewall proxy --port <P> --upstream <U>` | Runs HTTP/SSE reverse proxy |
| `claude-status` | `mcp-firewall claude-status` | Checks Claude Desktop config |
| `claude-protect` | `mcp-firewall claude-protect` | Wraps all servers in Claude Desktop config |
| `claude-unprotect` | `mcp-firewall claude-unprotect` | Unwraps servers and restores backup |

---

## License

MIT License.
