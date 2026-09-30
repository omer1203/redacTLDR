# 05 — Context Handoff (Compressed Memory)

> Read this first in a new session. Deep detail lives in [01](01_TLDR_MASTER_OVERVIEW.md) · [02](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md) · [03](03_TLDR_FEATURES_STATUS_AND_ROADMAP.md) · [04](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md).

**Audit date:** 2026-07-27 · **Output dir:** `docs/resume/` (exactly five Markdown files)

---

## 1. Project Identity

| Field | Value |
| ----- | ----- |
| Project name | RedacTLDR (`redacTLDR` repo) |
| Purpose | Privacy-preserving PDF document intelligence SaaS |
| Product type | Authenticated document workflow platform (not a creator directory/CMS) |
| Main users | Authenticated document owners; local developers (demo auth) |
| Primary problem | Upload sensitive PDFs and (eventually) detect/redact PII + summarize safely |
| Status | M1–M3 completed per project status docs; M4+ partial/planned; intelligence stages stubbed |

---

## 2. Verified Technology Stack

| Layer | Active tech |
| ----- | ----------- |
| Backend | Python, FastAPI, SQLAlchemy, Alembic, Pydantic, Celery |
| Frontend | Next.js 15, React 19, TypeScript, TanStack Query, Tailwind, Clerk |
| Database | PostgreSQL (+ Supabase-oriented RLS deny policies) |
| Authentication | Clerk JWT/JWKS; local `x-demo-user` |
| Storage | AWS S3 presigned PUT/GET |
| AI | **Stub/planned** (Bedrock model id in config; placeholder workers) |
| Testing | pytest (thin unit tests) |
| DevOps | Docker Compose, GitHub Actions, Syft/Trivy |
| Deployment | Terraform scaffold (S3/ECR/ECS cluster); Helm optional scaffold |

**Not present:** Django, DRF, creator marketplace, CMS, sitemap/robots SEO program.

---

## 3. Architecture Summary

- **Frontend:** `apps/web` — landing, Clerk sign-in/up, dashboard upload/list with polling.  
- **Backend:** `services/api` — FastAPI routers auth/documents/audit.  
- **Worker:** `services/worker` — Celery detect/export/summary (stub logic).  
- **DB:** 7 models; 2 Alembic migrations; soft deletes; jobs table.  
- **AuthZ:** `owner_user_id` checks (`_require_document`), not RBAC.  
- **Storage:** originals + downloads buckets; API does not proxy PDF bytes.  
- **SEO:** static layout metadata only.  
- **CMS/AI chat:** none.  
- **Deploy:** local Compose primary; ECS intended later.

---

## 4. Major Implemented Features

