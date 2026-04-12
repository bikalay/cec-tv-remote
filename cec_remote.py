#!/usr/bin/env python3
from __future__ import annotations

import logging
import subprocess
import threading
import time

from evdev import UInput, ecodes as e

from config import AppConfig, configure_logging, load_app_config

LOGGER = logging.getLogger("cec_remote")

IDLE_REACTIVATE_SECS = 8
DOUBLE_SELECT_WINDOW = 0.35
LONG_SELECT_SECS = 0.65

DIR_TO_KEY = {
    "up": e.KEY_UP,
    "down": e.KEY_DOWN,
    "left": e.KEY_LEFT,
    "right": e.KEY_RIGHT,
}

CONFIG: AppConfig
mouse_ui: UInput
key_ui: UInput

last_event_ts = time.monotonic()
last_activate_ts = 0.0
lock = threading.Lock()

current_pressed_cmd = None
select_press_ts = None
select_click_ts = None

mode = "mouse"

last_move_cmd = None
last_move_ts = 0.0
move_streak = 0

pending_user_control_press = False
standby_suppressed = False


def run_cmd(args: list[str]) -> None:
    subprocess.run(
        args,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def write_mode_state() -> None:
    try:
        CONFIG.state_file.write_text(mode + "\n")
    except Exception:
        LOGGER.exception("Failed to write mode state to %s", CONFIG.state_file)


def configure_cec() -> None:
    run_cmd(["/usr/bin/cec-ctl", "-d", CONFIG.cec_dev, "--clear"])
    run_cmd(
        [
            "/usr/bin/cec-ctl",
            "-d",
            CONFIG.cec_dev,
            "--playback",
            "--no-rc-passthrough",
            "--osd-name",
            "RaspberryPi",
        ]
    )


def wake_video_output() -> None:
    # Best effort for Raspberry Pi and similar Linux setups where the
    # video pipeline blanks after inactivity.
    run_cmd(["/usr/bin/vcgencmd", "display_power", "1"])
    run_cmd(["/usr/bin/tvservice", "-p"])


def activate_source(force: bool = False) -> None:
    global last_activate_ts

    with lock:
        now = time.monotonic()
        if not force and now - last_activate_ts < 2:
            return

        last_activate_ts = now

        run_cmd(
            [
                "/usr/bin/cec-ctl",
                "-d",
                CONFIG.cec_dev,
                "--active-source",
                f"phys-addr={CONFIG.phys_addr}",
            ]
        )
        time.sleep(0.25)
        run_cmd(
            [
                "/usr/bin/cec-ctl",
                "-d",
                CONFIG.cec_dev,
                "--to",
                "0",
                "--image-view-on",
            ]
        )


def mouse_move(dx: int, dy: int) -> None:
    if dx:
        mouse_ui.write(e.EV_REL, e.REL_X, dx)
    if dy:
        mouse_ui.write(e.EV_REL, e.REL_Y, dy)
    mouse_ui.syn()


def mouse_click(button: int) -> None:
    mouse_ui.write(e.EV_KEY, button, 1)
    mouse_ui.syn()
    mouse_ui.write(e.EV_KEY, button, 0)
    mouse_ui.syn()


def mouse_double_click(button: int) -> None:
    mouse_click(button)
    time.sleep(0.05)
    mouse_click(button)


def tap_key(key_code: int) -> None:
    key_ui.write(e.EV_KEY, key_code, 1)
    key_ui.syn()
    key_ui.write(e.EV_KEY, key_code, 0)
    key_ui.syn()


def reset_mouse_accel() -> None:
    global last_move_cmd, last_move_ts, move_streak
    last_move_cmd = None
    last_move_ts = 0.0
    move_streak = 0


def next_mouse_step(cmd: str) -> int:
    global last_move_cmd, last_move_ts, move_streak

    now = time.monotonic()

    if cmd == last_move_cmd and (now - last_move_ts) <= CONFIG.mouse_accel_window:
        move_streak += 1
    else:
        move_streak = 1

    last_move_cmd = cmd
    last_move_ts = now

    step = int(CONFIG.mouse_base_step * (CONFIG.mouse_accel_factor ** (move_streak - 1)))
    return min(step, CONFIG.mouse_max_step)


def move_mouse_for_cmd(cmd: str) -> None:
    step = next_mouse_step(cmd)

    if cmd == "up":
        mouse_move(0, -step)
    elif cmd == "down":
        mouse_move(0, step)
    elif cmd == "left":
        mouse_move(-step, 0)
    elif cmd == "right":
        mouse_move(step, 0)


def toggle_mode() -> None:
    global mode
    mode = "keyboard" if mode == "mouse" else "mouse"
    write_mode_state()
    reset_mouse_accel()
    LOGGER.info("Input mode switched to %s", mode)


def delayed_single_select(expected_ts: float) -> None:
    global select_click_ts
    time.sleep(DOUBLE_SELECT_WINDOW)

    with lock:
        if select_click_ts == expected_ts and mode == "mouse":
            mouse_click(e.BTN_LEFT)
            select_click_ts = None


def handle_select_press() -> None:
    global select_press_ts
    select_press_ts = time.monotonic()
    reset_mouse_accel()


def handle_select_release() -> None:
    global select_press_ts, select_click_ts

    if select_press_ts is None:
        return

    duration = time.monotonic() - select_press_ts
    select_press_ts = None

    if duration >= LONG_SELECT_SECS:
        toggle_mode()
        select_click_ts = None
        return

    if mode == "keyboard":
        tap_key(e.KEY_ENTER)
        return

    now = time.monotonic()
    with lock:
        if select_click_ts is not None and (now - select_click_ts) <= DOUBLE_SELECT_WINDOW:
            mouse_double_click(e.BTN_LEFT)
            select_click_ts = None
            return

        select_click_ts = now
        threading.Thread(
            target=delayed_single_select,
            args=(now,),
            daemon=True,
        ).start()


def handle_back_release() -> None:
    reset_mouse_accel()
    if mode == "keyboard":
        tap_key(e.KEY_ESC)
    else:
        mouse_click(e.BTN_RIGHT)


def handle_direction_press(cmd: str) -> None:
    if mode == "keyboard":
        tap_key(DIR_TO_KEY[cmd])
    else:
        move_mouse_for_cmd(cmd)


def watchdog() -> None:
    global last_event_ts

    while True:
        time.sleep(2)
        idle = time.monotonic() - last_event_ts
        if idle > IDLE_REACTIVATE_SECS and not standby_suppressed:
            configure_cec()
            activate_source()
            last_event_ts = time.monotonic()
            reset_mouse_accel()


def handle_pressed_cmd(cmd: str) -> None:
    global current_pressed_cmd
    current_pressed_cmd = cmd
    wake_video_output()
    activate_source()

    if cmd in {"up", "down", "left", "right"}:
        handle_direction_press(cmd)
    elif cmd == "select":
        handle_select_press()
    elif cmd == "back":
        pass


def handle_released_cmd() -> None:
    global current_pressed_cmd

    cmd = current_pressed_cmd
    current_pressed_cmd = None

    if cmd == "select":
        handle_select_release()
    elif cmd == "back":
        handle_back_release()


def handle_line(line: str) -> None:
    global last_event_ts, pending_user_control_press, standby_suppressed

    raw_line = line.rstrip()
    if raw_line and LOGGER.isEnabledFor(logging.DEBUG):
        LOGGER.debug("CEC line: %s", raw_line)

    line = raw_line.strip()
    if not line:
        return

    if (
        "USER_CONTROL_PRESSED" in line
        or "USER_CONTROL_RELEASED" in line
        or "SET_STREAM_PATH" in line
        or "ROUTING_CHANGE" in line
        or "ACTIVE_SOURCE" in line
    ):
        last_event_ts = time.monotonic()

    if "STANDBY" in line:
        standby_suppressed = True
        pending_user_control_press = False
        reset_mouse_accel()
        return

    if "SET_STREAM_PATH" in line and f"phys-addr: {CONFIG.phys_addr}" in line:
        standby_suppressed = False
        time.sleep(0.4)
        wake_video_output()
        configure_cec()
        activate_source()
        reset_mouse_accel()
        pending_user_control_press = False
        return

    if "ROUTING_CHANGE" in line and f"new-phys-addr: {CONFIG.phys_addr}" in line:
        standby_suppressed = False
        time.sleep(0.4)
        wake_video_output()
        configure_cec()
        activate_source()
        reset_mouse_accel()
        pending_user_control_press = False
        return

    if "USER_CONTROL_PRESSED" in line:
        pending_user_control_press = True
        return

    if pending_user_control_press and "ui-cmd:" in line:
        cmd = line.split("ui-cmd:", 1)[1].strip().split()[0].lower()
        pending_user_control_press = False
        LOGGER.info("Received CEC command: %s", cmd)
        handle_pressed_cmd(cmd)
        return

    if "USER_CONTROL_RELEASED" in line:
        pending_user_control_press = False
        handle_released_cmd()
        return


def initialize_inputs() -> None:
    global mouse_ui, key_ui

    mouse_ui = UInput(
        {
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT],
            e.EV_REL: [e.REL_X, e.REL_Y],
        },
        name="CEC TV Remote Mouse",
    )

    key_ui = UInput(
        {
            e.EV_KEY: [
                e.KEY_UP,
                e.KEY_DOWN,
                e.KEY_LEFT,
                e.KEY_RIGHT,
                e.KEY_ENTER,
                e.KEY_ESC,
            ],
        },
        name="CEC TV Remote Keys",
    )


