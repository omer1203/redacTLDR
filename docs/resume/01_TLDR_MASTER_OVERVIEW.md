# 01 — RedacTLDR Master Overview

> Companion docs: [Architecture](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md) · [Features & Roadmap](03_TLDR_FEATURES_STATUS_AND_ROADMAP.md) · [Resume & Interview](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md) · [Context Handoff](05_TLDR_CONTEXT_HANDOFF.md)

**Audit date:** 2026-07-27  
**Repository:** `redacTLDR` (local path and GitHub remote owned by `omer1203`)  
**Scope rule:** Claims require repository evidence. Planned and stubbed work is never presented as complete.

---

## 1. Executive Summary

### One-paragraph explanation

RedacTLDR is a website-first SaaS codebase for privacy-preserving PDF document intelligence: authenticated users upload PDFs via S3 presigned URLs, the API records ownership and lifecycle state in PostgreSQL, Celery workers run async detect/export/summary jobs, and a Next.js dashboard lists documents and drives upload. Detection, true redaction, and Bedrock AI summaries are scaffolded with stub implementations; M1–M3 (local stack, Clerk auth, schema/RLS) are marked completed in project status docs and match substantial code evidence.

### One-sentence explanation

RedacTLDR helps users upload sensitive PDFs, detect and redact PII, and produce safer summarized outputs—currently with a working auth/upload/job foundation and placeholder intelligence stages.

### Nontechnical explanation

Think of a secure document locker: you sign in, upload a PDF, the system tracks what happened to it, and later it is supposed to black out private details and give you a safe summary. Today you can sign in, upload, and see document status; the “smart blackout and summary” parts are still being built (they run placeholder logic so the pipeline can be tested).

### Technical explanation

Monorepo with Next.js App Router (`apps/web`) + Clerk, FastAPI orchestration (`services/api`), Celery/Redis workers (`services/worker`), PostgreSQL via SQLAlchemy/Alembic (Supabase-oriented RLS deny policies), and S3 presigned PUT/GET. Document ownership is enforced with `owner_user_id` checks. Worker tasks update a `jobs` table but use regex stub detection, synthetic PDF export, and placeholder summaries—not live Textract/Comprehend/Bedrock.

### Recruiter-friendly explanation

Full-stack privacy SaaS project: React/Next.js frontend, Python FastAPI backend, background workers, cloud object storage, and auth. Strong foundation for secure document upload and multi-tenant-style ownership; AI redaction pipeline milestones remain in progress.

### 30-second interview explanation

“RedacTLDR is a privacy-focused document platform I’m building. Users authenticate with Clerk, upload PDFs directly to S3 using short-lived presigned URLs, and the FastAPI backend tracks ownership and job state in Postgres. Celery workers handle detect, export, and summary asynchronously. The intelligence stages are still stubs—regex PII and placeholder summaries—while the auth, schema, upload, and job orchestration layers are implemented.”

### 60-second interview explanation

“The product goal is upload → detect PII → review redactions → export a truly redacted PDF → generate mode-specific AI summaries for resumes, employment, medical, legal, and terms documents. Architecturally it’s a monorepo: Next.js dashboard protected by Clerk, FastAPI with JWKS JWT verification and a local demo-auth bypass, Celery workers, Redis, Postgres with Alembic migrations and restrictive RLS so PostgREST anon/authenticated roles cannot read app tables, and dual S3 buckets for originals and downloads. I’ve completed foundation through schema/auth/upload orchestration (milestones M1–M3 in our plan). Detection doesn’t yet call AWS Textract/Comprehend; export rewrites PDFs with pikepdf but doesn’t apply true redaction annotations; summaries return schema-shaped placeholders. CI runs pytest, web lint/typecheck/build, Docker image builds, and Trivy/Syft scanning. Terraform scaffolds S3/ECR/ECS cluster only—not a full production deploy.”

### What is implemented / incomplete / planned / significant

| Area | Status |
| ---- | ------ |
| Local Compose stack (web, api, worker, postgres, redis) | Implemented |
| Clerk + local demo auth | Implemented |
| Dashboard upload + list | Implemented |
| S3 presign + ingest-complete + ownership checks | Implemented (hardening in progress) |
| Alembic schema, jobs table, soft deletes, RLS deny policies | Implemented |
| Celery detect/export/summary with retries + job status | Partially implemented (stubs) |
| Review UI overlays | Planned / not present in UI |
| Real OCR/PII/Bedrock | Planned |
| True PDF redaction | Prototype (geometry + pikepdf rewrite only) |
| ECS production deploy | Planned (scaffold only) |

