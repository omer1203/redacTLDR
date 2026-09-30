#!/usr/bin/env bash
# Copy active AWS CLI login/session credentials into ops/compose/.env, then
# recreate API/worker so Docker picks them up.
#
# Usage (from repo root):
#   bash scripts/sync-aws-env.sh
#   bash scripts/sync-aws-env.sh --no-restart
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/ops/compose/.env"
COMPOSE_FILE="${REPO_ROOT}/ops/compose/docker-compose.yml"
RESTART=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-restart) RESTART=false; shift ;;
    -h|--help)
      echo "Usage: bash scripts/sync-aws-env.sh [--no-restart]"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy ops/compose/.env.example first." >&2
  exit 1
fi

echo "Checking AWS CLI session..."
aws sts get-caller-identity >/dev/null

python3 - <<'PY'
import re
import subprocess
from pathlib import Path

env_path = Path("ops/compose/.env")
raw = subprocess.check_output(["aws", "configure", "export-credentials", "--format", "env"], text=True)
updates = {}
for line in raw.strip().splitlines():
    line = line.removeprefix("export ")
    if "=" in line:
        k, _, v = line.partition("=")
        if k.startswith("AWS_"):
            updates[k] = v

if not updates.get("AWS_ACCESS_KEY_ID"):
    raise SystemExit("Could not export AWS credentials. Run: aws login")

text = env_path.read_text()
for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_CREDENTIAL_EXPIRATION", "AWS_REGION"):
    val = updates.get(key)
    if key == "AWS_REGION" and not val:
        val = "us-east-1"
    if val is None and key in ("AWS_SESSION_TOKEN", "AWS_CREDENTIAL_EXPIRATION"):
        text = re.sub(rf"^{re.escape(key)}=.*\n?", "", text, flags=re.M)
        continue
    if val is None:
        continue
    pattern = rf"^{re.escape(key)}=.*$"
    replacement = f"{key}={val}"
    if re.search(pattern, text, flags=re.M):
        text = re.sub(pattern, replacement, text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{replacement}\n"

env_path.write_text(text)
print(f"Updated AWS credentials in {env_path}")
PY

bash "${SCRIPT_DIR}/verify-local-s3.sh"

if [[ "${RESTART}" == "true" ]]; then
  echo "Recreating api and worker containers..."
  # Match dev-up.sh: local Postgres unless caller already exported remote URLs.
  export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@postgres:5432/redactldr}"
  export MIGRATION_DATABASE_URL="${MIGRATION_DATABASE_URL:-postgresql+psycopg://postgres:postgres@postgres:5432/redactldr}"
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --force-recreate api worker
  echo "Done. Retry upload at http://localhost:3000/dashboard"
fi
