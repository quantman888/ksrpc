#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

copy_if_missing() {
  local src="$1"
  local dest="$2"
  if [[ -f "${dest}" ]]; then
    echo "[bootstrap_runtime_files] keep ${dest}"
    return
  fi
  cp "${src}" "${dest}"
  echo "[bootstrap_runtime_files] created ${dest}"
}

copy_if_missing "${APP_DIR}/.env.example" "${APP_DIR}/.env"
copy_if_missing "${APP_DIR}/config_server.example.py" "${APP_DIR}/config_server.py"
