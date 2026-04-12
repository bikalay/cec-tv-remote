#!/usr/bin/env python3
import threading
import time

import pystray
from PIL import Image, ImageDraw

from config import load_app_config

CONFIG = load_app_config()


def make_icon(bg: str, fg: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=bg)
    d.ellipse((20, 20, 44, 44), fill=fg)
    return img


ICONS = {
    "mouse": make_icon("#2e7d32", "#a5d6a7"),
    "keyboard": make_icon("#1565c0", "#90caf9"),
    "unknown": make_icon("#616161", "#bdbdbd"),
}


def read_mode() -> str:
    try:
        value = CONFIG.state_file.read_text().strip()
        if value in ("mouse", "keyboard"):
            return value
    except Exception:
        pass
    return "unknown"


def mode_text(mode: str) -> str:
    if mode == "mouse":
        return "CEC mode: mouse"
    if mode == "keyboard":
        return "CEC mode: keyboard"
    return "CEC mode: unknown"


def on_quit(icon: pystray.Icon, item) -> None:
    icon.stop()


def setup(icon: pystray.Icon) -> None:
    icon.visible = True

    def poll() -> None:
        last_mode = None
        while True:
            mode = read_mode()
            if mode != last_mode:
                icon.icon = ICONS[mode]
                icon.title = mode_text(mode)
                icon.update_menu()
                last_mode = mode
            time.sleep(0.4)

    threading.Thread(target=poll, daemon=True).start()


icon = pystray.Icon(
    "cec-mode",
    icon=ICONS["unknown"],
    title="CEC mode: unknown",
    menu=pystray.Menu(
        pystray.MenuItem("Quit", on_quit),
    ),
)

icon.run(setup=setup)
