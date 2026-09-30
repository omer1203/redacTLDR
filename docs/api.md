# RedacTLDR API Contracts (v1)

Base path: `/v1`

This is the API contract snapshot for implemented and near-term endpoints up to `M2`, with forward references for upcoming milestones.

## Health

- `GET /v1/health`
  - Returns service status and version.

## Auth

- `GET /v1/auth/me`
  - Requires bearer token (or local dev bypass where enabled).
  - Returns resolved caller identity.

## Documents

- `POST /v1/documents`
  - Creates document metadata.
  - Returns presigned S3 PUT URL for direct upload.
  - Request fields:
    - `filename`
    - `contentType` (PDF)
    - `mode`
    - `safeMode`
    - `sizeBytes` (optional)

- `GET /v1/documents`
  - Lists caller-owned documents.

- `GET /v1/documents/{docId}`
  - Gets one caller-owned document.

- `POST /v1/documents/{docId}/ingest-complete`
  - Canonical ingest completion endpoint.
  - Verifies upload object before queueing detect task.

- `POST /v1/documents/{docId}/ingestDone`
  - Backward-compatible alias.
  - Planned deprecation after clients migrate to `ingest-complete`.

- `GET /v1/documents/{docId}/jobs`
  - Lists jobs for the document, newest first.
  - Each item: `jobType`, `status`, `attemptCount`, `lastError`, `startedAt`, `finishedAt`.

- `POST /v1/documents/{docId}/process`
  - Re-runs detection for `FAILED` or stuck documents.
  - No-op when detection is already queued or already finished.

- `DELETE /v1/documents/{docId}`
  - Soft-deletes the row and deletes the original and export objects.
  - Returns 204.

## Review and Redaction Data

- `GET /v1/documents/{docId}/detections`
- `POST /v1/documents/{docId}/redactions`
- `GET /v1/documents/{docId}/review-state`

## Export

- `POST /v1/documents/{docId}/export`
- `GET /v1/documents/{docId}/export`

## Summary

- `POST /v1/documents/{docId}/summaries`
- `GET /v1/documents/{docId}/summaries/latest`
- `GET /v1/documents/modes/schema`

## Audit

- `GET /v1/audit`

## Auth Integration Requirements

- Clerk JWT audience must match API expectations.
- Web token minting enforces explicit JWT template (`CLERK_JWT_TEMPLATE`) when Clerk mode is enabled.
- JWKS caching is used server-side for verification performance and rotation resilience.
- Local development may use `x-demo-user` header when `ENVIRONMENT=local`.

## Error Handling

Current routes primarily return FastAPI standard error payloads with `detail`.
As part of later hardening milestones, error shape will be standardized across all routes.
