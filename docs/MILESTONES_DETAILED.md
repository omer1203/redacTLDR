# RedacTLDR Detailed Milestones (Canonical M1-M18)

This document is the full milestone specification. It is intentionally detailed and should be used as the implementation and review contract.

## Status Legend

- `completed`: implemented and verified
- `in_progress`: partially implemented
- `planned`: designed but not implemented
- `blocked`: cannot proceed due to dependency

## Legacy Mapping (Preserved)

Previous milestone references in old docs and task comments are preserved conceptually:

- old `M3` (detection stub) maps to new `M7`
- old `M5` (export stub) maps to new `M10`
- old `M6` (summary stub) maps to new `M11`

This mapping avoids confusion while keeping history intact.

---

## M1 - Foundation / Local Development Stack

### Goal

Establish a stable local environment where web, API, worker, DB, and Redis run together predictably.

### Current Status

`completed`

### Build

- Repository structure and ownership boundaries.
- Next.js app baseline.
- FastAPI app baseline with `/v1/health`.
- Celery worker startup with task registration.
- Dockerfiles and compose stack.
- Run scripts and setup documentation.

### Definition of Done

- `scripts/dev-up.sh` boots stack.
- `GET /v1/health` returns success.
- Worker registers tasks and stays healthy.
- Local docs are accurate and sufficient for first-time setup.

### Out of Scope

- Production deployment.
- Real OCR/PII/LLM integrations.

### Validation

- health endpoint check
- API/worker test suite baseline
- compose smoke run

### Risks and Mitigations

- Drift between docs and runtime -> maintain docs per milestone.
- Local-only assumptions creeping into production code -> isolate `ENVIRONMENT=local` behavior.

### Interview Signal

- Full-stack runtime bootstrapping discipline.

---

## M2 - Authentication + User Dashboard

### Goal

Add secure identity handling and a protected website entrypoint for document workflows.

### Current Status

`completed`

### Build

- Clerk middleware and protected routes.
- Sign-in and sign-up entrypoints.
- FastAPI JWT verification with cached JWKS.
- Dashboard with authenticated data access.
- Upload + list UX in dashboard.

### Definition of Done

- Signed-out users are redirected from protected pages.
- Signed-in users can reach dashboard.
- API `/v1/auth/me` resolves identity from token.
- Dashboard can list documents and start upload ingest flow.
- JWT template/audience alignment is enforced.

### Out of Scope

- Org/workspace RBAC.
- Advanced account workflows.

### Validation

- manual auth flow test
- API token verification test
- dashboard fetch with bearer token

### Security Notes

- local demo user bypass remains local-only.
- no sensitive auth exceptions returned to client.

### Interview Signal

- Correct separation of authn (identity) and authz (ownership checks).

---

## M3 - Supabase Database + Core Models

### Goal

Move to production-grade persistence discipline and migration safety.

### Current Status

`completed`

### Build

- Supabase runtime connectivity via pooler.
- Direct migration URL for Alembic.
- Core relational model and indexes.
- Migration workflow and rollback strategy.

### Definition of Done

- migrations run from clean state
- app boots without `create_all` in non-local
- CRUD paths validated against Supabase

### Validation

- alembic upgrade
- integration DB smoke tests

### Security Notes

- ownership fields required on document-linked entities
- selective RLS introduction plan

---

## M4 - Website-First Upload Flow with S3 Presigned URLs

### Goal

Enable authenticated direct browser-to-S3 PDF upload with API orchestration.

### Build

- originals bucket integration
- KMS-backed storage policy
- presign service with content-type/size checks
- ingest complete endpoint
- dashboard upload progress

### Definition of Done

- PDF uploads from dashboard to S3
- document transitions to `UPLOADED`
- list endpoints show correct status and metadata

### Validation

- upload smoke test
- ingest endpoint idempotency check

---

## M5 - Async Job System + Status Tracking

### Goal

Convert upload completion into queued background processing with visible state transitions.

### Build

