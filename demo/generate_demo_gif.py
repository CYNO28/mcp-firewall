"""Generate animated demonstration GIF and screenshots for README and deliverables."""

import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Dimensions
WIDTH, HEIGHT = 720, 560

# Palette
C_BG = (18, 20, 26)
C_CARD = (26, 29, 38)
C_INPUT = (34, 39, 54)
C_BORDER = (45, 51, 69)
C_TEXT = (248, 250, 252)
C_MUTED = (148, 163, 184)
C_AMBER = (245, 158, 11)
C_GREEN = (16, 185, 129)
C_GREEN_DARK = (5, 150, 105)
C_RED = (239, 68, 68)
C_RED_DARK = (220, 38, 38)
C_PURPLE = (139, 92, 246)
C_CYAN = (6, 182, 212)


def get_font(size=14, bold=False):
    try:
        font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            font_name = "arialbd.ttf" if bold else "arial.ttf"
            return ImageFont.truetype(font_name, size)
        except Exception:
            return ImageFont.load_default()


def get_mono_font(size=13):
    try:
        return ImageFont.truetype("consola.ttf", size)
    except Exception:
        return get_font(size)


def draw_window_frame(draw, title="MCP Firewall - Authorization Required"):
    # Outer background
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=C_BG)

    # Window titlebar
    draw.rectangle([0, 0, WIDTH, 36], fill=(22, 25, 34))
    draw.text((16, 9), f"🛡️  {title}", fill=C_MUTED, font=get_font(12, bold=True))

    # Window controls (close, min, max dots)
    draw.ellipse([WIDTH - 30, 12, WIDTH - 18, 24], fill=(239, 68, 68))
    draw.ellipse([WIDTH - 50, 12, WIDTH - 38, 24], fill=(245, 158, 11))
    draw.ellipse([WIDTH - 70, 12, WIDTH - 58, 24], fill=(16, 185, 129))