def main() -> None:
    global CONFIG, last_event_ts, mode, pending_user_control_press, standby_suppressed

    CONFIG = load_app_config()
    configure_logging(CONFIG.log_level)
    LOGGER.info(
        "Loaded config: cec_dev=%s phys_addr=%s state_file=%s mouse_base_step=%s mouse_accel_factor=%s mouse_max_step=%s mouse_accel_window=%s log_level=%s",
        CONFIG.cec_dev,
        CONFIG.phys_addr,
        CONFIG.state_file,
        CONFIG.mouse_base_step,
        CONFIG.mouse_accel_factor,
        CONFIG.mouse_max_step,
        CONFIG.mouse_accel_window,
        CONFIG.log_level,
    )

    initialize_inputs()

    mode = "mouse"
    pending_user_control_press = False
    standby_suppressed = False
    write_mode_state()

    wake_video_output()
    configure_cec()
    activate_source(force=True)
    last_event_ts = time.monotonic()

    threading.Thread(target=watchdog, daemon=True).start()

    proc = subprocess.Popen(
        ["/usr/bin/cec-ctl", "-d", CONFIG.cec_dev, "--monitor"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None

    for line in proc.stdout:
        handle_line(line)

    raise RuntimeError("cec-ctl monitor exited unexpectedly")


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            break
        except Exception:
            LOGGER.exception("cec_remote crashed; restarting in 1 second")
            time.sleep(1)
