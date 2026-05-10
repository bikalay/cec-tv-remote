#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-manual}"
STAGE="$(mktemp -d)"
PAYLOAD_DIR="${STAGE}/cec-tv-remote"
OUTPUT_RUN="${ROOT_DIR}/cec-tv-remote-${VERSION}.run"

cleanup() {
  rm -rf "${STAGE}"
}

trap cleanup EXIT

mkdir -p "${PAYLOAD_DIR}/packaging"
mkdir -p "${PAYLOAD_DIR}/assets"

cp -a "${ROOT_DIR}/cec_remote.py" "${PAYLOAD_DIR}/cec_remote.py"
cp -a "${ROOT_DIR}/cec_tray.py" "${PAYLOAD_DIR}/cec_tray.py"
cp -a "${ROOT_DIR}/config.py" "${PAYLOAD_DIR}/config.py"
cp -a "${ROOT_DIR}/assets/mouse.png" "${PAYLOAD_DIR}/assets/mouse.png"
cp -a "${ROOT_DIR}/assets/keyboard.png" "${PAYLOAD_DIR}/assets/keyboard.png"
cp -a "${ROOT_DIR}/requirements.txt" "${PAYLOAD_DIR}/requirements.txt"
cp -a "${ROOT_DIR}/README.md" "${PAYLOAD_DIR}/README.md"
cp -a "${ROOT_DIR}/install.sh" "${PAYLOAD_DIR}/install.sh"
cp -a "${ROOT_DIR}/installer_entrypoint.sh" "${PAYLOAD_DIR}/installer_entrypoint.sh"
cp -a "${ROOT_DIR}/packaging/cec-remote.service.in" "${PAYLOAD_DIR}/packaging/cec-remote.service.in"
cp -a "${ROOT_DIR}/packaging/cec-tray.desktop.in" "${PAYLOAD_DIR}/packaging/cec-tray.desktop.in"
cp -a "${ROOT_DIR}/packaging/config.toml.in" "${PAYLOAD_DIR}/packaging/config.toml.in"

chmod +x "${PAYLOAD_DIR}/install.sh" "${PAYLOAD_DIR}/installer_entrypoint.sh"
rm -f "${OUTPUT_RUN}"

makeself \
  --nox11 \
  --sha256 \
  "${PAYLOAD_DIR}" \
  "${OUTPUT_RUN}" \
  "CEC TV Remote Installer (${VERSION})" \
  ./installer_entrypoint.sh

chmod +x "${OUTPUT_RUN}"

printf 'Created: %s\n' "${OUTPUT_RUN}"
