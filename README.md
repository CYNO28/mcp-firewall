# 🛡️ MCP Firewall

A real-time monitoring, protocol interception, and user authorization firewall for Model Context Protocol (MCP) communication initiated by Claude Desktop and Claude Web.

---

## 🚀 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/CYNO28/mcp-firewall.git
   cd mcp-firewall
   ```

2. **Activate the virtual environment**:
   - **Windows (PowerShell)**:
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     source .venv/bin/activate
     ```

3. **Install in editable mode**:
   ```bash
   pip install -e .
   ```

*(Note: If running without activating the venv, prefix commands with `.\.venv\Scripts\mcp-firewall` or `python -m mcp_firewall`)*

---

## 🖥️ How to Start and Run the App

### Quick Start (Easiest)

To start the central authorization daemon and the **Live Activity Dashboard**:

```bash
python start.py
```

To check the firewall daemon and Claude Desktop configuration status:

```bash
python start.py status
```

---

### Alternative: CLI Commands

You can also run commands directly via the CLI:

```bash
# Start the daemon and dashboard
mcp-firewall start

# Check overall status
mcp-firewall status
```

---

### 2. Protect Claude Desktop

#### Automatic Setup (Recommended)
Inspect your current Claude Desktop configuration:
```bash
mcp-firewall claude-status
```

Automatically wrap all configured servers in `claude_desktop_config.json` with MCP Firewall:
```bash
mcp-firewall claude-protect
```
*(To restore original settings at any time: `mcp-firewall claude-unprotect`)*

#### Manual Setup
Prepend `python -m mcp_firewall wrap --server-name <NAME> --` to any MCP server in your `claude_desktop_config.json`:
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

### 3. Protect Claude Web (HTTP / SSE)

Start the reverse proxy pointing to your upstream MCP server:
```bash
mcp-firewall proxy --port 8765 --upstream http://127.0.0.1:3000 --server-name web-tools
```

In Claude Web, configure your MCP server URL to:
```
http://127.0.0.1:8765/sse
```

Whenever Claude Web triggers a tool invocation, MCP Firewall intercepts the request and presents the confirmation popup.

---

### 4. Running with the Included Sample Server (Optional)

To test the firewall with a standalone server containing filesystem and database tools:

```bash
mcp-firewall wrap --server-name secure-tools -- python mcp_server.py
```

---

## 📖 CLI Commands Reference

| Command | Usage | Description |
| :--- | :--- | :--- |
| `mcp-firewall daemon` | `mcp-firewall daemon [--port 9876] [--dashboard]` | Starts the central authorization daemon & GUI modal |
| `mcp-firewall wrap` | `mcp-firewall wrap --server-name <NAME> -- <CMD...>` | Wraps target MCP server stdio streams (Claude Desktop) |
| `mcp-firewall proxy` | `mcp-firewall proxy --port 8765 --upstream <URL>` | Runs the HTTP/SSE reverse proxy (Claude Web) |
| `mcp-firewall claude-status` | `mcp-firewall claude-status` | Checks Claude Desktop MCP configuration |
| `mcp-firewall claude-protect` | `mcp-firewall claude-protect [--server <NAME>]` | Automatically wraps servers with MCP Firewall |
| `mcp-firewall claude-unprotect` | `mcp-firewall claude-unprotect [--server <NAME>]` | Restores original Claude Desktop configuration |

---

## 📄 License

MIT License.
