#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
GIT_REMOTE="${DEPLOY_GIT_REMOTE:-origin}"
CURRENT_BRANCH="$(git -C "${APP_DIR}" branch --show-current 2>/dev/null || true)"
GIT_REF="${DEPLOY_GIT_REF:-${CURRENT_BRANCH}}"
ENV_FILE="${DEPLOY_ENV_FILE:-${APP_DIR}/.env}"
CONFIG_FILE="${DEPLOY_CONFIG_FILE:-${APP_DIR}/config_server.py}"
BUILD_IMAGE="${DEPLOY_BUILD_IMAGE:-ksrpc:git-deploy}"
PULL_ONLY="${DEPLOY_PULL_ONLY:-0}"

log() {
  echo "[deploy_from_git] $*"
}

die() {
  log "$*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "command not found: $1"
}

read_env_from_file() {
  local key="$1"
  local file="$2"
  local default_value="$3"
  local line value

  line="$(grep -E "^${key}=" "${file}" | tail -n 1 || true)"
  if [[ -z "${line}" ]]; then
    echo "${default_value}"
    return
  fi

  value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  if [[ -z "${value}" ]]; then
    echo "${default_value}"
  else
    echo "${value}"
  fi
}

require_clean_tracked_worktree() {
  git -C "${APP_DIR}" diff --quiet || die "tracked working tree has unstaged changes"
  git -C "${APP_DIR}" diff --cached --quiet || die "tracked working tree has staged changes"
}

checkout_target_ref() {
  git -C "${APP_DIR}" fetch --tags --prune "${GIT_REMOTE}"
  if git -C "${APP_DIR}" show-ref --verify --quiet "refs/remotes/${GIT_REMOTE}/${GIT_REF}"; then
    if git -C "${APP_DIR}" show-ref --verify --quiet "refs/heads/${GIT_REF}"; then
      git -C "${APP_DIR}" checkout "${GIT_REF}"
    else
      git -C "${APP_DIR}" checkout -b "${GIT_REF}" --track "${GIT_REMOTE}/${GIT_REF}"
    fi
    git -C "${APP_DIR}" pull --ff-only "${GIT_REMOTE}" "${GIT_REF}"
    return
  fi

  git -C "${APP_DIR}" checkout --detach "${GIT_REF}"
}

require_cmd git
require_cmd docker

[[ -d "${APP_DIR}/.git" ]] || die "git repository not found: ${APP_DIR}"
[[ -n "${GIT_REF}" ]] || die "DEPLOY_GIT_REF is required when HEAD is detached"

require_clean_tracked_worktree
checkout_target_ref
git -C "${APP_DIR}" submodule update --init --recursive

[[ -f "${ENV_FILE}" ]] || die "env file not found: ${ENV_FILE}"
[[ -f "${CONFIG_FILE}" ]] || die "config file not found: ${CONFIG_FILE}"

if [[ "${PULL_ONLY}" == "1" ]]; then
  log "pull-only completed at $(git -C "${APP_DIR}" rev-parse --short HEAD)"
  exit 0
fi

INSTANCES="$(read_env_from_file KSRPC_INSTANCES "${ENV_FILE}" 1)"
if [[ "${INSTANCES}" != "1" ]]; then
  die "KSRPC_INSTANCES=${INSTANCES} is not supported by scripts/deploy_from_git.sh yet"
fi

(
  cd "${APP_DIR}"
  docker build -t "${BUILD_IMAGE}" .
  OCI_IMAGE_REF="${BUILD_IMAGE}" docker compose --env-file "${ENV_FILE}" config >/dev/null
  OCI_IMAGE_REF="${BUILD_IMAGE}" docker compose --env-file "${ENV_FILE}" up -d --remove-orphans --force-recreate
)

log "deployed ref $(git -C "${APP_DIR}" rev-parse --short HEAD) with image ${BUILD_IMAGE}"
