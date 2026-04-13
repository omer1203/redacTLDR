# redactldr API Contracts (v1)

Base path: `/v1`

## Health

- `GET /v1/health`
  - Returns service status and version.

## Auth

- `GET /v1/auth/me`
  - Requires Clerk bearer token.
  - Returns user identity resolved from JWT.

## Documents

- `POST /v1/documents`
  - Creates document metadata and presigned upload URL.
  - Request:
    - `filename: string`
    - `contentType: string` (default `application/pdf`)
    - `mode: DocumentMode`
    - `safeMode?: boolean`
  - Response:
    - `id`, `s3Key`, `presignedPutUrl`, `status`

- `GET /v1/documents`
  - Lists user documents with pagination.

- `GET /v1/documents/{docId}`
  - Returns document detail and status.

- `POST /v1/documents/{docId}/ingestDone`
  - Marks upload complete and enqueues detection.

## Review

- `GET /v1/documents/{docId}/detections`
  - Returns proposed detections with citations and confidence.

- `POST /v1/documents/{docId}/redactions`
  - Saves review decision or manual redaction.
  - Supports entity-level and custom bbox/span redactions.

## Export

- `POST /v1/documents/{docId}/export`
  - Enqueues true redaction export job.

- `GET /v1/documents/{docId}/export`
  - Returns export status and optional presigned download URL.

## Summaries

- `POST /v1/documents/{docId}/summaries`
  - Enqueues summary generation for selected mode.

- `GET /v1/documents/{docId}/summaries/latest`
  - Returns latest summary:
    - `json: object` (schema per mode)
    - `markdown: string`
    - `citations: [{page, block}]`
    - `confidence: object`

## Audit

- `GET /v1/audit`
  - Returns paginated audit events for user/workspace.

## Error Shape

All errors follow:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```