def draw_popup_state(
    client_name: str,
    client_color: tuple,
    server_name: str,
    tool_name: str,
    params: dict,
    queue_text: str = "",
    timer_text: str = "Auto-decision in 54s",
    highlight_btn: str = None,  # "ALLOW" or "BLOCK"
    banner_alert: str = None,
):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_BG)
    draw = ImageDraw.Draw(img)
    draw_window_frame(draw)

    # Header Card
    draw.rectangle([16, 50, WIDTH - 16, 106], fill=C_CARD, outline=C_BORDER)
    draw.text((32, 60), "⚠️  MCP Tool Execution Request", fill=C_AMBER, font=get_font(15, bold=True))
    draw.text((32, 82), "An application is requesting to execute a local or remote tool via MCP.", fill=C_MUTED, font=get_font(11))

    if queue_text:
        draw.text((WIDTH - 200, 64), queue_text, fill=C_AMBER, font=get_font(12, bold=True))

    # Meta Badges Card
    draw.rectangle([16, 118, WIDTH - 16, 190], fill=C_CARD, outline=C_BORDER)

    # Client badge
    draw.rounded_rectangle([32, 130, 220, 156], radius=4, fill=client_color)
    draw.text((40, 134), f"Client: {client_name}", fill=(255, 255, 255), font=get_font(11, bold=True))

    # Server badge
    draw.rounded_rectangle([230, 130, 390, 156], radius=4, fill=C_INPUT, outline=C_BORDER)
    draw.text((240, 134), f"Server: {server_name}", fill=C_TEXT, font=get_font(11, bold=True))

    # Tool Name
    draw.text((32, 165), "Tool Requested:", fill=C_MUTED, font=get_font(12))
    draw.text((135, 163), tool_name, fill=C_AMBER, font=get_mono_font(14))

    # Parameters header & box
    draw.text((20, 204), "Parameters & Payload", fill=C_TEXT, font=get_font(12, bold=True))
    draw.text((WIDTH - 180, 204), timer_text, fill=C_AMBER, font=get_font(11))

    draw.rectangle([16, 226, WIDTH - 16, 460], fill=C_INPUT, outline=C_BORDER)
    json_lines = json.dumps(params, indent=2).split("\n")
    y = 240
    for line in json_lines[:12]:
        draw.text((32, y), line, fill=C_TEXT, font=get_mono_font(12))
        y += 18

    # Bottom Actions Bar
    draw.rectangle([16, 474, WIDTH - 16, 544], fill=C_CARD, outline=C_BORDER)

    # Block Button
    block_bg = C_RED_DARK if highlight_btn == "BLOCK" else C_RED
    draw.rounded_rectangle([32, 486, 340, 532], radius=6, fill=block_bg)
    draw.text((130, 498), "✕  BLOCK REQUEST", fill=(255, 255, 255), font=get_font(13, bold=True))

    # Allow Button
    allow_bg = C_GREEN_DARK if highlight_btn == "ALLOW" else C_GREEN
    draw.rounded_rectangle([380, 486, WIDTH - 32, 532], radius=6, fill=allow_bg)
    draw.text((485, 498), "✓  ALLOW REQUEST", fill=(255, 255, 255), font=get_font(13, bold=True))

    # If banner alert overlay (e.g. APPROVED or BLOCKED splash)
    if banner_alert:
        is_allow = "ALLOWED" in banner_alert
        banner_color = C_GREEN if is_allow else C_RED
        draw.rectangle([0, HEIGHT // 2 - 35, WIDTH, HEIGHT // 2 + 35], fill=(10, 12, 16))
        draw.rectangle([0, HEIGHT // 2 - 35, WIDTH, HEIGHT // 2 - 32], fill=banner_color)
        draw.rectangle([0, HEIGHT // 2 + 32, WIDTH, HEIGHT // 2 + 35], fill=banner_color)
        draw.text((WIDTH // 2 - 180, HEIGHT // 2 - 12), banner_alert, fill=banner_color, font=get_font(16, bold=True))

    return img


def generate_all_assets():
    frames = []

    # Sequence 1: Claude Desktop calls read_file -> ALLOW
    f1 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="filesystem",
        tool_name="read_file",
        params={"path": "C:/Projects/financial_report.pdf", "encoding": "utf-8"},
        timer_text="Auto-decision in 58s",
    )
    for _ in range(6):
        frames.append(f1)

    f2 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="filesystem",
        tool_name="read_file",
        params={"path": "C:/Projects/financial_report.pdf", "encoding": "utf-8"},
        highlight_btn="ALLOW",
    )
    for _ in range(3):
        frames.append(f2)

    f3 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="filesystem",
        tool_name="read_file",
        params={"path": "C:/Projects/financial_report.pdf"},
        banner_alert="✓ REQUEST ALLOWED: Released to MCP Server",
    )
    for _ in range(6):
        frames.append(f3)

    # Sequence 2: Claude Desktop calls delete_database -> BLOCK
    f4 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="production-db",
        tool_name="delete_database",
        params={"database_name": "prod_users_2026", "drop_all_tables": True, "cascade": True},
        timer_text="Auto-decision in 55s",
    )
    for _ in range(6):
        frames.append(f4)

    f5 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="production-db",
        tool_name="delete_database",
        params={"database_name": "prod_users_2026", "drop_all_tables": True, "cascade": True},
        highlight_btn="BLOCK",
    )
    for _ in range(3):
        frames.append(f5)

    f6 = draw_popup_state(
        client_name="Claude Desktop",
        client_color=C_PURPLE,
        server_name="production-db",
        tool_name="delete_database",
        params={"database_name": "prod_users_2026"},
        banner_alert="🚫 REQUEST BLOCKED: Database Untouched & Safe",
    )
    for _ in range(7):
        frames.append(f6)

    # Sequence 3: Claude Web calls execute_shell_command via HTTP/SSE
    f7 = draw_popup_state(
        client_name="Claude Web (HTTP/SSE)",
        client_color=C_CYAN,
        server_name="claude-web-gateway",
        tool_name="execute_shell_command",
        params={"command": "rm -rf /var/www/html/backup.tar.gz", "timeout": 30},
        timer_text="Auto-decision in 52s",
    )
    for _ in range(6):
        frames.append(f7)

    # Sequence 4: Concurrent Requests Queue
    f8 = draw_popup_state(
        client_name="Claude Web (HTTP/SSE)",
        client_color=C_CYAN,
        server_name="multi-tenant-gateway",
        tool_name="transfer_funds",
        params={"account_id": "ACC-99201", "amount": 50000.0, "currency": "USD"},
        queue_text="Queue: 1 of 2 pending",
        timer_text="Auto-decision in 48s",
    )
    for _ in range(6):
        frames.append(f8)

    # Save animated GIF
    gif_path = ASSETS_DIR / "demo.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=350,
        loop=0,
    )
    print(f"[OK] Saved animated demonstration GIF to: {gif_path}")

    # Also save static screenshots for markdown
    f1.save(ASSETS_DIR / "screenshot_allow.png")
    f4.save(ASSETS_DIR / "screenshot_block.png")
    f8.save(ASSETS_DIR / "screenshot_queue.png")
    print(f"[OK] Saved screenshots to: {ASSETS_DIR}")


if __name__ == "__main__":
    generate_all_assets()
