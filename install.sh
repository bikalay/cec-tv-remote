#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/cec-tv-remote"
SERVICE_NAME="cec-tv-remote.service"
RUN_USER=""
RUN_HOME=""
INSTALL_TRAY=1
INSTALL_DEPS=1

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh [options]

Options:
  --install-dir PATH   Install application into PATH (default: /opt/cec-tv-remote)
  --user NAME          Linux user that should run the service and own tray autostart
  --no-tray            Skip desktop autostart installation
  --skip-deps          Skip apt dependency installation
  -h, --help           Show this help
EOF
}

log() {
  printf '[install] %s\n' "$*"
}

fail() {
  printf '[install] ERROR: %s\n' "$*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    fail "run this script with sudo or as root"
  fi
}

detect_default_user() {
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    printf '%s\n' "${SUDO_USER}"
    return
  fi

  if [[ -n "${PKEXEC_UID:-}" ]]; then
    getent passwd "${PKEXEC_UID}" | cut -d: -f1
    return
  fi

  fail "could not detect target user, pass --user explicitly"
}

lookup_home() {
  local user="$1"
  getent passwd "${user}" | cut -d: -f6
}

install_apt_deps() {
  if ! command -v apt-get >/dev/null 2>&1; then
    log "apt-get not found, skipping OS package install"
    return
  fi

  export DEBIAN_FRONTEND=noninteractive
  log "installing apt packages"
  apt-get update
  apt-get install -y \
    cec-utils \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libevdev-dev \
    libusb-1.0-0-dev \
    python3-tk
}

sync_app_files() {
  log "copying application files into ${INSTALL_DIR}"
  install -d -m 0755 "${INSTALL_DIR}"
  install -m 0644 "${SCRIPT_DIR}/cec_remote.py" "${INSTALL_DIR}/cec_remote.py"
  install -m 0644 "${SCRIPT_DIR}/cec_tray.py" "${INSTALL_DIR}/cec_tray.py"
  install -m 0644 "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/requirements.txt"
  install -d -m 0755 "${INSTALL_DIR}/packaging"
  install -m 0644 "${SCRIPT_DIR}/packaging/cec-remote.service.in" "${INSTALL_DIR}/packaging/cec-remote.service.in"
  install -m 0644 "${SCRIPT_DIR}/packaging/cec-tray.desktop.in" "${INSTALL_DIR}/packaging/cec-tray.desktop.in"
}

setup_venv() {
  log "creating virtual environment"
  python3 -m venv "${INSTALL_DIR}/.venv"
  "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip
  "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
}

fix_permissions() {
  log "normalizing install permissions"
  chmod -R a+rX "${INSTALL_DIR}"
  chmod a+rx "${INSTALL_DIR}/.venv/bin/python" "${INSTALL_DIR}/.venv/bin/pip"
}

install_service() {
  local service_path="/etc/systemd/system/${SERVICE_NAME}"

  log "installing systemd service"
  sed \
    -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
    -e "s|__RUN_USER__|${RUN_USER}|g" \
    "${INSTALL_DIR}/packaging/cec-remote.service.in" > "${service_path}"

  systemctl daemon-reload
  systemctl enable --now "${SERVICE_NAME}"
}

install_tray_autostart() {
  local autostart_dir="${RUN_HOME}/.config/autostart"
  local desktop_path="${autostart_dir}/cec-tray.desktop"
  local run_group

  run_group="$(id -gn "${RUN_USER}")"

  log "installing tray autostart for ${RUN_USER}"
  install -d -o "${RUN_USER}" -g "${run_group}" -m 0755 "${autostart_dir}"
  sed \
    -e "s|__INSTALL_DIR__|${INSTALL_DIR}|g" \
    "${INSTALL_DIR}/packaging/cec-tray.desktop.in" > "${desktop_path}"
  chown "${RUN_USER}:${run_group}" "${desktop_path}"
  chmod 0644 "${desktop_path}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-dir)
        INSTALL_DIR="$2"
        shift 2
        ;;
      --user)
        RUN_USER="$2"
        shift 2
        ;;
      --no-tray)
        INSTALL_TRAY=0
        shift
        ;;
      --skip-deps)
        INSTALL_DEPS=0
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

main() {
  parse_args "$@"
  require_root

  if [[ -z "${RUN_USER}" ]]; then
    RUN_USER="$(detect_default_user)"
  fi

  RUN_HOME="$(lookup_home "${RUN_USER}")"
  [[ -n "${RUN_HOME}" ]] || fail "could not resolve home directory for ${RUN_USER}"

  if [[ "${INSTALL_DEPS}" -eq 1 ]]; then
    install_apt_deps
  fi

  sync_app_files
  setup_venv
  fix_permissions
  install_service

  if [[ "${INSTALL_TRAY}" -eq 1 ]]; then
    install_tray_autostart
  fi

  log "installation complete"
  log "service status: systemctl status ${SERVICE_NAME}"
}

main "$@"
