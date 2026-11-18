"""Always-on-top Confirmation Modal for MCP requests."""

import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from mcp_firewall.models import MCPRequest, RequestStatus, ApprovalDecision
from mcp_firewall.ui.theme import THEME


class ConfirmationModal:
    """
    Modern, always-on-top confirmation modal dialog for MCP requests.
    Supports concurrency, queue navigation, countdown timer, and detailed parameter inspection.
    """

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        on_decision: Optional[Callable[[ApprovalDecision], None]] = None,
        default_timeout: int = 60,
    ):
        self._external_root = root is not None
        self.root = root or tk.Tk()
        self.on_decision = on_decision
        self.default_timeout = default_timeout

        # Queue of pending requests
        self.pending_requests: List[MCPRequest] = []
        self.current_index: int = 0
        self.remaining_seconds: int = self.default_timeout

        # Timer handle
        self._timer_job = None

        self._setup_window()
        self._build_ui()

        # Hide initially if managed as persistent daemon
        if self._external_root:
            self.root.withdraw()

    def _setup_window(self):
        self.root.title("MCP Firewall - Authorization Required")
        self.root.geometry("620x540")
        self.root.minsize(540, 480)
        self.root.configure(bg=THEME["bg_main"])

        # Always-on-top behavior
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_clicked)

    def _bring_to_front(self):
        """Bring window above all other active applications."""
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.focus_force()

        if os.name == "nt":
            try:
                # Force Windows foreground priority
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass

    def _build_ui(self):
        # Top banner
        self.banner_frame = tk.Frame(self.root, bg=THEME["bg_card"], padx=16, pady=12)
        self.banner_frame.pack(fill=tk.X, side=tk.TOP)

        self.title_label = tk.Label(
            self.banner_frame,
            text="⚠️  MCP Tool Execution Request",
            font=(THEME["font_family"], 13, "bold"),
            fg=THEME["accent"],
            bg=THEME["bg_card"],
        )
        self.title_label.pack(side=tk.LEFT)

        self.queue_label = tk.Label(
            self.banner_frame,
            text="",
            font=(THEME["font_family"], 9, "bold"),
            fg=THEME["text_muted"],
            bg=THEME["bg_card"],
        )
        self.queue_label.pack(side=tk.RIGHT)

        # Meta info card
        self.meta_frame = tk.Frame(self.root, bg=THEME["bg_card"], padx=16, pady=10)
        self.meta_frame.pack(fill=tk.X, padx=14, pady=(10, 4))

        # Client Type & Server row
        meta_row1 = tk.Frame(self.meta_frame, bg=THEME["bg_card"])
        meta_row1.pack(fill=tk.X, pady=2)

        self.client_badge = tk.Label(
            meta_row1,
            text="Client: Unknown",
            font=(THEME["font_family"], 9, "bold"),
            fg="#ffffff",
            bg=THEME["badge_desktop"],
            padx=8,
            pady=2,
        )
        self.client_badge.pack(side=tk.LEFT, padx=(0, 8))

        self.server_badge = tk.Label(
            meta_row1,
            text="Server: default",
            font=(THEME["font_family"], 9, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_input"],
            padx=8,
            pady=2,
        )
        self.server_badge.pack(side=tk.LEFT)

        # Tool Name row
        meta_row2 = tk.Frame(self.meta_frame, bg=THEME["bg_card"])
        meta_row2.pack(fill=tk.X, pady=(6, 2))

        tk.Label(
            meta_row2,
            text="Tool Requested:",
            font=(THEME["font_family"], 10),
            fg=THEME["text_secondary"],
            bg=THEME["bg_card"],
        ).pack(side=tk.LEFT)

        self.tool_label = tk.Label(
            meta_row2,
            text="",
            font=(THEME["font_mono"], 11, "bold"),
            fg=THEME["accent"],
            bg=THEME["bg_card"],
        )
        self.tool_label.pack(side=tk.LEFT, padx=6)

        # Parameters Section
        param_header_frame = tk.Frame(self.root, bg=THEME["bg_main"], padx=16)
        param_header_frame.pack(fill=tk.X, pady=(8, 2))

        tk.Label(
            param_header_frame,
            text="Parameters & Payload",
            font=(THEME["font_family"], 10, "bold"),
            fg=THEME["text_primary"],
            bg=THEME["bg_main"],
        ).pack(side=tk.LEFT)

        self.time_label = tk.Label(
            param_header_frame,
            text="",
            font=(THEME["font_mono"], 8),
            fg=THEME["text_muted"],
            bg=THEME["bg_main"],
        )
        self.time_label.pack(side=tk.RIGHT)

        # Text area for formatted JSON parameters
        text_frame = tk.Frame(self.root, bg=THEME["border"], padx=1, pady=1)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        self.param_text = tk.Text(
            text_frame,
            font=(THEME["font_mono"], 10),
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            insertbackground=THEME["text_primary"],
            relief=tk.FLAT,
            padx=10,
            pady=8,
            wrap=tk.WORD,
        )
        scrollbar = tk.Scrollbar(text_frame, command=self.param_text.yview)
        self.param_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.param_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Queue Navigation (if multiple concurrent requests)
        self.nav_frame = tk.Frame(self.root, bg=THEME["bg_main"], padx=14, pady=2)
        self.nav_frame.pack(fill=tk.X)

        self.prev_btn = tk.Button(
            self.nav_frame,
            text="◀ Previous",
            font=(THEME["font_family"], 8),
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            activebackground=THEME["nav_btn_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._prev_request,
        )
        self.prev_btn.pack(side=tk.LEFT)

        self.next_btn = tk.Button(
            self.nav_frame,
            text="Next ▶",
            font=(THEME["font_family"], 8),
            bg=THEME["bg_input"],
            fg=THEME["text_primary"],
            activebackground=THEME["nav_btn_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=8,
            pady=2,
            command=self._next_request,
        )
        self.next_btn.pack(side=tk.LEFT, padx=4)

        self.timer_label = tk.Label(
            self.nav_frame,
            text="",
            font=(THEME["font_family"], 9),
            fg=THEME["accent"],
            bg=THEME["bg_main"],
        )
        self.timer_label.pack(side=tk.RIGHT)

        # Action Buttons bar
        self.actions_frame = tk.Frame(self.root, bg=THEME["bg_card"], padx=16, pady=12)
        self.actions_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Block Button
        self.block_btn = tk.Button(
            self.actions_frame,
            text="✕  BLOCK REQUEST",
            font=(THEME["font_family"], 11, "bold"),
            bg=THEME["block_btn"],
            fg="#ffffff",
            activebackground=THEME["block_btn_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._block_current,
        )
        self.block_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))

        # Allow Button
        self.allow_btn = tk.Button(
            self.actions_frame,
            text="✓  ALLOW REQUEST",
            font=(THEME["font_family"], 11, "bold"),
            bg=THEME["allow_btn"],
            fg="#ffffff",
            activebackground=THEME["allow_btn_hover"],
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._allow_current,
        )
        self.allow_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(8, 0))

    def add_request(self, request: MCPRequest):
        """Add a new incoming request to the queue and refresh UI."""
        # Check if already present
        for req in self.pending_requests:
            if req.request_id == request.request_id:
                return

        self.pending_requests.append(request)
        if len(self.pending_requests) == 1:
            self.current_index = 0
            self.remaining_seconds = self.default_timeout

        self._refresh_display()
        self._bring_to_front()
        self._start_timer()

    def _refresh_display(self):
        """Update window contents with currently selected pending request."""
        count = len(self.pending_requests)
        if count == 0:
            self._stop_timer()
            self.root.withdraw()
            return

        if self.current_index >= count:
            self.current_index = count - 1
        if self.current_index < 0:
            self.current_index = 0

        req = self.pending_requests[self.current_index]

        # Update queue indicator
        if count > 1:
            self.queue_label.config(text=f"Queue: {self.current_index + 1} of {count} pending")
            self.prev_btn.pack(side=tk.LEFT)
            self.next_btn.pack(side=tk.LEFT, padx=4)
        else:
            self.queue_label.config(text="")
            self.prev_btn.pack_forget()
            self.next_btn.pack_forget()

        # Client Badge
        client_name = req.client_type.value if hasattr(req.client_type, "value") else str(req.client_type)
        self.client_badge.config(text=f"Client: {client_name}")
        if "Web" in client_name:
            self.client_badge.config(bg=THEME["badge_web"])
        else:
            self.client_badge.config(bg=THEME["badge_desktop"])

        # Server Badge
        self.server_badge.config(text=f"Server: {req.server_name}")

        # Tool name
        self.tool_label.config(text=req.tool_name)

        # Time label
        req_time = time.strftime("%H:%M:%S", time.localtime(req.timestamp))
        self.time_label.config(text=f"Received: {req_time} (ID: {req.request_id[:8]})")

        # Arguments text
        self.param_text.config(state=tk.NORMAL)
        self.param_text.delete("1.0", tk.END)
        try:
            formatted_args = json.dumps(req.arguments, indent=2, ensure_ascii=False)
        except Exception:
            formatted_args = str(req.arguments)
        self.param_text.insert(tk.END, formatted_args)
        self.param_text.config(state=tk.DISABLED)

    def _start_timer(self):
        """Start countdown tick."""
        self._stop_timer()
        if self.default_timeout > 0:
            self._tick_timer()

    def _tick_timer(self):
        if not self.pending_requests:
            return

        self.timer_label.config(text=f"Auto-decision in {self.remaining_seconds}s")
        if self.remaining_seconds <= 0:
            # Timeout reached: default action is BLOCK for security
            self._timeout_current()
            return

        self.remaining_seconds -= 1
        self._timer_job = self.root.after(1000, self._tick_timer)

    def _stop_timer(self):
        if self._timer_job:
            try:
                self.root.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None
        self.timer_label.config(text="")

    def _prev_request(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._refresh_display()

    def _next_request(self):
        if self.current_index < len(self.pending_requests) - 1:
            self.current_index += 1
            self._refresh_display()

    def _resolve_current(self, status: RequestStatus, reason: str):
        if not self.pending_requests:
            return

        req = self.pending_requests.pop(self.current_index)
        decision = ApprovalDecision(
            request_id=req.request_id,
            status=status,
            reason=reason,
        )

        if self.on_decision:
            self.on_decision(decision)

        # Reset timer for next item in queue
        self.remaining_seconds = self.default_timeout
        self._refresh_display()

    def _allow_current(self):
        self._resolve_current(RequestStatus.ALLOWED, "Allowed by user via confirmation modal")

    def _block_current(self):
        self._resolve_current(RequestStatus.BLOCKED, "Blocked by user via confirmation modal")

    def _timeout_current(self):
        self._resolve_current(RequestStatus.TIMEOUT, f"Blocked automatically due to timeout ({self.default_timeout}s)")

    def _on_close_clicked(self):
        """Closing the window blocks all remaining requests for security."""
        while self.pending_requests:
            self._resolve_current(RequestStatus.BLOCKED, "Blocked: Confirmation window closed by user")


def run_standalone_dialog(request: MCPRequest, timeout: int = 60) -> ApprovalDecision:
    """Helper to run a self-contained modal loop for a single request (fallback mode)."""
    result = {"decision": ApprovalDecision(request_id=request.request_id, status=RequestStatus.BLOCKED, reason="Default block")}

    root = tk.Tk()

    def callback(dec: ApprovalDecision):
        result["decision"] = dec
        root.quit()

    modal = ConfirmationModal(root=root, on_decision=callback, default_timeout=timeout)
    modal.add_request(request)

    root.mainloop()
    try:
        root.destroy()
    except Exception:
        pass

    return result["decision"]
