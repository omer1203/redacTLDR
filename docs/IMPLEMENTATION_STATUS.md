# RedacTLDR Implementation Status

This file is the human-readable status dashboard. The machine-readable companion is `docs/MILESTONE_STATUS.json`.

## Snapshot

- `M1`: completed and validated
- `M2`: completed and validated (local demo + Clerk integration paths)
- `M3`: completed and validated
- `M4`: completed for the API/worker path (presign, ingest, job list, delete). Live browser restart after `dev-up.sh --build` is still an open R0 check.
- `M5`: completed for queue reliability (retry, failure `last_error`, stale-upload cleanup, SQL casts, idempotent detect)
- `M6+`: planned or partial scaffolding depending on subsystem

## What Is Implemented Now

- FastAPI runtime with route domains (`auth`, `documents`, `audit`)
- Clerk JWT verification path with JWKS caching
- Local auth bypass for developer workflows (`ENVIRONMENT=local`)
- SQLAlchemy model baseline for document lifecycle entities
- API to worker queue wiring through Celery + Redis
- Worker task skeleton for detect/export/summary with retries
- S3 presign support and ingest completion flow checks
- Next.js dashboard route protection and API-backed document list/upload flow
- Explicit sign-in/sign-up routes for Clerk mode
- Strict `CLERK_JWT_TEMPLATE` enforcement when Clerk mode is enabled
- Local no-login dashboard mode using `x-demo-user` for developer ergonomics
- Local docker-compose stack with web, api, worker, postgres, redis, otel
- `ops/compose/.env.example` baseline and runbook-driven startup

## M1/M2 Evidence (Latest)

- Automated checks passed:
  - `npm run web:lint`
  - `npm run web:typecheck`
  - `pytest services/api/tests services/worker/tests`
- Runtime smoke checks passed:
  - `GET /v1/health`
  - `GET /v1/documents` with local `x-demo-user`
- Manual + integration playbook published:
  - `docs/M1_M2_VALIDATION_PLAYBOOK.md`

## M4/M5 Evidence

- Pipeline tests in `services/api/tests/test_document_pipeline.py`:
  - create → moto S3 put → ingest-complete → eager `detect_job` → `DETECTED` and a `COMPLETED` job
  - detect failure retries and stores `last_error`
  - `POST /v1/documents/{id}/process` retries a `FAILED` document and is a no-op once detected
  - `DELETE /v1/documents/{id}` soft-deletes the row and removes the S3 object
  - `cleanup_stale_uploads` soft-deletes `CREATED` rows older than 24 hours
- `pytest services/api/tests services/worker/tests`: 12 passed on 2026-09-30
- Runbook: `docs/M4_M5_VALIDATION_PLAYBOOK.md`

## Known Gaps Beyond M2

- schema redesign for M3 canonical model (`owner_user_id`, `workspace_id`, soft deletes, jobs table, RLS policies)
- real Textract/Comprehend/Bedrock execution paths
- true-redaction correctness guarantees on real PDFs
- policy engine depth and workspace-level governance
- production deployment hardening

## M3 Evidence (Completed)

- Alembic scaffolding + migration history in repo.
- Runtime/migration URL split:
  - `DATABASE_URL` (pooler runtime)
  - `MIGRATION_DATABASE_URL` (direct migration connection)
- Migration-first safety:
  - non-local API startup no longer runs implicit schema creation.
- Applied migrations on Supabase:
  - baseline `0e64b6ccff04`
  - schema expansion `eb35da4c4c2e`
- Schema additions implemented:
  - canonical document fields (`owner_user_id`, `workspace_id`, `document_type`, `s3_key_original`)
  - soft-delete columns on core tables
  - `jobs` table
- RLS hardening:
  - RLS enabled and restrictive deny policies added on all core tables.
- Seed tooling:
  - `scripts/seed_m3_demo.py`
- Validation runbook:
  - `docs/M3_VALIDATION_PLAYBOOK.md`

## Evidence Policy

No milestone is marked complete without:

- command-level validation
- test output or manual runbook evidence
- updated docs and status files
