"""MCP Server implementing JSON-RPC 2.0 over stdio with comprehensive filesystem, system, and database tools."""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

TOOLS = [
    {
        "name": "create_file",
        "description": "Create a file on the filesystem with specified content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path of the file to create"},
                "content": {"type": "string", "description": "Text content to write into the file"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file from the filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path of the file to read"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file from the filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path of the file to delete"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_directory",
        "description": "List all files and folders in a directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "rename_file",
        "description": "Rename or move a file from one path to another",
        "inputSchema": {
            "type": "object",
            "properties": {
                "old_path": {"type": "string", "description": "Original file path"},
                "new_path": {"type": "string", "description": "New file path"},
            },
            "required": ["old_path", "new_path"],
        },
    },
    {
        "name": "execute_shell_command",
        "description": "CRITICAL: Execute a command in Windows PowerShell or CMD",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "query_database",
        "description": "Execute a SQL query against the database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "Database to query"},
                "sql": {"type": "string", "description": "SQL query statement"},
            },
            "required": ["database_name", "sql"],
        },
    },
    {
        "name": "delete_database",
        "description": "CRITICAL: Drop or permanently wipe a database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "description": "Database name to drop"},
                "force": {"type": "boolean", "description": "Force drop all active connections"},
            },
            "required": ["database_name"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Download or fetch data from an external HTTP/HTTPS URL",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "HTTP/HTTPS URL to fetch"},
            },
            "required": ["url"],
        },
    },
]


def handle_request(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "SecureMCPServer", "version": "1.1.0"},
            },
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "create_file":
            file_path = args.get("path", "test.txt")
            content = args.get("content", "")
            try:
                p = Path(file_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"[SUCCESS]: File '{file_path}' created with {len(content)} characters."}],
                        "isError": False,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "read_file":
            file_path = args.get("path", "test.txt")
            try:
                p = Path(file_path)
                if p.exists():
                    data = p.read_text(encoding="utf-8")
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Contents of {file_path}:\n{data}"}],
                            "isError": False,
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[NOT FOUND]: '{file_path}' does not exist."}], "isError": True},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "delete_file":
            file_path = args.get("path", "test.txt")
            try:
                p = Path(file_path)
                if p.exists():
                    p.unlink()
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"[DELETED]: File '{file_path}' removed."}],
                            "isError": False,
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[NOT FOUND]: '{file_path}' does not exist."}], "isError": True},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "list_directory":
            dir_path = args.get("path", ".")
            try:
                p = Path(dir_path)
                if p.exists() and p.is_dir():
                    entries = [f"{'[DIR]' if e.is_dir() else '[FILE]'} {e.name} ({e.stat().st_size if e.is_file() else '-'} bytes)" for e in p.iterdir()]
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"Directory listing of '{dir_path}':\n" + "\n".join(entries)}],
                            "isError": False,
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: Directory '{dir_path}' not found."}], "isError": True},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "rename_file":
            old_p = Path(args.get("old_path", ""))
            new_p = Path(args.get("new_path", ""))
            try:
                if old_p.exists():
                    new_p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old_p), str(new_p))
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"[RENAMED]: '{old_p}' -> '{new_p}'."}],
                            "isError": False,
                        },
                    }
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[NOT FOUND]: '{old_p}' does not exist."}], "isError": True},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "execute_shell_command":
            cmd = args.get("command", "")
            try:
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                out = res.stdout if res.stdout else res.stderr
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"[EXIT {res.returncode}]:\n{out}"}],
                        "isError": res.returncode != 0,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[EXECUTION ERROR]: {e}"}], "isError": True},
                }

        elif tool_name == "query_database":
            db = args.get("database_name", "default")
            sql = args.get("sql", "")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"[DATABASE '{db}']: Query '{sql}' returned 42 rows."}],
                    "isError": False,
                },
            }

        elif tool_name == "delete_database":
            db = args.get("database_name", "prod_db")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"[DATABASE DROPPED]: Database '{db}' permanently wiped."}],
                    "isError": False,
                },
            }

        elif tool_name == "fetch_url":
            url = args.get("url", "")
            try:
                req_obj = urllib.request.Request(url, headers={"User-Agent": "MCP-Client/1.0"})
                with urllib.request.urlopen(req_obj, timeout=10) as resp:
                    data = resp.read()[:500].decode("utf-8", errors="replace")
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "content": [{"type": "text", "text": f"[HTTP {resp.status}]: {data}..."}],
                            "isError": False,
                        },
                    }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"[HTTP ERROR]: {e}"}], "isError": True},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {},
    }


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception:
            pass


if __name__ == "__main__":
    main()
