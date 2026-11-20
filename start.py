"""Quick-start script for MCP Firewall.

Usage:
  python start.py          # Start the firewall daemon and monitoring dashboard
  python start.py status   # Check firewall daemon and Claude configuration status
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_firewall.cli import main

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("start")
    elif sys.argv[1] in ("status", "--status", "-s"):
        sys.argv[1] = "status"
    main()
