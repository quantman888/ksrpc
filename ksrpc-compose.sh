#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

ACTION="${1:-start}"

case "${ACTION}" in
  start|restart|up)
    docker compose --env-file .env -f docker-compose.yml up -d --build --remove-orphans --force-recreate
    ;;
  clean)
    docker compose --env-file .env -f docker-compose.yml down -v --remove-orphans
    ;;
  *)
    echo "Usage: bash ./ksrpc-compose.sh [start|restart|clean]"
    exit 1
    ;;
esac
