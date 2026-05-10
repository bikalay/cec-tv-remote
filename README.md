# CEC TV Remote

`cec-tv-remote` lets a TV remote control a Linux machine over HDMI-CEC.

It is built for Raspberry Pi, but it may also work on other Linux systems that expose a usable CEC device such as `/dev/cec1`.

## What It Does

- listens to HDMI-CEC remote events with `cec-ctl`
- exposes directional input as either mouse movement or keyboard arrows
- maps `select` to left click or `Enter`
- maps `back` to right click or `Esc`
- automatically re-activates the Pi as the active HDMI source after idle periods
- optionally runs a small tray app that shows the current input mode

## Modes

The remote works in two modes:

- `mouse` mode: arrows move the pointer, `select` clicks, `back` right-clicks
- `keyboard` mode: arrows send arrow keys, `select` sends `Enter`, `back` sends `Esc`

Mode switching:

- short `select`: normal action
- double `select` in mouse mode: double click
- long `select`: toggle between mouse and keyboard mode

## Requirements

- Linux
- Python 3
- `cec-utils` with `cec-ctl`
- systemd for the service install
- a CEC-capable HDMI setup

For the tray app:

- a desktop session
- `pystray`
- Pillow

## Installation

The repository includes an install script that:

- installs OS packages with `apt` when available
- copies the app into `/opt/cec-tv-remote`
- creates `~/.config/cec-tv-remote/config.toml` for the selected install user
- creates a Python virtual environment
- installs Python dependencies
- installs and starts a systemd service
- optionally installs a desktop autostart entry for the tray app

### Install From Self-Extracting Installer

Download the `.run` release and execute it:

```bash
chmod +x cec-tv-remote-<version>.run
./cec-tv-remote-<version>.run --user pi
```

The `.run` package extracts the payload and starts the installer automatically. If root privileges are required, it tries `pkexec` first and then `sudo`.

### Install From Release Archive

1. Download `cec-tv-remote-<version>.tar.gz` from GitHub Releases.
2. Extract it on the target machine.
3. Run:

```bash
tar -xzf cec-tv-remote-<version>.tar.gz
cd cec-tv-remote
sudo ./install.sh
```

### Install From Source

```bash
git clone <your-repo-url>
cd cec-tv-remote
sudo ./install.sh
```

### Installer Options

- `--user <name>`: install the service and tray for a specific Linux user
- `--install-dir <path>`: change the default install path
- `--no-tray`: skip installing the tray autostart entry
- `--skip-deps`: skip `apt-get` package installation
- `-h`, `--help`: show help

Example:

```bash
sudo ./install.sh --user pi
```

## Installed Files

- app files: `/opt/cec-tv-remote`
- Python virtualenv: `/opt/cec-tv-remote/.venv`
- systemd service: `/etc/systemd/system/cec-tv-remote.service`
- user config: `~/.config/cec-tv-remote/config.toml`
- tray autostart: `~/.config/autostart/cec-tray.desktop`

## Service Management

After installation:

```bash
systemctl status cec-tv-remote.service
systemctl restart cec-tv-remote.service
journalctl -u cec-tv-remote.service -f
```

## Configuration

Runtime configuration is stored in:

```bash
~/.config/cec-tv-remote/config.toml
```

Default contents:

```toml
[cec]
device = "/dev/cec1"
phys_addr = "2.0.0.0"

[state]
file = "/tmp/cec-remote-mode"

[wake]
wayland_output = "HDMI-A-1"

[mouse]
base_step = 42
accel_factor = 1.30
max_step = 180
accel_window = 0.28

[logging]
level = "INFO"
```

Supported settings:

- `cec.device`: CEC device path, for example `/dev/cec1`
- `cec.phys_addr`: HDMI physical address used for active-source handling
- `state.file`: file used to share the current mode between the service and tray app
- `wake.wayland_output`: Wayland output name used for `wlr-randr --output <name> --on`
- `mouse.base_step`: initial cursor movement step
- `mouse.accel_factor`: movement acceleration multiplier for repeated directional presses
- `mouse.max_step`: maximum cursor movement step
- `mouse.accel_window`: time window in seconds for chaining accelerated movement
- `logging.level`: log level for the service, such as `INFO` or `DEBUG`

For raw CEC debugging, set:

```toml
[logging]
level = "DEBUG"
```

Then restart the service and follow journald:

```bash
sudo systemctl restart cec-tv-remote.service
sudo journalctl -u cec-tv-remote.service -f
```

At `DEBUG` level, the service logs every received line from `cec-ctl --monitor`.

## Repository Layout

- `cec_remote.py`: main HDMI-CEC to input bridge
- `cec_tray.py`: tray icon that shows the current mode
- `config.py`: shared config loader and logging setup
- `install.sh`: installer
- `requirements.txt`: Python dependencies
- `packaging/`: service and desktop entry templates
- `.github/workflows/build-install-archive.yml`: archive build workflow

## Building Release Archives

GitHub Actions builds an install archive on:

- manual workflow runs
- pushed tags matching `v*`

To create a release archive:

```bash
git tag v1.0.0
git push origin v1.0.0
```

That workflow produces:

- a workflow artifact with `cec-tv-remote-v1.0.0.tar.gz`
- a self-extracting installer `cec-tv-remote-v1.0.0.run`
- a GitHub Release attachment for tag builds

## Notes

- the installer is currently optimized for Debian-based systems such as Raspberry Pi OS
- on non-Debian Linux distributions, use `--skip-deps` and install the required packages manually
- the tray app is optional and mainly useful on desktop systems, not headless installs
- the system service runs as root so it can access `/dev/uinput` and other device nodes needed for virtual input injection