**Business value designed for:** safer sharing of sensitive PDFs (resume anonymization, employment, medical, legal, T&Cs) without exposing raw PII to downstream AI summarization—when the intelligence milestones land.

---

## 2. Product and Business Context

### Actual product domain

**Privacy-preserving document intelligence / PDF redaction SaaS** — not a creator directory, talent marketplace, portfolio platform, or CMS.

| Category from audit template | Present? |
| ---------------------------- | -------- |
| Creator directory / talent marketplace | Not present |
| Portfolio / public profile platform | Not present |
| Content-management / CMS | Not present |
| Multi-role public web app with visitors browsing creators | Not present |
| AI-assisted business application | **Designed / partially scaffolded** |
| Authenticated document operations platform | **Yes** |
| Administrative management system | Not present (no staff admin UI) |
| Internal operations platform | Partial (audit API for own events only) |

### Intended user groups (from product docs + code)

| Group | Problems addressed | Evidence |
| ----- | ------------------ | -------- |
| Authenticated end user | Upload sensitive PDFs; track status; (future) review/export/summarize | Dashboard + document APIs |
| Local developer | Iterate without Clerk | `x-demo-user` when `ENVIRONMENT=local` |
| Staff / admin / moderator | N/A in code | Not present |
| Anonymous public visitor | Landing page only | `apps/web/app/page.tsx` |

### Use-case classes

- **Public-facing:** marketing-style landing page; no public document/profile SEO directory.
- **Authenticated:** upload PDF, list documents, poll status.
- **Administrative:** none implemented.
- **Revenue/marketplace:** none in code.
- **CMS:** none.
- **AI workflows:** API + worker stubs + mode schemas; Bedrock model ID in config only.

---

## 3. User and Role Inventory

There are **no** Django-style staff/superuser/creator roles. Identity is Clerk subject (`sub`) or local demo user id. Authorization is **object ownership**, not RBAC roles.

| Role | Purpose | Main Capabilities | Restrictions | Frontend Experience | Backend Enforcement | Evidence |
| ---- | ------- | ----------------- | ------------ | ------------------- | ------------------- | -------- |
| Anonymous visitor | See product pitch | View `/` | No dashboard if Clerk on | Landing links | N/A | `apps/web/app/page.tsx` |
| Local demo user | Dev without Clerk | Upload/list via `x-demo-user` | Only when `ENVIRONMENT=local` | Dashboard without login | `get_current_user` demo branch | `auth.py` L68–70; `dashboard/page.tsx` L16–25 |
| Authenticated Clerk user | Product user | Upload/list documents; API calls with JWT | Only own documents | `/dashboard`, sign-in/up | JWT + `owner_user_id` | `auth.py` L72–102; `documents.py` `_require_document` |
| Staff / Admin / Superuser / Creator / Talent | — | — | — | — | — | **Not present** |

### Permission dimensions present

| Dimension | Status |
| --------- | ------ |
| Authentication state | Yes (Clerk or demo) |
| User role field | Not present |
| Staff / superuser | Not present |
| Object ownership | Yes (`owner_user_id`) |
| Organization / tenant (`workspace_id`) | Column exists; always `None` on create |
| Feature-level permissions | Not present |

---

## 4. Main Product Workflows

### 4.1 Authentication (Clerk or local demo)

1. **Business purpose:** Identify callers for ownership-scoped APIs.  
2. **User:** End user / developer.  
3. **Trigger:** Visit `/dashboard` or call API.  
4. **Frontend:** Clerk middleware protects `/dashboard`; server page calls `getToken({ template })`.  
5. **API:** `Authorization: Bearer` or local `x-demo-user`.  
6. **Logic:** JWKS fetch/cache + `jose` JWT decode.  
7. **DB:** No user table; identity is string id on documents/jobs/audit.  
8. **Validation:** Audience/issuer when Clerk configured.  
9. **Permissions:** Authenticated principal required on protected routes.  
10. **Output:** `UserPrincipal`.  
11. **Errors:** 401 missing/invalid token.  
12. **Status:** Implemented.  
13. **Evidence:** `services/api/app/auth.py`; `apps/web/middleware.ts`; `apps/web/app/dashboard/page.tsx`.  
14. **Resume relevance:** High.

