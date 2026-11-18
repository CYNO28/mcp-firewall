"""A realistic mock MCP Server implementing JSON-RPC 2.0 over stdio."""

import json
import sys


TOOLS = [
    {
        "name": "read_file",
        "description": "Read file contents from filesystem",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "delete_database",
        "description": "CRITICAL: Drop or wipe a database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "force": {"type": "boolean"},
            },
            "required": ["database_name"],
        },
    },
    {
        "name": "execute_shell_command",
        "description": "CRITICAL: Run a bash or PowerShell command",
        "inputSchema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
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
                "serverInfo": {"name": "MockSecureMCPServer", "version": "1.0.0"},
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

        # Log execution to stderr so test runner can audit whether server actually ran
        sys.stderr.write(f"[MOCK-MCP-SERVER] >>> EXECUTING TOOL: {tool_name} with args: {args}\n")
        sys.stderr.flush()

        if tool_name == "read_file":
            path = args.get("path", "sample.txt")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Contents of {path}: [CONFIDENTIAL DATA - READ SUCCESSFUL]"}],
                    "isError": False,
                },
            }

        elif tool_name == "delete_database":
            db = args.get("database_name", "prod_db")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"SUCCESS: Database '{db}' was PERMANENTLY DELETED."}],
                    "isError": False,
                },
            }

        elif tool_name == "execute_shell_command":
            cmd = args.get("command", "dir")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Command '{cmd}' executed with exit status 0."}],
                    "isError": False,
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
        }

    # Default fallback
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {},
    }


def main():
    sys.stderr.write("[MOCK-MCP-SERVER] Server started and listening on stdio.\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"[MOCK-MCP-SERVER] Error processing line: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
