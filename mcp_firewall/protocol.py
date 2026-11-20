"""JSON-RPC 2.0 and MCP Protocol parsing, handling, and synthetic responses."""

import json
from typing import Any, Dict, Optional, Tuple


def parse_jsonrpc(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single JSON-RPC line into a Python dict."""
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        if isinstance(data, dict) and data.get("jsonrpc") == "2.0":
            return data
        return None
    except Exception:
        return None


def is_tool_call(message: Dict[str, Any]) -> bool:
    """Check if the JSON-RPC message is a tool invocation request."""
    return message.get("method") == "tools/call"


def extract_tool_call_details(message: Dict[str, Any]) -> Tuple[str, Dict[str, Any], Any]:
    """
    Extract (tool_name, arguments, raw_id) from an MCP tools/call request.
    
    Format:
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "example_tool",
            "arguments": {...}
        }
    }
    """
    raw_id = message.get("id")
    params = message.get("params", {})
    tool_name = params.get("name", "unknown_tool")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        arguments = {"raw_arguments": arguments}
    return tool_name, arguments, raw_id


def create_block_response(
    raw_id: Any,
    tool_name: str,
    reason: str = "Request blocked by user via MCP Firewall",
    use_protocol_error: bool = False,
) -> Dict[str, Any]:
    """
    Generate an MCP-compliant response indicating the tool call was blocked.
    
    By default, returns an MCP CallToolResult with `isError: true`. This allows
    Claude Desktop and Claude Web to present the rejection naturally in conversation
    without terminating or crashing the MCP connection.
    """
    if use_protocol_error:
        return {
            "jsonrpc": "2.0",
            "id": raw_id,
            "error": {
                "code": -32000,
                "message": f"MCP Firewall Error: Execution of '{tool_name}' was blocked by the user. {reason}",
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": raw_id,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"[MCP FIREWALL BLOCKED]: User explicitly REJECTED the execution of tool '{tool_name}'.\n"
                        f"Reason: {reason}\n"
                        "Permission was denied by the user. Do NOT retry this operation."
                    ),
                }
            ],
            "isError": True,
        },
    }


def serialize_jsonrpc(message: Dict[str, Any]) -> str:
    """Serialize a dict to a single-line JSON string followed by newline."""
    return json.dumps(message, ensure_ascii=False) + "\n"