### 4.2 Create document + presigned upload + ingest

1. **Purpose:** Get PDF into S3 and queue detection without proxying bytes through API.  
2. **User:** Authenticated / demo.  
3. **Trigger:** Dashboard form submit.  
4. **Frontend:** `createDocument` → `uploadFileToPresignedUrl` → `completeIngest`.  
5. **API:** `POST /v1/documents`, client `PUT` to S3, `POST .../ingest-complete`.  
6. **Logic:** Key naming, PDF content-type + size checks, HeadObject verify, enqueue `detect_job`.  
7. **DB:** `documents` CREATED→UPLOADED→DETECT_QUEUED; `jobs` detect QUEUED; audit events.  
8. **Validation:** filename, content type PDF, max size.  
9. **Permissions:** Owner-only.  
10. **Output:** Document id + status.  
11. **Errors:** 400/401/409/503.  
12. **Status:** Implemented (M4 hardening still in progress per status JSON).  
13. **Evidence:** `documents.py` L86–228; `s3.py`; `dashboard-client.tsx` L77–88.  
14. **Resume relevance:** High.

### 4.3 List documents + status polling

1. **Purpose:** Show user’s documents and in-flight statuses.  
2–12. React Query list + 5s refetch while active statuses.  
13. **Status:** Implemented.  
14. **Evidence:** `GET /v1/documents`; `dashboard-client.tsx` L67–74.

### 4.4 Detection job (stub)

1. **Purpose:** Find PII candidates.  
12. **Status:** Partially implemented / prototype — regex on synthetic text, not OCR of uploaded PDF.  
13. **Evidence:** `tasks.py` `detect_job` L130–170.  
14. **Resume relevance:** Medium (pipeline/orchestration); do not claim production PII detection.

### 4.5 Manual redactions + review-state APIs (no UI)

1. **Purpose:** Store reviewer instructions; serve review payload.  
12. **Status:** Backend partial; **no review UI**.  
13. **Evidence:** `POST .../redactions`, `GET .../review-state`; no frontend callers in `apps/web/lib/api.ts`.  
14. **Resume relevance:** Medium as API design; low as shipped UX.

### 4.6 Export + summary (stub)

12. **Status:** Prototype — queue/API/DB wired; worker uses fake PDF / placeholder summary; export does not upload redacted bytes to S3.  
13. **Evidence:** `export_job`, `summary_job`; `redaction.py` comments.  
14. **Resume relevance:** Mention as foundation only.

### 4.7 Audit event listing

12. **Status:** Implemented for own events; no staff cross-user audit UI.  
13. **Evidence:** `GET /v1/audit`; `log_event` from document routes.

### Workflows from template that are Not present

Visitor browsing public profiles, creator registration/onboarding, portfolio, staff approval, CMS, public SEO page generation, contact forms, password recovery UI (Clerk-hosted only), AI chat/streaming UI, marketplace.

---

## 5. Repository Map

| Directory | Purpose | Classification | Active? | Read order |
| --------- | ------- | -------------- | ------- | ---------- |
| `apps/web/` | Next.js product UI | Frontend / core | Yes | 1 |
| `services/api/` | FastAPI API | Backend / core | Yes | 2 |
| `services/worker/` | Celery workers | Backend / core | Yes | 3 |
| `alembic/` | DB migrations | Data | Yes | 4 |
| `ops/compose/` | Local Docker stack | Infrastructure | Yes | 5 |
| `ops/docker/` | API/worker images | Infrastructure | Yes | 6 |
| `ops/k8s/helm/` | Optional K8s | Infrastructure / prototype | Scaffold | Later |
| `infra/terraform/` | AWS S3/ECR/ECS scaffold | Infrastructure / partial | Scaffold | Later |
| `.github/workflows/` | CI + security scan | Infrastructure | Yes | 7 |
| `scripts/` | dev-up, S3 CORS, seed | Supporting | Yes | 8 |
| `docs/` | Architecture, milestones | Documentation | Yes | Parallel |
| `docs/resume/` | This audit set | Documentation | Yes | After code |
| `frontend/mobile/` | Expo prototype | Frontend / deferred | Prototype | Optional |
| `apps/mobile/` | Empty placeholder | Unknown / unused | No | Skip |
| `backend/` | Legacy stub remnant | Legacy | No | Skip |

