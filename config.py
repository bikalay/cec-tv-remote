#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class AppConfig:
    cec_dev: str
    phys_addr: str
    state_file: Path
    wayland_output: str
    mouse_base_step: int
    mouse_accel_factor: float
    mouse_max_step: int
    mouse_accel_window: float
    log_level: str


def _coerce_str(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def _coerce_int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _coerce_float(value: object, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def config_path_for() -> Path:
    configured = os.environ.get("CEC_REMOTE_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "cec-tv-remote" / "config.toml"


def load_app_config() -> AppConfig:
    config_path = config_path_for()
    raw: dict[str, object] = {}
    if config_path.exists():
        raw = tomllib.loads(config_path.read_text())

    cec = raw.get("cec", {})
    state = raw.get("state", {})
    wake = raw.get("wake", {})
    mouse = raw.get("mouse", {})
    logging_cfg = raw.get("logging", {})

    if not isinstance(cec, dict):
        cec = {}
    if not isinstance(state, dict):
        state = {}
    if not isinstance(wake, dict):
        wake = {}
    if not isinstance(mouse, dict):
        mouse = {}
    if not isinstance(logging_cfg, dict):
        logging_cfg = {}

    return AppConfig(
        cec_dev=_coerce_str(cec.get("device"), "/dev/cec1"),
        phys_addr=_coerce_str(cec.get("phys_addr"), "2.0.0.0"),
        state_file=Path(_coerce_str(state.get("file"), "/tmp/cec-remote-mode")),
        wayland_output=_coerce_str(wake.get("wayland_output"), "HDMI-A-1"),
        mouse_base_step=_coerce_int(mouse.get("base_step"), 20),
        mouse_accel_factor=_coerce_float(mouse.get("accel_factor"), 1.30),
        mouse_max_step=_coerce_int(mouse.get("max_step"), 180),
        mouse_accel_window=_coerce_float(mouse.get("accel_window"), 0.28),
        log_level=_coerce_str(logging_cfg.get("level"), "INFO").upper(),
    )


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )
