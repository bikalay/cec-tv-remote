#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -eq 0 ]]; then
  exec "${SCRIPT_DIR}/install.sh" "$@"
fi

if command -v pkexec >/dev/null 2>&1; then
  exec pkexec "${SCRIPT_DIR}/install.sh" "$@"
fi

if command -v sudo >/dev/null 2>&1; then
  exec sudo "${SCRIPT_DIR}/install.sh" "$@"
fi

printf 'This installer needs root privileges.\n' >&2
printf 'Run: sudo ./install.sh\n' >&2
exit 1
