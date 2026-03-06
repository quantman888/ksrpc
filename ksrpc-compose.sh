#!/usr/bin/env bash
set -euo pipefail

ACTION="restart"
if [[ $# -gt 0 ]]; then
  case "$1" in
    generate|start|restart|clean)
      ACTION="$1"
      shift
      ;;
    stop|status)
      echo "Action '$1' is no longer supported."
      echo "Use: bash ./ksrpc-compose.sh [generate|start|restart|clean] [options]"
      exit 1
      ;;
    -*)
      # 默认动作 restart，继续解析后续选项
      ;;
    *)
      echo "Unknown action: $1"
      echo "Allowed: generate|start|restart|clean"
      exit 1
      ;;
  esac
fi

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

END_PORT=$((START_PORT + INSTANCES - 1))
if [[ "${END_PORT}" -gt 65535 ]]; then
  echo "Port range overflow: ${START_PORT}-${END_PORT} exceeds 65535"
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

port_is_expected_occupier() {
  local port="$1"
  local expected_name="$2"
  local names
  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi
  names="$(docker ps --filter "publish=${port}" --format '{{.Names}}' 2>/dev/null || true)"
  if [[ -z "${names}" ]]; then
    return 1
  fi
  while IFS= read -r name; do
    if [[ "${name}" == "${expected_name}" ]]; then
      return 0
    fi
  done <<< "${names}"
  return 1
}

ensure_port_range_available() {
  local i port expected_name
  local -a occupied=()
  for ((i = 1; i <= INSTANCES; i++)); do
    port=$((START_PORT + i - 1))
    if [[ "${INSTANCES}" -eq 1 ]]; then
      expected_name="${BASE_CONTAINER_NAME}"
    else
      expected_name="$(printf "%s-%02d" "${BASE_CONTAINER_NAME}" "${i}")"
    fi

    if port_in_use "${port}"; then
      if port_is_expected_occupier "${port}" "${expected_name}"; then
        continue
      fi
      occupied+=("${port}")
    fi
  done

  if [[ "${#occupied[@]}" -gt 0 ]]; then
    echo "Port range check failed."
    echo "Required range: ${START_PORT}-${END_PORT}"
    echo "Occupied by other process/container: ${occupied[*]}"
    exit 1
  fi
}

generate_compose() {
  ensure_port_range_available

  cat > "${COMPOSE_FILE}" <<EOF
services:
EOF

  local i host_port cache_host_path service_name container_name suffix

  for ((i = 1; i <= INSTANCES; i++)); do
    host_port=$((START_PORT + i - 1))
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
      PORT: "8080"
      CACHE_PATH: /opt/ksrpc/cache
    volumes:
      - "\${KSRPC_GUNICORN_CONFIG_PATH:-./gunicorn.conf.py}:/etc/ksrpc/gunicorn.conf.py:ro"
      - "\${KSRPC_CONFIG_PATH:-./ksrpc.conf.py}:/etc/ksrpc/ksrpc.conf.py:ro"
      - "${cache_host_path}:/opt/ksrpc/cache"
    ports:
      - "${host_port}:8080"
EOF
    } >> "${COMPOSE_FILE}"
  done

  echo "Generated: ${COMPOSE_FILE}"
  echo "Instances: ${INSTANCES}"
  echo "Container prefix: ${BASE_CONTAINER_NAME}"
  echo "Port range: ${START_PORT}-${END_PORT} (strict mode)"
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
    # 等价于首次部署/应用配置：强制重建以确保配置更新立即生效
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single up -d --remove-orphans --force-recreate
    else
      generate_compose
      compose_multi up -d --remove-orphans --force-recreate
    fi
    ;;
  restart)
    # 无参数默认走 restart，更新配置后直接运行本脚本即可生效
    if [[ "${INSTANCES}" -eq 1 ]]; then
      compose_single up -d --remove-orphans --force-recreate
    else
      generate_compose
      compose_multi up -d --remove-orphans --force-recreate
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
    echo "Allowed: generate|start|restart|clean"
    exit 1
    ;;
esac