**Major files:** `services/api/app/main.py`, `auth.py`, `models.py`, `routes/documents.py`, `services/s3.py`, `services/worker/app/tasks.py`, `apps/web/components/dashboard-client.tsx`, `ops/compose/docker-compose.yml`.

---

## 6. Technology Summary

| Technology | Category | Actual Usage | Status | Evidence | Resume Strength |
| ---------- | -------- | ------------ | ------ | -------- | --------------- |
| Python 3 | Language | API + worker | Active | `services/` | Strongly demonstrated |
| FastAPI | Backend | HTTP API | Active | `main.py` | Strongly demonstrated |
| SQLAlchemy 2 | ORM | Models + sessions | Active | `models.py`, `db.py` | Strongly demonstrated |
| Alembic | Migrations | 2 revisions | Active | `alembic/versions/` | Strongly demonstrated |
| PostgreSQL 16 | Database | Compose + Supabase-oriented | Active | compose + migrations | Strongly demonstrated |
| Celery + Redis | Async jobs | detect/export/summary | Active (stub logic) | `tasks.py`, compose | Strongly demonstrated |
| boto3 / S3 | Storage | Presign PUT/GET, HeadObject | Active | `s3.py` | Strongly demonstrated |
| Clerk | Auth | JWT JWKS + Next middleware | Active | `auth.py`, middleware | Strongly demonstrated |
| Next.js 15 / React 19 | Frontend | App Router dashboard | Active | `apps/web` | Strongly demonstrated |
| TanStack Query | Frontend state | Document list/upload | Active | `dashboard-client.tsx` | Moderately demonstrated |
| Tailwind CSS | Styling | Utility classes | Active | web components | Moderately demonstrated |
| Zustand | State | In package.json | Light / unclear usage in dashboard | `apps/web/package.json` | Lightly demonstrated |
| pikepdf | PDF | Rewrite path, not true redact | Prototype | `redaction.py` | Moderately demonstrated |
| OpenTelemetry | Observability | Optional OTLP | Partial | `telemetry.py`, compose profile | Moderately demonstrated |
| Docker / Compose | DevOps | Local stack | Active | `ops/compose` | Strongly demonstrated |
| GitHub Actions | CI | pytest, web build, image build | Active | `.github/workflows/ci.yml` | Strongly demonstrated |
| Syft / Trivy | Security CI | SBOM + vuln scan | Active | `security.yml` | Moderately demonstrated |
| Terraform | IaC | S3, ECR, ECS cluster name | Partial scaffold | `infra/terraform/main.tf` | Moderately demonstrated |
| Helm | K8s | Chart scaffold | Prototype | `ops/k8s/helm` | Lightly demonstrated |
| LangChain / Bedrock | AI | Deps + config model id; no live path | Planned / dependency | `requirements.txt`, `BEDROCK_MODEL_ID` | Dependency only / Planned only |
| Expo / React Native | Mobile | Deferred prototype | Prototype | `frontend/mobile` | Lightly demonstrated |
| Django / DRF | Backend | — | **Not present** | Search | Do not claim |
| Elasticsearch / Algolia | Search | — | Not present | — | Do not claim |

---

## 7. Current Project Status

### Fully implemented (evidence-backed)

- Local Compose development stack and scripts  
- Health endpoint  
- Clerk JWT auth + local demo auth  
- Document create/list/get with ownership  
- Presigned upload orchestration + ingest verification  
- Audit log write (on document events) + list own events  
- Alembic migrations including jobs + RLS deny policies  
- CI lint/typecheck/build/pytest/Docker build  
- Security workflow SBOM/Trivy  

### Partially implemented

- Async job system (queue + status real; payload logic stub)  
- S3 upload hardening (M4 in_progress)  
- OTel (collector profile + basic instrument)  
- Terraform / Helm / ECS  

### Experimental / prototype

