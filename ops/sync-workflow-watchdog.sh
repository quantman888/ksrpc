#!/usr/bin/env bash
set -euo pipefail

# External watchdog for repositories where scheduled workflows may be auto-disabled.
# Usage:
#   GITHUB_TOKEN=xxx ./ops/sync-workflow-watchdog.sh quantman888/ksrpc ops/sync

REPO_FULL_NAME="${1:-quantman888/ksrpc}"
REF_BRANCH="${2:-ops/sync}"
WORKFLOW_FILE="sync-upstream.yml"
API_ROOT="https://api.github.com/repos/${REPO_FULL_NAME}/actions/workflows/${WORKFLOW_FILE}"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "GITHUB_TOKEN is required"
  exit 1
fi

auth_header="Authorization: Bearer ${GITHUB_TOKEN}"
accept_header="Accept: application/vnd.github+json"

curl -fsSL -X PUT -H "${auth_header}" -H "${accept_header}" "${API_ROOT}/enable" >/dev/null

curl -fsSL -X POST \
  -H "${auth_header}" \
  -H "${accept_header}" \
  -d "{\"ref\":\"${REF_BRANCH}\"}" \
  "${API_ROOT}/dispatches" >/dev/null

echo "sync-upstream workflow enabled and dispatched for ${REPO_FULL_NAME}@${REF_BRANCH}"