Link to [03 Feature Catalog](03_TLDR_FEATURES_STATUS_AND_ROADMAP.md#1-feature-catalog) and [02 API Inventory](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md#3-api-inventory).

- Local Compose stack + health  
- Clerk + local demo auth  
- Dashboard PDF upload + document list  
- S3 presign + ingest-complete verification  
- Owner-scoped document APIs + audit log  
- Alembic schema, jobs, RLS deny policies  
- CI + container builds + vulnerability scans  

---

## 5. Partial and Incomplete Features

- Celery pipeline with **stub** detect/export/summary  
- pikepdf export without true redaction / without S3 upload of bytes  
- Review/export/summary **APIs without web UI**  
- OTel, Terraform, Helm, Cosign signing placeholder  
- Expo mobile deferred prototype  
- Thin tests (no route/e2e)

---

## 6. Planned Features

From `docs/MILESTONE_STATUS.json` / milestones: Textract (M6), Comprehend (M7), policy engine (M8), review UI (M9), true export (M10), Bedrock summaries (M11), polish/SOC2 (M12–13), deeper OTel/CI/Terraform (M14–16), ECS (M17), optional K8s (M18).

---

## 7. Important Files and Symbols

| Area | Important Files | Important Symbols | Purpose |
| ---- | --------------- | ----------------- | ------- |
| API entry | `services/api/app/main.py` | `app`, `startup`, `health` | ASGI app |
| Auth | `services/api/app/auth.py` | `get_current_user`, `_fetch_jwks` | JWT/demo |
| Documents | `services/api/app/routes/documents.py` | `_require_document`, `create_document`, `_ingest_complete` | Core API |
| S3 | `services/api/app/services/s3.py` | `presign_put`, `get_original_object_metadata` | Uploads |
| Models | `services/api/app/models.py` | `Document`, `Job`, … | Schema |
| Worker | `services/worker/app/tasks.py` | `detect_job`, `export_job`, `summary_job` | Async stubs |
| Redaction | `services/worker/app/redaction.py` | `redact_pdf_bytes`, `clamp_bbox` | Prototype |
| Web UI | `apps/web/components/dashboard-client.tsx` | `DashboardClient` | Upload UX |
| Web API | `apps/web/lib/api.ts` | `createDocument`, `completeIngest` | Client |
| Middleware | `apps/web/middleware.ts` | `clerkMiddleware` | Route protect |
| Migrations | `alembic/versions/eb35da4c4c2e_*.py` | RLS policies | M3 |
| Compose | `ops/compose/docker-compose.yml` | services | Local runtime |
| Status | `docs/MILESTONE_STATUS.json` | milestones[] | Plan tracker |

---

## 8. Verified Personal Contributions

- **Git:** All 8 commits by `omer1203` / `Omer` (same email); remote `omer1203/redacTLDR`.  
- **Confidence:** Verified sole author of committed history.  
- **Caveat:** Large uncommitted WIP (~56 paths) includes Alembic, Clerk routes, docs, API/worker M3 work — attribute as personal working tree pending commits; do not invent coauthors.  
- Uncertain until owner confirms: employment framing, production deploy, business metrics.

---

## 9. Resume Summary

| Item | Guidance |
| ---- | -------- |
| Strongest angle | Full-stack / backend privacy SaaS foundation |
| Role categories | SE, Full-Stack, Backend/Python, React (supporting) |
| Safest four bullets | Clerk JWT + owner APIs; S3 presign upload; Postgres/Alembic/RLS; Celery + Docker/CI scans |
| Important skills | FastAPI, Next.js, Postgres, S3, Celery, Clerk, Docker, GHA |
| Metrics needing confirmation | Users, traffic, prod uptime, SEO scores, “N documents” |
| Claims to avoid | Finished true redaction, live Bedrock/OCR, SEO gains, SOC2, ECS production, Django/CMS/creator platform |

Details: [04](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md).

---

## 10. Current Questions

1. Personal project vs company title on resume?  
2. Any live production environment?  
3. Confirm metrics (users/docs/SEO)?  
4. Commit WIP before citing M3 migrations as “on main”?  
5. Mobile still deferred for resume?  
6. Any off-Git collaborators?

---

## 11. Documentation Navigation

| Topic | Authoritative file |
| ----- | ------------------ |
| What the product is / nontechnical | [01](01_TLDR_MASTER_OVERVIEW.md) |
| Architecture, API, DB, security, setup | [02](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md) |
| Feature status, debt, roadmap | [03](03_TLDR_FEATURES_STATUS_AND_ROADMAP.md) |
| Resume bullets, ATS, interviews | [04](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md) |
| Session memory | This file |

Project milestone docs outside this folder (`docs/MILESTONE_STATUS.json`, etc.) are inputs; **code wins** on conflicts.

---

## 12. Continuation Instructions

* **Analyzed:** Repo inventory, API/worker/web/auth/S3/DB/CI/terraform, Git authorship, SEO absence, stub AI, resume material.  
* **Incomplete / access unavailable:** Live production runtime, analytics, private AWS account state, unreproducible SEO scores.  
* **Before new claims:** Re-read code paths; update status labels; never promote stubs to “implemented.”  
* **Updates:** Edit these five files only; consolidate; link across files.  
* **Do not** create a sixth Markdown audit file unless explicitly authorized.  
* **Do not** modify production application source for documentation-only tasks.

---

## 13. Copy-Paste Continuation Prompt

```
Read docs/resume/05_TLDR_CONTEXT_HANDOFF.md first. Then read only the linked sections of the other TLDR audit documents under docs/resume/ that are relevant to the current task. Treat the codebase as the source of truth. Do not invent implementation status, metrics, ownership, or business outcomes. Distinguishing implemented vs stubbed intelligence (detect/export/summary) is mandatory. Update the existing five audit files when new verified information is discovered. Do not create additional Markdown documentation unless explicitly authorized.
```
