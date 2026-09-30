# M4/M5 Validation Playbook (Upload + Jobs)

This runbook checks the R0 upload and queue path: presigned upload, detect job,
retry, delete, and stale `CREATED` cleanup.

## Preconditions

- Long-lived IAM keys are in `ops/compose/.env` (`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`).
  Do not leave `AWS_SESSION_TOKEN` in that file. `bash scripts/dev-up.sh` will not
  copy CLI session tokens unless you pass `--sync-aws`.
- Local Postgres is reachable as `postgres:postgres` on port 5432, or on 5433 when
  5432 is already taken. Tests pick the first of those that accepts a connection.
- `pip install -r requirements.txt` (includes `moto[s3]` for the pipeline tests).

## 1) Automated pipeline

```bash
pytest services/api/tests services/worker/tests
```

Expected:

- All tests pass, including `services/api/tests/test_document_pipeline.py`.
- That module covers create → S3 put → ingest-complete → `DETECTED`, failure
  `last_error`, `POST /process`, `DELETE`, and the stale-upload cleanup task.

## 2) Local stack

```bash
bash scripts/dev-up.sh --build
bash scripts/verify-local-s3.sh
```

If 5432 or 8000 is busy, the script prints fallback URLs (API on 8001, Postgres on 5433).

Expected:

- API health responds on the printed URL.
- S3 checks pass with the keys already in `.env`.

## 3) Jobs endpoint

After a document has been ingested, replace `<id>` and the port if the script printed 8001:

```bash
curl -s localhost:8000/v1/documents/<id>/jobs -H "x-demo-user: demo-user"
```

Expected JSON fields on each row: `jobType`, `status`, `attemptCount`, `lastError`, `startedAt`, `finishedAt`.

Retry a failed document:

```bash
curl -s -X POST localhost:8000/v1/documents/<id>/process -H "x-demo-user: demo-user"
```

## 4) Still manual

Upload a PDF in the browser after a full `dev-up.sh --build` restart, with no
`sync-aws-env.sh` step. That is the remaining R0 checkbox in
`docs/ROAD_FULL_IMPLEMENTATION.md`.
