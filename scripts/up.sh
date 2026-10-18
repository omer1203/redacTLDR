#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${SCRIPT_DIR}/../ops/compose"
ENV_FILE="${COMPOSE_DIR}/.env"
ENV_EXAMPLE_FILE="${COMPOSE_DIR}/.env.example"

BUILD_FLAG=""
COMPOSE_PROFILES_VALUE=""
OBSERVABILITY_ENABLED=false
USE_REMOTE_DB=false
ATTACH=false
SYNC_AWS=false
COMPOSE_FILES=(-f "${COMPOSE_DIR}/docker-compose.yml")
API_PORT=8000
POSTGRES_PORT=5432

LOCAL_DATABASE_URL="postgresql+psycopg://postgres:postgres@postgres:5432/redactldr"

usage() {
  cat <<'EOF'
Usage: bash scripts/up.sh [options]

Options:
  --build              Rebuild local images before starting.
  --attach             Stream logs in the foreground after startup.
  --profile NAME       Enable a Docker Compose profile, e.g. observability.
  --remote-db          Use DATABASE_URL values from ops/compose/.env or shell.
  --sync-aws           Overwrite AWS keys in .env from the current CLI session.
                       Off by default so long-lived IAM keys are not replaced
                       by expiring session tokens. scripts/sync-aws-env.sh
                       remains available as the same fallback.
  -h, --help           Show this help message.

Default startup reuses existing images and points services at the local
Postgres container for fast, repeatable development. Services start detached so
the command returns after boot.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD_FLAG="--build"
      shift
      ;;
    --attach)
      ATTACH=true
      shift
      ;;
    --profile)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "Error: --profile requires a profile name."
        exit 1
      fi
      if [[ -z "${COMPOSE_PROFILES_VALUE}" ]]; then
        COMPOSE_PROFILES_VALUE="$2"
      else
        COMPOSE_PROFILES_VALUE="${COMPOSE_PROFILES_VALUE},$2"
      fi
      if [[ "$2" == "observability" ]]; then
        OBSERVABILITY_ENABLED=true
      fi
      shift 2
      ;;
    --remote-db)
      USE_REMOTE_DB=true
      shift
      ;;
    --sync-aws)
      SYNC_AWS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker is not installed or not in PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Error: docker compose is not available."
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  if [[ -f "${ENV_EXAMPLE_FILE}" ]]; then
    cp "${ENV_EXAMPLE_FILE}" "${ENV_FILE}"
    echo "Created ${ENV_FILE} from ${ENV_EXAMPLE_FILE}."
  else
    echo "Error: ${ENV_EXAMPLE_FILE} not found."
    exit 1
  fi
  echo "Fill in Clerk/AWS values as needed before testing real integrations."
  echo "If browser uploads fail with an S3 CORS error, run: bash scripts/apply-s3-cors.sh"
  echo "Check buckets/credentials: bash scripts/verify-local-s3.sh"
fi

if [[ "${OBSERVABILITY_ENABLED}" == "true" ]]; then
  export OTEL_EXPORTER_OTLP_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT:-http://otel-collector:4317}"
fi
if [[ -n "${COMPOSE_PROFILES_VALUE}" ]]; then
  export COMPOSE_PROFILES="${COMPOSE_PROFILES_VALUE}"
fi
if [[ "${USE_REMOTE_DB}" != "true" ]]; then
  export DATABASE_URL="${LOCAL_DATABASE_URL}"
  export MIGRATION_DATABASE_URL="${LOCAL_DATABASE_URL}"
fi

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

if port_in_use 5432 || port_in_use 8000; then
  if port_in_use 5433 || port_in_use 8001; then
    echo "Error: default ports 5432/8000 are busy, and fallback ports 5433/8001 are busy too."
    exit 1
  fi
  COMPOSE_FILES+=(-f "${COMPOSE_DIR}/docker-compose.local-ports.yml")
  API_PORT=8001
  POSTGRES_PORT=5433
  echo "Ports 5432 and/or 8000 are in use. Using fallback ports (Postgres ${POSTGRES_PORT}, API ${API_PORT})."
fi

if [[ "${SYNC_AWS}" == "true" ]]; then
  echo "Syncing AWS credentials from the active CLI session into ops/compose/.env..."
  bash "${SCRIPT_DIR}/sync-aws-env.sh" --no-restart
else
  echo "Using AWS keys already in ops/compose/.env (pass --sync-aws to refresh from the CLI session)."
fi

echo "Starting RedacTLDR local stack..."
if [[ "${ATTACH}" == "true" ]]; then
  docker compose \
    --env-file "${ENV_FILE}" \
    "${COMPOSE_FILES[@]}" \
    up ${BUILD_FLAG}
else
  # --wait returns when Postgres, Redis, and the API are healthy. The web
  # dev server is not part of that wait; Next.js keeps booting after this.
  docker compose \
    --env-file "${ENV_FILE}" \
    "${COMPOSE_FILES[@]}" \
    up -d --wait --wait-timeout 300 ${BUILD_FLAG}
fi

echo
echo "Services are running."
echo "Web: http://localhost:3000"
echo "API health: http://localhost:${API_PORT}/v1/health"
echo "Postgres host port: ${POSTGRES_PORT}"
echo "Logs: docker compose --env-file ops/compose/.env ${COMPOSE_FILES[*]} logs -f"
echo
docker compose --env-file "${ENV_FILE}" "${COMPOSE_FILES[@]}" ps
