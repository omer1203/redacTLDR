#!/usr/bin/env bash
# Sanity-check AWS identity and that originals/downloads buckets exist and are reachable.
# Does not modify AWS resources.
#
# Usage (from repo root):
#   bash scripts/verify-local-s3.sh
#   bash scripts/verify-local-s3.sh --read-env path/to/.env
#
# If --read-env is omitted and ops/compose/.env exists, it is sourced automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOAD_ENV=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --read-env)
      LOAD_ENV="${2:?expected path after --read-env}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${LOAD_ENV}" && -f "${REPO_ROOT}/ops/compose/.env" ]]; then
  LOAD_ENV="${REPO_ROOT}/ops/compose/.env"
fi

if [[ -n "${LOAD_ENV}" && -f "${LOAD_ENV}" ]]; then
  echo "Loading env from: ${LOAD_ENV}"
  set -a
  # shellcheck disable=SC1090
  source "${LOAD_ENV}"
  set +a
fi

REGION="${AWS_REGION:-us-east-1}"
ORIGINALS="${S3_BUCKET_ORIGINALS:-redactldr-originals-dev}"
DOWNLOADS="${S3_BUCKET_DOWNLOADS:-redactldr-downloads-dev}"

echo "== AWS identity"
aws sts get-caller-identity || {
  echo "Fix: configure credentials (aws configure, SSO, or env vars)." >&2
  exit 1
}

echo
echo "== Region: ${REGION}"
echo "== Buckets: originals=${ORIGINALS} downloads=${DOWNLOADS}"
echo

for label in originals downloads; do
  if [[ "$label" == originals ]]; then
    b="$ORIGINALS"
  else
    b="$DOWNLOADS"
  fi
  echo -n "  ${label} (${b}) ... "
  if err="$(aws s3api head-bucket --bucket "$b" --region "$REGION" 2>&1)"; then
    echo "OK"
  else
    echo "FAIL"
    echo "$err" >&2
    echo "Create: aws s3 mb s3://${b} --region ${REGION}" >&2
    exit 1
  fi
done

echo
echo "All checks passed. Use the same AWS_REGION and S3_BUCKET_* values in ops/compose/.env for the API/worker containers."
