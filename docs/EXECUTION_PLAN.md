# RedacTLDR Canonical Execution Plan (M1-M18)

This is the source-of-truth plan for how we build and verify RedacTLDR.

## Working Agreement

- Build in milestone order (`M1` through `M18`).
- Every milestone includes:
  - scope
  - definition of done
  - validation evidence
  - security notes
  - interview talking points
- No "vibe coding": each implementation step must be explainable and testable.
- API stays orchestration-focused; heavy work stays in workers.
- Privacy policy is a first-class runtime concern, not a post-processing add-on.

## Current Repository Canonical Layout

- `apps/web`: Next.js website-first product surface
- `services/api`: FastAPI orchestration and API contracts
- `services/worker`: Celery background processing
- `ops`: local runtime, docker, optional k8s assets
- `infra/terraform`: infrastructure as code
- `docs`: architecture, contracts, milestones, runbooks

Mobile is explicitly deferred and out of scope for current execution until website milestones are stable.

---

## M1 - Foundation / Local Development Stack

### Scope

- Monorepo structure is clean and consistent.
- Next.js web app bootstrapped with TypeScript and Tailwind.
- FastAPI backend with `/v1/health`.
- Celery worker with sample task path.
- Redis broker in local environment.
- Dockerfiles and Compose for local stack.
- `.env.example` style setup guidance and local runbook.

### Definition of Done

- Web opens locally.
- API health endpoint returns `ok`.
- Worker process starts and registers tasks.
- Compose starts API + worker + Redis (+ DB + web).
- README and setup docs provide exact local run steps.

### Validation

- `bash scripts/dev-up.sh` starts full stack.
- `GET /v1/health` succeeds.
- Worker logs show registered task names.
- `pytest services/api/tests services/worker/tests` passes baseline tests.

### Security Notes

- Keep local defaults practical; do not require production auth to boot.
- No secrets committed; env-driven config only.

### Interview Talking Points

- Why monorepo boundaries were chosen.
- Why async workers exist even before full AI integrations.
- Why local reliability and reproducibility matter early.

---

## M2 - Authentication + User Dashboard

### Scope

- Clerk in web app.
- Route protection with middleware.
- Backend JWT verification with cached JWKS.
- Identity extraction dependency in FastAPI.
- Protected dashboard after login.
- Dashboard includes document list and upload flow to pipeline entrypoint.

### Definition of Done

- Sign-in works with Clerk.
- Unauthenticated dashboard access redirects.
- API can identify caller from bearer token.
- Dashboard shows documents and supports upload + ingest completion flow.

### Validation

- Manual auth flow test (signed-in vs signed-out behavior).
- API `/v1/auth/me` returns user identity with valid token.
- Upload flow calls:
  - `POST /v1/documents`
  - direct S3 `PUT`
  - `POST /v1/documents/{id}/ingest-complete`

### Security Notes

- Enforce JWT template/audience alignment between web and API.
- Keep `local` demo bypass only for local developer ergonomics.
- Do not leak token parsing internals in auth errors.

### Interview Talking Points

- Why JWKS caching is used and how rotation is handled safely.
- Tradeoff between developer-local bypass and production auth strictness.
- Ownership boundary enforcement at API layer.

---

## M3 - Supabase Database + Core Models

### Scope

- Supabase Postgres integration.
- Runtime pooler URL and migration direct URL strategy.
- SQLAlchemy/SQLModel model baseline.
- Alembic migrations.
- Core tables: documents, detections, redactions, summaries, exports, jobs/events.

### Definition of Done

- Migrations run forward on clean database.
- Backend creates and reads test document records.
- Ownership fields are present and enforced.

### Validation

- `alembic upgrade head` succeeds in local/staging.
- CRUD smoke tests pass against Supabase-connected runtime.

### Security Notes

- Hybrid model: backend ownership checks + targeted RLS on sensitive tables.

### Interview Talking Points

- Why pooler vs direct DB URLs are separated.
- Why migrations are mandatory for production safety.

---

## M4 - Website-First Upload Flow with S3 Presigned URLs

### Scope

- Authenticated web upload flow for PDFs.
- KMS-encrypted S3 originals bucket usage.
- Presigned PUT URL generation in API.
- Ingest completion endpoint and dashboard listing.

### Definition of Done

- Authenticated user uploads PDF from web.
- Object exists in S3 originals bucket.
- Document row exists and status transitions to `UPLOADED`.

### Validation

- Browser upload smoke test.
- API verifies S3 object existence before queueing detection.

### Security Notes

- Content-type and size validation on presign.
- Short-lived presigned URLs.

### Interview Talking Points

- Why direct-to-S3 is preferred over API file proxying.

---

## M5 - Async Job System + Status Tracking

### Scope

- Queue processing kickoff after ingest completion.
- Status lifecycle updates by worker.
- Status polling endpoint and dashboard indicators.
- Retries and failure states for jobs.

### Definition of Done

- Upload triggers queued job.
- Worker moves status through lifecycle.
- Dashboard reflects transitions.

### Validation

- Queue + worker integration test.
- Retry and failure path smoke test.

### Security Notes

- Idempotent worker updates; avoid duplicated side-effects.

### Interview Talking Points

- Why async boundary improves latency and reliability.

---

## M6 - Textract OCR + Layout Extraction
## M7 - Comprehend PII Detection + Span Mapping
## M8 - Document Modes + Policy Engine
## M9 - Web Review UI + Redaction Controls
## M10 - True PDF Redaction Export
## M11 - AI Summary Engine (LangChain + Bedrock)
## M12 - Notifications + UX Polish
## M13 - Security Hardening + SOC 2 Readiness
## M14 - OpenTelemetry Observability
## M15 - CI/CD Pipeline
## M16 - Terraform Infrastructure
## M17 - ECS Deployment
## M18 - Optional Kubernetes Path

Detailed milestone specifications for `M6` through `M18` are defined in `docs/MILESTONES_DETAILED.md`. This split keeps this file concise and execution-oriented while preserving full milestone depth.

---

## Phase Gates

- Gate A (`M1-M2`): local stack + auth + dashboard + upload entrypoint.
- Gate B (`M3-M5`): persistent model + queued lifecycle reliability.
- Gate C (`M6-M11`): real data-plane intelligence and redaction correctness.
- Gate D (`M12-M15`): product polish, security, and delivery maturity.
- Gate E (`M16-M18`): production infrastructure and deployment paths.

---

## Evidence-Driven Development Policy

Every merged step must include:

- code change
- docs update
- validation evidence
- explicit statement of remaining known gaps

---

## Next Execution Target

`M1`–`M3` are complete. Execution order from here is defined by the compressed
phase plan in `docs/ROAD_FULL_IMPLEMENTATION.md` (phases `R0`–`R9`), which is the
master workflow. This file remains the reference for milestone rationale and
interview talking points.
