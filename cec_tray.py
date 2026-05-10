#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from pathlib import Path
import threading
import time

LOG_DIR = Path.home() / ".cache" / "cec-tv-remote"
LOG_FILE = LOG_DIR / "cec-tray.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("cec_tray")

if not os.environ.get("DISPLAY"):
    os.environ["DISPLAY"] = ":0"

xauthority = Path.home() / ".Xauthority"
if not os.environ.get("XAUTHORITY") and xauthority.exists():
    os.environ["XAUTHORITY"] = str(xauthority)

import pystray # type: ignore[import]
from PIL import Image, ImageDraw # type: ignore[import]

from config import load_app_config

CONFIG = load_app_config()
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def make_icon(bg: str, fg: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=bg)
    d.ellipse((20, 20, 44, 44), fill=fg)
    return img


def load_icon(name: str) -> Image.Image:
    path = ASSETS_DIR / name
    with Image.open(path) as img:
        return img.convert("RGBA")


ICONS = {
    "mouse": load_icon("mouse.png"),
    "keyboard": load_icon("keyboard.png"),
    "unknown": make_icon("#616161", "#bdbdbd"),
}


def read_mode() -> str:
    try:
        value = CONFIG.state_file.read_text().strip()
        if value in ("mouse", "keyboard"):
            return value
    except Exception:
        LOGGER.exception("Failed to read mode from %s", CONFIG.state_file)
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
    LOGGER.info(
        "Starting tray: display=%s xauthority=%s state_file=%s",
        os.environ.get("DISPLAY", ""),
        os.environ.get("XAUTHORITY", ""),
        CONFIG.state_file,
    )
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

try:
    icon.run(setup=setup)
except Exception:
    LOGGER.exception("Tray startup failed")
    raise