- pikepdf export path  
- Regex detection  
- Placeholder summaries  
- Expo mobile upload client  

### Planned (docs M6–M13, M17–M18)

- Textract OCR, Comprehend PII, policy engine depth, review UI, true redaction, Bedrock summaries, notifications, SOC2 program, ECS deploy  

### Known gaps / debt

- Thin tests (no route/integration/e2e)  
- Large uncommitted working tree vs 8 commits  
- Stale notes in some docs (`EXECUTION_PLAN` still says M3 next)  
- Export job does not upload artifact to S3  
- `workspace_id` unused  
- No staff roles  

### Deployment status

- **Local containerized:** supported  
- **Production:** no evidence of live production traffic in-repo; Terraform/ECS incomplete  

---

## 8. Key Numbers

| Metric | Value | How counted |
| ------ | ----- | ----------- |
| Backend service packages | 2 | `services/api`, `services/worker` |
| ORM models | 7 | Classes in `models.py` |
| Alembic migrations | 2 | Files in `alembic/versions/*.py` (excl. `.gitkeep`) |
| Registered API HTTP endpoints | 16 | Decorators on `main` + auth + audit + documents routers |
| Frontend App Router pages | 4 | `page.tsx` under `apps/web/app` |
| User roles (product RBAC) | 0 named roles; 2 auth modes | Clerk vs demo |
| Meaningful reusable UI components | ~3 | `DashboardClient`, `Providers`, `DocumentRow` (inline) |
| Test files | 4 | Under `services/*/tests` |
| Test functions | 7 | `def test_` count via ripgrep |
| External integrations wired in code | Clerk, S3/AWS, Redis, Postgres, optional OTLP | Config + clients |
| Public SEO routes / sitemap | 0 specialized | No `sitemap.xml` / `robots.txt` found |
| Git commits (all history) | 8 | `git log --oneline --all` |
| Distinct Git author identities | 2 display names, 1 person | `omer1203` (7), `Omer` (1), same email |
| Uncommitted changed/untracked paths (audit time) | ~56 | `git status --short` |

These are engineering counts, **not** business-impact metrics.

---

## 9. Audit Completion Checklist

| Area | Status |
| ---- | ------ |
| Root-level files | Inspected |
| Backend `services/api` | Inspected |
| Backend `services/worker` | Inspected |
| Legacy `backend/` | Inspected (unused stub) |
| Frontend `apps/web` | Inspected |
| Frontend `frontend/mobile` | Inspected |
| `apps/mobile` placeholder | Inspected (empty) |
| Shared libs | Inspected (types/api in web) |
| Django apps / settings / URLs | **Not present** |
| FastAPI routers / schemas / models | Inspected |
| Alembic migrations | Inspected |
| Auth (Clerk + demo) | Inspected |
| Authorization (ownership) | Inspected |
| S3 / media | Inspected |
| Celery jobs | Inspected |
| AI / LLM live path | Inspected — planned/stub only |
| SEO (metadata, sitemap, robots, OG) | Inspected — minimal metadata only |
| CMS | **Not present** |
| Search/directory | **Not present** |
| Tests | Inspected |
| Docker / Compose | Inspected |
| CI/CD | Inspected |
| Terraform / Helm | Inspected |
| Env templates | Inspected (placeholders only documented) |
| Docs / milestones / ADRs | Inspected |
| TODO/FIXME/stub comments | Inspected |
| Git history / authorship | Inspected |
| Production runtime / analytics | **Access unavailable** (no prod metrics in repo) |
| Secrets / real credentials | Not reproduced; templates only |

---

## 10. Questions for the Project Owner

1. Confirm preferred resume project title (personal project vs company product name).  
2. Confirm sole-author treatment of `omer1203` / `Omer` (Git supports this).  
3. Is there a live production deployment? URL/environment name (no secrets)?  
4. Any real user/creator counts, traffic, or SEO audit scores to confirm? (None found in repo.)  
5. Should uncommitted WIP be described as “current work in progress” on resume, or only committed history?  
6. Has Supabase RLS been validated in a shared project beyond local/docs playbooks?  
7. Cosign “sign-images” job currently echoes a placeholder— intentional?  
8. Any team collaborators not reflected in Git author names?

---

*Next: detailed architecture in [02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md).*
