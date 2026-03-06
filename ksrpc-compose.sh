#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
if [[ -z "${ACTION}" ]]; then
  echo "Usage: bash ./ksrpc-compose.sh <generate|start|stop|restart|status|clean> [options]"
  exit 1
fi
shift || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}"

COMPOSE_FILE="${APP_DIR}/docker-compose.multi.yml"
ENV_FILE="${APP_DIR}/.env"
INSTANCES=""
IMAGE_OVERRIDE=""
FORCE_BUILD="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--instances)
      INSTANCES="$2"
      shift 2
      ;;
    -f|--compose-file)
      COMPOSE_FILE="$2"
      shift 2
      ;;
    -e|--env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --image)
      IMAGE_OVERRIDE="$2"
      shift 2
      ;;
    --build)
      FORCE_BUILD="1"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "env file not found: ${ENV_FILE}"
  exit 1
fi

mkdir -p "$(dirname "${COMPOSE_FILE}")"

read_env_from_file() {
  local key="$1"
  local file="$2"
  local default="$3"
  local line value
  line="$(grep -E "^${key}=" "${file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    echo "${default}"
    return
  fi
  value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  if [[ -z "${value}" ]]; then
    echo "${default}"
  else
    echo "${value}"
  fi
}

INSTANCES="${INSTANCES:-${KSRPC_INSTANCES:-$(read_env_from_file KSRPC_INSTANCES "${ENV_FILE}" 1)}}"
START_PORT="${KSRPC_HOST_PORT:-$(read_env_from_file KSRPC_HOST_PORT "${ENV_FILE}" 18080)}"
BASE_CONTAINER_NAME="${KSRPC_CONTAINER_NAME:-$(read_env_from_file KSRPC_CONTAINER_NAME "${ENV_FILE}" ksrpc)}"
MULTI_PROJECT_NAME="${BASE_CONTAINER_NAME}-multi"
SINGLE_PROJECT_NAME="${BASE_CONTAINER_NAME}"

if ! [[ "${INSTANCES}" =~ ^[0-9]+$ ]] || [[ "${INSTANCES}" -lt 1 ]]; then
  echo "KSRPC_INSTANCES must be an integer >= 1"
  exit 1
fi

if ! [[ "${START_PORT}" =~ ^[0-9]+$ ]] || [[ "${START_PORT}" -lt 1 ]] || [[ "${START_PORT}" -gt 65535 ]]; then
  echo "KSRPC_HOST_PORT must be an integer in 1..65535"
  exit 1
fi

port_in_use() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "( sport = :${port} )" 2>/dev/null | grep -q .
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi
  netstat -an 2>/dev/null | grep -E "[:.]${port}[[:space:]].*LISTEN" >/dev/null 2>&1
}

declare -A ALLOCATED_PORTS=()
allocate_next_free_port() {
  local candidate="$1"
  while true; do
    if [[ "${candidate}" -gt 65535 ]]; then
      echo "No free port found in 1..65535"
      exit 1
    fi
    if [[ -n "${ALLOCATED_PORTS[${candidate}]+x}" ]]; then
      candidate=$((candidate + 1))
      continue
    fi
    if port_in_use "${candidate}"; then
      candidate=$((candidate + 1))
      continue
    fi
    ALLOCATED_PORTS["${candidate}"]=1
    echo "${candidate}"
    return
  done
}

generate_compose() {
  cat > "${COMPOSE_FILE}" <<EOF
services:
EOF

  local i host_port cache_host_path service_name container_name suffix next_port
  next_port="${START_PORT}"

  for ((i = 1; i <= INSTANCES; i++)); do
    host_port="$(allocate_next_free_port "${next_port}")"
    next_port=$((host_port + 1))
    suffix="$(printf "%02d" "${i}")"
    cache_host_path="./data/cache/${BASE_CONTAINER_NAME}-${suffix}"
    mkdir -p "${APP_DIR}/${cache_host_path#./}"
    service_name="${BASE_CONTAINER_NAME}-${suffix}"
    container_name="${BASE_CONTAINER_NAME}-${suffix}"

    {
      echo "  ${service_name}:"
      if [[ "${FORCE_BUILD}" == "1" ]]; then
        echo "    build:"
        echo "      context: ."
        echo "      dockerfile: Dockerfile"
      else
        if [[ -n "${IMAGE_OVERRIDE}" ]]; then
          echo "    image: ${IMAGE_OVERRIDE}"
        else
          echo "    image: \${OCI_IMAGE_REF}"
        fi
      fi
      cat <<EOF
    container_name: ${container_name}
    restart: always
    command: ["python", "-u", "-m", "gunicorn", "-c", "/etc/ksrpc/gunicorn.conf.py", "ksrpc.run_gunicorn:web_app"]
    env_file:
      - ${ENV_FILE}
    environment:
      TZ: Asia/Shanghai
      CONFIG_SERVER: /etc/ksrpc/ksrpc.conf.py
      KSRPC_GUNICORN_BIND: 0.0.0.0:8080
      KSRPC_PORT: "8080"
      KSRPC_CACHE_PATH: /opt/ksrpc/cache
    volumes:
      - "\${KSRPC_GUNICORN_CONFIG_PATH:-./gunicorn.conf.py}:/etc/ksrpc/gunicorn.conf.py:ro"
      - "\${KSRPC_CONFIG_PATH:-./ksrpc.conf.py}:/etc/ksrpc/ksrpc.conf.py:ro"
      - "${cache_host_path}:/opt/ksrpc/cache"
    ports:
      - "${host_port}:8080"
    healthcheck:
      test:
        - CMD-SHELL
        - python -c "import socket; p=8080; s=socket.create_connection(('127.0.0.1', p), 3); s.close()"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
EOF
    } >> "${COMPOSE_FILE}"
  done

  echo "Generated: ${COMPOSE_FILE}"
  echo "Instances: ${INSTANCES}"
  echo "Container prefix: ${BASE_CONTAINER_NAME}"
  echo "Start port: ${START_PORT} (auto skip occupied ports)"
}

compose_multi() {
  (cd "${APP_DIR}" && docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" -p "${MULTI_PROJECT_NAME}" "$@")
}

compose_single() {
  (cd "${APP_DIR}" && docker compose --env-file "${ENV_FILE}" -f "${APP_DIR}/docker-compose.yml" -p "${SINGLE_PROJECT_NAME}" "$@")
}

case "${ACTION}" in
  generate)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      echo "KSRPC_INSTANCES=1: use docker-compose.yml directly; skip multi compose generation."
    else
      generate_compose
    fi
    ;;
  start)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single up -d --remove-orphans
    else
      generate_compose
      compose_multi up -d --remove-orphans
    fi
    ;;
  stop)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single down --remove-orphans
    else
      compose_multi down --remove-orphans
    fi
    ;;
  restart)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single down --remove-orphans
      compose_single up -d --remove-orphans
    else
      generate_compose
      compose_multi down --remove-orphans
      compose_multi up -d --remove-orphans
    fi
    ;;
  status)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single ps
    else
      compose_multi ps
    fi
    ;;
  clean)
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single down -v --remove-orphans
    else
      compose_multi down -v --remove-orphans
    fi
    ;;
  *)
    echo "Unknown action: ${ACTION}"
    echo "Allowed: generate|start|stop|restart|status|clean"
    exit 1
    ;;
esac
