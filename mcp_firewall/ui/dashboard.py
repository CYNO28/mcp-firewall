import json
import time
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from mcp_firewall.models import MCPRequest, RequestStatus
from mcp_firewall.ui.theme import THEME


class MonitoringDashboard:
    def __init__(self, root: Optional[tk.Tk] = None):
        self.root = root or tk.Tk()
        self.history: List[MCPRequest] = []
        self._item_map = {}
        self._setup_window()
        self._build_ui()

    def _setup_window(self):
        self.root.title("MCP Firewall - Activity & Security Monitor")
        self.root.geometry("860x600")
        self.root.minsize(720, 500)
        self.root.configure(bg=THEME["bg_main"])

    def _build_ui(self):
        header = tk.Frame(self.root, bg=THEME["bg_card"], padx=20, pady=16)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="🛡️  MCP Firewall Dashboard",
            font=(THEME["font_family"], 16, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_card"],
        ).pack(side=tk.LEFT)

        self.status_indicator = tk.Label(
            header,
            text="● SERVICE ACTIVE",
            font=(THEME["font_family"], 10, "bold"),
            fg=THEME["allow_btn"],
            bg=THEME["bg_card"],
        )
        self.status_indicator.pack(side=tk.RIGHT)

        clear_btn = tk.Button(
            header,
            text="Clear Table",
            font=(THEME["font_family"], 9, "bold"),
            bg=THEME["bg_input"],
            fg=THEME["text_muted"],
            activebackground=THEME["bg_card"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=2,
            cursor="hand2",
            command=self.clear_table,
        )
        clear_btn.pack(side=tk.RIGHT, padx=12)

        metrics_frame = tk.Frame(self.root, bg=THEME["bg_main"], padx=20, pady=14)
        metrics_frame.pack(fill=tk.X)

        self.card_total = self._create_metric_card(metrics_frame, "TOTAL REQUESTS", "0", THEME["text_primary"])
        self.card_allowed = self._create_metric_card(metrics_frame, "ALLOWED", "0", THEME["allow_btn"])
        self.card_blocked = self._create_metric_card(metrics_frame, "BLOCKED", "0", THEME["block_btn"])

        table_frame = tk.Frame(self.root, bg=THEME["bg_main"], padx=20, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            table_frame,
            text="Intercepted Requests History",
            font=(THEME["font_family"], 12, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_main"],
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = ("time", "client", "server", "tool", "status", "params")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

        self.tree.heading("time", text="Timestamp")
        self.tree.heading("client", text="Client")
        self.tree.heading("server", text="Server")
        self.tree.heading("tool", text="Tool")
        self.tree.heading("status", text="Decision")
        self.tree.heading("params", text="Arguments Summary")

        self.tree.column("time", width=80, anchor=tk.CENTER)
        self.tree.column("client", width=140, anchor=tk.W)
        self.tree.column("server", width=100, anchor=tk.W)
        self.tree.column("tool", width=140, anchor=tk.W)
        self.tree.column("status", width=90, anchor=tk.CENTER)
        self.tree.column("params", width=260, anchor=tk.W)

        self.tree.tag_configure("PENDING", foreground="#f59e0b")
        self.tree.tag_configure("ALLOWED", foreground="#10b981")
        self.tree.tag_configure("BLOCKED", foreground="#ef4444")
        self.tree.tag_configure("TIMEOUT", foreground="#ef4444")

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _create_metric_card(self, parent, title: str, initial_value: str, value_color: str):
        card = tk.Frame(parent, bg=THEME["bg_card"], padx=16, pady=12, relief=tk.FLAT)
        card.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6)

        tk.Label(
            card,
            text=title,
            font=(THEME["font_family"], 9, "bold"),
            fg=THEME["text_muted"],
            bg=THEME["bg_card"],
        ).pack(anchor=tk.W)

        val_label = tk.Label(
            card,
            text=initial_value,
            font=(THEME["font_family"], 20, "bold"),
            fg=value_color,
            bg=THEME["bg_card"],
        )
        val_label.pack(anchor=tk.W, pady=(4, 0))
        return val_label

    def update_metrics(self, total: int, allowed: int, blocked: int):
        self.card_total.config(text=str(total))
        self.card_allowed.config(text=str(allowed))
        self.card_blocked.config(text=str(blocked))

    def clear_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.history.clear()
        self._item_map.clear()
        self.update_metrics(0, 0, 0)
        from mcp_firewall.config import AUDIT_LOG_FILE
        if AUDIT_LOG_FILE.exists():
            try:
                AUDIT_LOG_FILE.unlink()
            except Exception:
                pass

    def record_request(self, request: MCPRequest):
        if request.request_id in self._item_map:
            return
        self.history.append(request)
        timestr = time.strftime("%H:%M:%S", time.localtime(request.timestamp))
        status = request.status.value if hasattr(request.status, "value") else str(request.status)
        client = request.client_type.value if hasattr(request.client_type, "value") else str(request.client_type)
        summary = json.dumps(request.arguments)
        if len(summary) > 60:
            summary = summary[:57] + "..."

        item_id = self.tree.insert(
            "",
            0,
            values=(timestr, client, request.server_name, request.tool_name, status, summary),
            tags=(status,),
        )
        self._item_map[request.request_id] = item_id

        total = len(self.history)
        allowed = sum(1 for r in self.history if r.status == RequestStatus.ALLOWED)
        blocked = sum(1 for r in self.history if r.status in (RequestStatus.BLOCKED, RequestStatus.TIMEOUT))
        self.update_metrics(total, allowed, blocked)
        try:
            self.root.update_idletasks()
        except Exception:
            pass

    def update_decision(self, request_id: str, status: RequestStatus):
        for r in self.history:
            if r.request_id == request_id:
                r.status = status
                break

        item_id = self._item_map.get(request_id)
        if item_id and self.tree.exists(item_id):
            current_vals = list(self.tree.item(item_id, "values"))
            if len(current_vals) >= 6:
                status_str = status.value if hasattr(status, "value") else str(status)
                current_vals[4] = status_str
                self.tree.item(item_id, values=current_vals, tags=(status_str,))

        total = len(self.history)
        allowed = sum(1 for r in self.history if r.status == RequestStatus.ALLOWED)
        blocked = sum(1 for r in self.history if r.status in (RequestStatus.BLOCKED, RequestStatus.TIMEOUT))
        self.update_metrics(total, allowed, blocked)
        try:
            self.root.update_idletasks()
        except Exception:
            pass