- enqueue job after ingest complete
- document/job status model (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`)
- polling endpoint for status
- retry semantics and error handling

### Definition of Done

- queue receives job
- worker consumes job and updates status
- dashboard reflects status changes

### Validation

- Redis outage and retry behavior checks
- worker retry backoff verification

---

## M6 - Textract OCR + Layout Extraction

### Goal

Extract text and geometry from source PDFs for downstream detection and review.

### Build

- Textract wrapper service
- worker S3 fetch and Textract invocation
- parse pages/lines/words and normalized coordinates
- OCR storage policy controls (raw/masked/encrypted)

### Definition of Done

- test PDF produces OCR output with geometry
- document reaches OCR completion status

---

## M7 - Comprehend PII Detection + Custom Entity Strategy

### Goal

Detect sensitive entities and map them to reviewable geometry.

### Build

- Comprehend wrapper
- chunk/page PII detection
- entity normalization and confidence handling
- span-to-bbox mapping
- detection persistence with safe storage defaults

### Definition of Done

- detections persisted per document
- each detection has page + bbox
- raw sensitive text storage respects policy

---

## M8 - Document Type Modes + Policy Engine

### Goal

Make behavior mode-specific and policy-driven rather than generic.

### Build

- mode selection and storage
- mode-specific redaction defaults
- mode-specific summary schema contracts
- workspace policy config (safe mode, OCR storage, export constraints)

### Definition of Done

- mode affects backend behavior for redaction/summaries
- policy checks are enforced by service layer

---

## M9 - Web Review UI with Redaction Overlays

### Goal

Add human-in-the-loop review controls over AI detections.

### Build

- review page
- PDF rendering with overlay boxes
- detection list and toggle controls
- manual redaction creation
- persistence APIs and optimistic UI updates

### Definition of Done

- user can enable/disable detections
- user can add manual redaction boxes
- edits persist and reload correctly

---

## M10 - Secure PDF Export with True Text Removal

### Goal

Generate export PDFs where redacted content is actually removed, not visually hidden only.

### Build

- export worker pipeline
- map approved redactions to PDF coordinates
- apply true text removal using PDF tooling
- upload output to downloads bucket
- export record and retrieval endpoint

### Definition of Done

- exported PDF contains true redactions
- copy/paste does not reveal redacted text
- export artifact downloadable via presigned URL

### Security Notes

- export correctness tests are mandatory
- preserve audit evidence of export inputs and outputs

---

## M11 - AI Summary Engine with LangChain + Bedrock

### Goal

Generate structured, mode-aware summaries with optional safe-mode masking.

### Build

- LangChain summarization pipeline
- Bedrock model integration (single-model strategy v1)
- map-reduce for long documents
- structured outputs per mode
- persistence and summary UI

### Definition of Done

- generated summary stored and viewable
- output schema varies by mode
- safe mode masking enforced when enabled

---

## M12 - Notifications + Product Polish

### Goal

Improve user trust and workflow clarity for async processing.

### Build

- in-app notifications
- optional email notifications
- robust loading/error/empty states
- dashboard history improvements

### Definition of Done

- users receive actionable progress and completion feedback

---

## M13 - Security Hardening + SOC 2 Readiness

### Goal

Enforce privacy/security controls in code and operations.

### Build

- KMS encryption and key policy hardening
- least-privilege IAM
- audit event coverage
- no raw PII logs
- selective RLS + backend authorization checks
- threat model documentation

### Definition of Done

- sensitive actions auditable
- secrets managed safely
- policy checks enforced

---

## M14 - Observability with OpenTelemetry

### Goal

Enable tracing, logging, and metrics for diagnosis and SLO ownership.

### Build

- API and worker instrumentation
- trace propagation across async boundaries
- structured logs
- metrics for latency, queue, failure, and stage durations
- collector and dashboard target integration

### Definition of Done

- document processing flow traceable end-to-end
- key operational metrics emitted

---

## M15 - CI/CD Pipeline

### Goal

Automate quality, security scanning, and deployment workflow.

### Build

- PR checks: lint, typecheck, tests
- image build and push
- SBOM generation
- vulnerability scanning
- image signing
- deploy orchestration with migration safety

### Definition of Done

- PR gates are reliable
- main builds deployable artifacts
- security scanning integrated in pipeline

---

## M16 - Terraform Infrastructure

### Goal

Provision reproducible cloud infrastructure with environment isolation.

### Build

- modules/resources for S3, KMS, IAM, ECR, ECS, logs, secrets
- optional networking/alarm resources
- environment-specific naming and outputs

### Definition of Done

- `terraform plan/apply` provisions core platform reliably

---

## M17 - ECS Deployment

### Goal

Run API, worker, and web in production-like managed containers.

### Build

- ECS task definitions and services
- image pull from ECR
- secret injection via SSM/Secrets Manager
- logging and health checks

### Definition of Done

- deployed API responds healthy
- worker runs and processes jobs
- web can call deployed API

---

## M18 - Optional Kubernetes Deployment Path

### Goal

Provide a documented alternative deployment path without replacing ECS as primary.

### Build

- k8s manifests or helm chart for API/worker (+ dependencies/config)
- docs comparing ECS and Kubernetes tradeoffs

### Definition of Done

- optional deployment path is runnable and documented

---

## Governance Rules for All Milestones

- No milestone marked `completed` without validation evidence.
- Every milestone update must revise:
  - `docs/IMPLEMENTATION_STATUS.md`
  - `docs/MILESTONE_STATUS.json`
- Security/privacy implications are documented at each stage, not only at `M13`.
# Redactr Detailed Milestones

This file consolidates all milestones visible in the current codebase and expands them into an owner-grade roadmap.

It has two layers:

1. **Explicit milestone tags already present in code**
2. **A full consolidated milestone plan** (grounded in current implementation state)

---

## 1) Milestones Explicitly Present in Code Today

These are the only milestone IDs directly labeled inside implementation comments:

- **M3**: Detection task stub  
  - Source: `services/worker/app/tasks.py` (`detect_job` docstring says "M3 detection task stub")
- **M5**: Export task stub  
  - Source: `services/worker/app/tasks.py` (`export_job` docstring says "M5 export task stub")
- **M6**: Summary task stub  
  - Source: `services/worker/app/tasks.py` (`summary_job` docstring says "M6 summary task stub")

Interpretation:

- The project has **phase labels for deeper pipeline stages**, but those stages are currently represented by placeholder worker logic.
- Milestone tags for M1/M2/M4 are not explicitly labeled in code comments, so those are inferred from existing architecture and route behavior.

---

## 2) Consolidated Milestone Map (Owner View)

This is the practical milestone structure that matches what exists and what is still missing.

### Milestone Status Legend

- **Completed**: fully present in executable code path
- **Partial**: present but incomplete or placeholder-heavy
- **Scaffolded**: mostly docs/infrastructure skeleton
- **Not Started**: intended but not implemented in runtime path

---

## M0 - Repository and Runtime Foundation

**Status:** Completed (with cleanup debt)  
**Goal:** Establish a workable monorepo and local runtime stack.

### What this milestone covers

- Monorepo structure (`apps`, `services`, `ops`, `infra`, `docs`)
- Local Compose topology (web/api/worker/postgres/redis/otel)
- Dockerfiles for API and worker
- CI/security workflow scaffolding

### Evidence in code

- `ops/compose/docker-compose.yml`
- `ops/docker/api.Dockerfile`
- `ops/docker/worker.Dockerfile`
- `.github/workflows/ci.yml`
- `.github/workflows/security.yml`
- `docs/decisions/ADR-0001-repo-layout.md`

### Remaining gaps in M0

- Minor naming/import consistency issues remain (notably worker import path style).
- Some duplicated/legacy paths still exist (`backend/`).

### Done criteria

- Local stack starts reliably.
- API, worker, and web can run together.
- Baseline CI checks pass.

---

## M1 - API Core + Auth + Data Model

**Status:** Completed (core), Partial (production maturity)  
**Goal:** Build secure API control-plane with user scoping and persistent lifecycle records.

### What this milestone covers

- FastAPI app entrypoint and route registration
- Clerk JWT validation and current-user dependency
- SQLAlchemy models for documents/detections/redactions/exports/summaries/audit
- Core endpoints under `/v1/auth`, `/v1/documents`, `/v1/audit`

### Evidence in code

- `services/api/app/main.py`
- `services/api/app/auth.py`
- `services/api/app/models.py`
- `services/api/app/routes/auth.py`
- `services/api/app/routes/documents.py`
- `services/api/app/routes/audit.py`

### Remaining gaps in M1

- No migration system (startup `create_all` is still used).
- Authorization model is user-level only (no org/workspace roles).
- Route module is becoming orchestration-heavy.

### Done criteria

- Authenticated users can only access their own records.
- Document lifecycle rows are created and updated via API.
- Audit events are written for core actions.

---

## M2 - Async Pipeline Skeleton (Queue + Worker + Status Machine)

**Status:** Completed skeleton  
**Goal:** Wire API events to background jobs and reflect state transitions in DB.

### What this milestone covers

- Celery client in API + Celery app in worker
- Task routing and consumption through Redis
- `detect_job`, `export_job`, `summary_job` invocation from API routes
- Status transitions (`DETECT_QUEUED`, `EXPORTED`, `SUMMARIZED`, etc.)

### Evidence in code

- `services/api/app/celery_client.py`
- `services/worker/app/celery_app.py`
- `services/worker/app/tasks.py`
- Document status enum in `services/api/app/enums.py`

### Remaining gaps in M2

- Dead-letter queue policy is still not configured.
- API and worker need fuller integration tests for broker outages and retries.

### Done criteria

- Jobs reliably enqueue and execute.
- DB status transitions are visible through API polling endpoints.

---

## M3 - Detection Pipeline (Real OCR + PII)

**Status:** Partial (stubbed under explicit M3 label)  
**Goal:** Replace placeholder detection with real extraction and detection.

### What exists now

- `detect_job` runs and writes rows to `detections`.
- Current detection logic uses regex against synthetic text, not real document text.

### What must be implemented

- Fetch source PDF from S3 originals bucket.
- OCR/layout extraction (Textract path).
- PII/entity detection (Comprehend path or equivalent).
- Mapping detected entities to reviewable geometry.
- Confidence and source metadata that reflect real inference.

### Primary files to evolve

- `services/worker/app/tasks.py`
- `services/worker/app/geometry.py`
- potentially new extraction/detection service modules

### Dependencies

- AWS credentials + IAM for Textract/Comprehend
- Reliable source object retrieval from S3

### Done criteria

- `detections` table is derived from actual uploaded document content.
- Detection quality and geometry are reviewable and reproducible.

---

## M4 - Review State + Human-in-the-Loop Controls

**Status:** Partial  
**Goal:** Provide full review workflow for accepting/rejecting suggestions and adding manual redactions.

### What exists now

- API endpoint to save manual redactions.
- API `review-state` response envelope combining detections/redactions.
- Data model supports manual redaction records.

### What is missing

- Web review UI (overlay rendering, selection, toggles, revision UX).
- Detection acceptance workflow updates (currently mostly static assumptions).
- Collaboration/activity stream behavior in `review-state` (`activity` is empty).

### Primary files to evolve

- `services/api/app/routes/documents.py` (review semantics)
- `apps/web` dashboard/components (new review pages/components)

### Done criteria

- User can complete full review pass from browser.
- Review decisions are persisted and become export input.

---

## M5 - True Redaction Export Engine

**Status:** Partial (stubbed under explicit M5 label)  
**Goal:** Generate truly redacted export PDFs from approved redaction inputs.

### What exists now

- Export queuing route and `exports` records.
- `redact_pdf_bytes` helper validates geometry and rewrites bytes through pikepdf.
- Worker marks export status as `EXPORTED`.

### What is missing

- Read original PDF from S3.
- Apply approved redaction geometry from detections/manual redactions to real pages.
- Upload generated export PDF to downloads bucket.
- Verify object existence and integrity before returning download URL.

### Primary files to evolve

- `services/worker/app/tasks.py`
- `services/worker/app/redaction.py`
- `services/api/app/services/s3.py`

### Done criteria

- Export artifact in S3 is actually redacted content from source PDF.
- Download endpoint only returns URL for verified generated export.
- Redaction correctness tests exist for representative edge cases.

---

## M6 - Summary Generation Pipeline

**Status:** Partial (stubbed under explicit M6 label)  
**Goal:** Produce mode-specific, privacy-safe summaries from real document text.

### What exists now

- Summary queue and persistence are functional.
- Worker writes placeholder JSON/markdown payload.
- Mode concepts exist in enums and schema/template helpers.

### What is missing

- Build masked text from real content and accepted redaction set.
- Real LLM invocation (Bedrock and/or LangChain orchestration).
- Mode-specific extraction quality checks and confidence logic.
- Citation reliability against source chunks/blocks.

### Primary files to evolve

- `services/worker/app/tasks.py`
- `services/worker/app/summary.py`
- `services/api/app/services/summary_schema.py`
- `services/api/app/services/validation.py`

### Done criteria

- Summary payloads come from actual doc content.
- Output schema is valid per mode and includes useful citations/confidence.
- Safe mode guarantees are enforced and testable.

---

## M7 - Website Product Surface (Upload, Review, Export, Summary UX)

**Status:** Partial  
**Goal:** Implement full web experience beyond document listing.

### What exists now

- Public landing page.
- Clerk-protected dashboard route.
- Document listing with TanStack Query.

### What is missing

- Upload flow UI and ingest completion.
- Detection/review UI.
- Export request and download UX.
- Summary request and structured display UX.
- Audit history/inspection UX.

### Primary files to evolve

- `apps/web/app/dashboard/*` (new nested routes/pages)
- `apps/web/components/*` (workflow components)
- `apps/web/lib/api.ts` (expand API bindings)
- `apps/web/lib/types.ts` (align with backend payloads)

### Done criteria

- User can complete end-to-end pipeline entirely from web.
- UI transparently shows processing states and failures.

---

## M8 - Data Governance, Privacy, and Security Controls

**Status:** Partial/Scaffolded  
**Goal:** Turn privacy-first design claims into enforceable controls.

### What exists now

- User-scoped data access pattern in routes.
- Presigned URL architecture.
- Audit table and event logging hooks.
- Security scanning workflow scaffold in GitHub Actions.

### What is missing

- Retention cleanup execution despite `RETENTION_DAYS` config.
- Strong immutability posture for audit logs.
- Export/redaction correctness guarantees in tests.
- Secrets manager integration and tighter runtime secret boundaries.

### Done criteria

- Retention policies are enforced in code and operations.
- Security-sensitive flows have explicit tests and alerting.

---

## M9 - Infrastructure Productionization

**Status:** Scaffolded  
**Goal:** Move from local/dev scaffolding to production-grade deployment.

### What exists now

- Terraform baseline resources (S3, ECR, ECS cluster).
- Optional Helm chart skeleton.
- CI image build and security scan workflows.

### What is missing

- ECS task/service definitions and networking setup.
- ALB/TLS and service exposure strategy.
- IAM task roles with least privilege.
- secrets management (parameter store/secrets manager integration).
- autoscaling, alarms, observability backend wiring.

### Done criteria

- Deployable staging/prod stacks with secure defaults.
- Operational playbooks and rollback strategy exist.

---

## M10 - QA, Reliability, and Launch Readiness

**Status:** Not Started (beyond baseline unit tests)  
**Goal:** Ensure trustworthy end-to-end behavior and operability.

### What exists now

- Baseline unit tests for helper logic and validation.

### What is missing

- Integration tests for API + DB + queue.
- End-to-end tests for upload -> detect -> review -> export -> summary.
- Reliability tests for retries, duplicate jobs, partial failures.
- SLO-oriented observability and alerting thresholds.

### Done criteria

- Critical workflows are covered by deterministic E2E/integration tests.
- Failure modes are observable and recoverable.

---

## 3) Milestone Dependency Graph (Practical Execution Order)

Recommended order:

1. **M1/M2 hardening** (stability before feature depth)
2. **M3 detection real implementation**
3. **M4 review workflow completion**
4. **M5 true export correctness**
5. **M6 real summaries**
6. **M7 full web UX**
7. **M8 governance/security hardening**
8. **M9 infra productionization**
9. **M10 QA/reliability gates**

Reasoning:

- M3-M6 are core value pipeline steps.
- M7 depends on backend behavior being reliable enough to expose.
- M8-M10 are required for trust and production confidence.

---

## 4) Current Milestone Snapshot (Quick View)

- **Completed:** M0, core M1, M2 skeleton
- **Partial:** M3, M4, M5, M6, M7, M8
- **Scaffolded:** M9
- **Not Started (at full depth):** M10

If you want, this can be split next into a sprint-ready version (`MILESTONES_EXECUTION_PLAN.md`) with:

- story-sized tasks
- owner labels
- estimated effort
- weekly sequencing
- explicit "definition of done" checklist per ticket

