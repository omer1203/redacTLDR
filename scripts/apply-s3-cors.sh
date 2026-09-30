#!/usr/bin/env bash
# Apply browser CORS to S3 originals (and optionally downloads) so presigned PUT/GET
# works from the web app. Required for uploads from http://localhost:3000.
#
# Usage:
#   AWS_PROFILE=... ./scripts/apply-s3-cors.sh
#   S3_BUCKET_ORIGINALS=my-bucket S3_BUCKET_DOWNLOADS=my-exports ./scripts/apply-s3-cors.sh
#   S3_CORS_CONFIG=/path/to/cors.json ./scripts/apply-s3-cors.sh
#   AWS_REGION=us-west-2 ...  # must match the bucket’s region (default: us-east-1)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="${S3_CORS_CONFIG:-${ROOT_DIR}/scripts/s3-cors-browser-upload.local.json}"
ORIGINALS="${S3_BUCKET_ORIGINALS:-redactldr-originals-dev}"
DOWNLOADS="${S3_BUCKET_DOWNLOADS:-}"
REGION="${AWS_REGION:-us-east-1}"

reject_copy_paste_placeholders() {
  case "${REGION}" in
    the-bucket-region|your-region|my-region|REGION)
      echo "AWS_REGION is set to a documentation placeholder (${REGION})." >&2
      echo "Use a real value such as us-east-1 (must match the bucket region)." >&2
      exit 1
      ;;
  esac
  case "${ORIGINALS}" in
    your-originals-bucket|your-downloads-bucket|my-bucket|example-bucket)
      echo "S3_BUCKET_ORIGINALS looks like a placeholder (${ORIGINALS})." >&2
      echo "Use your real bucket name (aws s3 ls) or the defaults in ops/compose/.env.example." >&2
      exit 1
      ;;
  esac
  case "${DOWNLOADS}" in
    your-downloads-bucket|your-originals-bucket)
      echo "S3_BUCKET_DOWNLOADS looks like a placeholder (${DOWNLOADS})." >&2
      exit 1
      ;;
  esac
}

reject_copy_paste_placeholders

if [[ ! -f "$CONFIG" ]]; then
  echo "CORS config not found: $CONFIG" >&2
  exit 1
fi

ensure_bucket_readable() {
  local name="$1"
  if ! err="$(aws s3api head-bucket --bucket "$name" --region "$REGION" 2>&1)"; then
    echo "Cannot access bucket s3://${name} in region ${REGION}." >&2
    echo "${err}" >&2
    echo >&2
    echo "Typical fixes:" >&2
    echo "  1. Create it: aws s3 mb s3://${name} --region ${REGION}" >&2
    echo "  2. Wrong region: set AWS_REGION to the bucket region (Console → bucket → Properties)." >&2
    echo "  3. Wrong account: set AWS_PROFILE / keys for the account that owns the bucket." >&2
    echo "  4. Wrong name: set S3_BUCKET_ORIGINALS (see aws s3 ls)." >&2
    exit 1
  fi
}

ensure_bucket_readable "$ORIGINALS"

echo "Applying CORS from $CONFIG to s3://${ORIGINALS} (region ${REGION})"
aws s3api put-bucket-cors --bucket "$ORIGINALS" --region "$REGION" --cors-configuration "file://${CONFIG}"

if [[ -n "$DOWNLOADS" ]]; then
  ensure_bucket_readable "$DOWNLOADS"
  echo "Applying CORS from $CONFIG to s3://${DOWNLOADS} (region ${REGION})"
  aws s3api put-bucket-cors --bucket "$DOWNLOADS" --region "$REGION" --cors-configuration "file://${CONFIG}"
fi

echo "Done. For production, copy the JSON, set AllowedOrigins to your HTTPS app URL(s), and re-run."
