"""Configuration settings for MCP Firewall."""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MCP_FIREWALL_DATA_DIR", Path.home() / ".mcp_firewall"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUDIT_LOG_FILE = DATA_DIR / "audit_log.jsonl"
CONFIG_FILE = DATA_DIR / "config.json"

# Daemon IPC network settings
DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = int(os.environ.get("MCP_FIREWALL_IPC_PORT", 9876))

# HTTP / SSE Proxy network settings (for Claude Web)
DEFAULT_HTTP_PROXY_HOST = "127.0.0.1"
DEFAULT_HTTP_PROXY_PORT = int(os.environ.get("MCP_FIREWALL_HTTP_PORT", 8765))

# Request confirmation timeout in seconds (0 = infinite / wait forever)
DEFAULT_REQUEST_TIMEOUT = int(os.environ.get("MCP_FIREWALL_TIMEOUT", 60))

# Default action when confirmation dialog times out: "BLOCK" or "ALLOW"
DEFAULT_TIMEOUT_ACTION = os.environ.get("MCP_FIREWALL_TIMEOUT_ACTION", "BLOCK").upper()

# UI settings
UI_THEME = "dark"
POPUP_ALWAYS_ON_TOP = True
MAX_DISPLAY_ARG_LENGTH = 10000

# Interception rules
# Sensitive methods to intercept. Typically "tools/call".
INTERCEPTED_METHODS = {"tools/call"}

# Whitelist / Auto-approve tool patterns (optional regex list)
# e.g., ["read_.*", "get_.*"] if user opts in
AUTO_APPROVE_PATTERNS = []

# Claude Desktop config paths by OS
def get_claude_desktop_config_path() -> Path:
    """Returns the expected path to claude_desktop_config.json."""
    custom_path = os.environ.get("CLAUDE_CONFIG_PATH")
    if custom_path:
        return Path(custom_path)
    
    if os.name == "nt":  # Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    elif os.uname().sysname == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
