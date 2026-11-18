"""Helper to inspect, backup, and patch Claude Desktop configuration."""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_firewall.config import get_claude_desktop_config_path


class ClaudeConfigManager:
    """Manages claude_desktop_config.json for seamless MCP firewall wrapping."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or get_claude_desktop_config_path()

    def exists(self) -> bool:
        return self.config_path.exists()

    def read_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {"mcpServers": {}}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to read Claude Desktop config: {e}")

    def write_config(self, config: Dict[str, Any]):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def backup_config(self) -> Optional[Path]:
        if not self.config_path.exists():
            return None
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.with_name(f"{self.config_path.name}.{timestamp}.backup")
        shutil.copy2(self.config_path, backup_path)
        return backup_path

    def list_servers(self) -> List[Dict[str, Any]]:
        cfg = self.read_config()
        servers = cfg.get("mcpServers", {})
        result = []
        for name, spec in servers.items():
            command = spec.get("command", "")
            args = spec.get("args", [])
            is_wrapped = "mcp_firewall" in " ".join([command] + args)
            result.append({
                "name": name,
                "command": command,
                "args": args,
                "is_protected": is_wrapped,
            })
        return result

    def protect_server(self, server_name: str) -> bool:
        """Wrap a specific MCP server with mcp_firewall."""
        cfg = self.read_config()
        servers = cfg.get("mcpServers", {})
        if server_name not in servers:
            return False

        spec = servers[server_name]
        cmd = spec.get("command")
        args = spec.get("args", [])

        # Check if already wrapped
        if "mcp_firewall" in " ".join([cmd] + args):
            return True

        self.backup_config()

        # Wrap command
        new_command = sys.executable
        new_args = ["-m", "mcp_firewall", "wrap", "--server-name", server_name, "--", cmd] + args

        servers[server_name] = {
            "command": new_command,
            "args": new_args,
            "_original_command": cmd,
            "_original_args": args,
        }
        if "env" in spec:
            servers[server_name]["env"] = spec["env"]

        self.write_config(cfg)
        return True

    def unprotect_server(self, server_name: str) -> bool:
        """Restore an MCP server to its original command."""
        cfg = self.read_config()
        servers = cfg.get("mcpServers", {})
        if server_name not in servers:
            return False

        spec = servers[server_name]
        orig_cmd = spec.get("_original_command")
        orig_args = spec.get("_original_args")

        if orig_cmd is not None and orig_args is not None:
            servers[server_name] = {
                "command": orig_cmd,
                "args": orig_args,
            }
            if "env" in spec:
                servers[server_name]["env"] = spec["env"]
            self.write_config(cfg)
            return True

        # Fallback if _original_* wasn't saved: parse from args after '--'
        args = spec.get("args", [])
        if "--" in args:
            idx = args.index("--")
            rest = args[idx + 1:]
            if rest:
                servers[server_name] = {
                    "command": rest[0],
                    "args": rest[1:],
                }
                if "env" in spec:
                    servers[server_name]["env"] = spec["env"]
                self.write_config(cfg)
                return True

        return False

    def protect_all(self) -> Tuple[int, int]:
        """Protect all configured servers. Returns (protected_count, total_count)."""
        cfg = self.read_config()
        servers = cfg.get("mcpServers", {})
        count = 0
        for name in list(servers.keys()):
            if self.protect_server(name):
                count += 1
        return count, len(servers)

    def unprotect_all(self) -> Tuple[int, int]:
        """Unprotect all configured servers. Returns (unprotected_count, total_count)."""
        cfg = self.read_config()
        servers = cfg.get("mcpServers", {})
        count = 0
        for name in list(servers.keys()):
            if self.unprotect_server(name):
                count += 1
        return count, len(servers)
