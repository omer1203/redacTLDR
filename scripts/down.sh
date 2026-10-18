#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/../ops/compose"
COMPOSE_FILES=(
  -f "${COMPOSE_DIR}/docker-compose.yml"
  -f "${COMPOSE_DIR}/docker-compose.local-ports.yml"
)
ENV_FILE="${COMPOSE_DIR}/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not in PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose is not available."
  exit 1
fi

echo "Stopping RedacTLDR local stack..."
if [[ -f "${ENV_FILE}" ]]; then
  docker compose \
    --env-file "${ENV_FILE}" \
    "${COMPOSE_FILES[@]}" \
    down "$@"
else
  docker compose \
    "${COMPOSE_FILES[@]}" \
    down "$@"
fi
