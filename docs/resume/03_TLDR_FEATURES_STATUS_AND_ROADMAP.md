# 03 — Features Status and Roadmap

> Companions: [Overview](01_TLDR_MASTER_OVERVIEW.md) · [Architecture](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md) · [Resume](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md) · [Handoff](05_TLDR_CONTEXT_HANDOFF.md)

Implementation-status definitions follow the audit charter: **Implemented**, **Partially Implemented**, **Prototype**, **Planned**, **Legacy**, **Unused**, **Unclear**.

---

## 1. Feature Catalog

### Local development stack (Compose)

* Business purpose: Run full system locally  
* Intended users: Developers  
* UX: `scripts/dev-up.sh` starts web/api/worker/postgres/redis  
* Frontend/Backend/DB: All compose services  
* APIs: health  
* Testing: smoke via playbooks  
* Main files: `ops/compose/docker-compose.yml`, `scripts/dev-up.sh`  
* Status: **Implemented**  
* Evidence: compose services L3–98; README quick start  
* Limitations: Requires Docker; S3 is real AWS not LocalStack  
* Complexity: Medium  
* Resume relevance: High  
* Ownership: Verified sole-author repo (committed + WIP)  
* Planned improvements: LocalStack optional path (not present)

### Clerk authentication + JWT API verification

* Business purpose: Secure multi-user identity  
* Users: End users  
* UX: Sign-in/up routes; protected dashboard  
* Frontend: middleware + dashboard token mint  
* Backend: JWKS cache + RS256 decode + audience  
* DB: No users table; string subject ids  
* Endpoints: `/v1/auth/me`; all protected document routes  
* Validation: Bearer format, `sub` required  
* Permissions: Authenticated principal  
* Integrations: Clerk  
* Testing: Demo auth unit only  
* Files: `auth.py`, `middleware.ts`, `dashboard/page.tsx`, sign-in/up pages  
* Status: **Implemented**  
* Evidence: `auth.py` L57–102; `middleware.ts` L1–13  
* Limitations: Demo bypass in local; JWKS cache per-process  
* Resume relevance: High  
* Ownership: Verified personal (sole author)

### Local demo auth (`x-demo-user`)

* Purpose: Developer ergonomics without Clerk  
* Status: **Implemented** (local-only)  
* Evidence: `auth.py` L68–70; dashboard demo branch  
* Resume relevance: Medium  
* Ownership: Verified

### Dashboard document list + PDF upload

* Purpose: Primary authenticated workflow  
* UX: Form (file, mode, safe mode) + status list with polling  
* Frontend: `DashboardClient`  
* Backend: create + ingest-complete + list  
* DB: documents + audit + jobs  
* Endpoints: `POST/GET /v1/documents`, ingest-complete  
* Validation: PDF client + server content-type/size  
* Permissions: Owner  
* Integrations: S3  
* Testing: No UI/route tests  
* Status: **Implemented**  
* Evidence: `dashboard-client.tsx` L57–186; `documents.py` L86–228  
* Limitations: No detail page; no review/export/summary actions in UI  
* Resume relevance: High  

### S3 presigned upload + ingest verification

* Purpose: Direct-to-cloud upload without API byte proxy  
* Status: **Implemented** / M4 hardening **in_progress** (status JSON)  
* Evidence: `s3.py` L77–118; ingest HeadObject checks  
* Limitations: Relies on correct bucket CORS; Content-Type not bound on presign  
* Resume relevance: High  

### Document ownership + soft-delete filters

* Purpose: Prevent cross-user access  
* Status: **Implemented** (soft delete columns exist; delete API not exposed)  
* Evidence: `_require_document` L44–64  
* Resume relevance: High  

### Async jobs table + Celery enqueue

* Purpose: Durable job visibility beyond Celery  
* Status: **Partially Implemented** (wiring real; business logic stub)  
* Evidence: `_queue_job_record`; `_update_job_status`; tasks  
* Resume relevance: High (orchestration)  

### PII detection

* Purpose: Find sensitive entities  
* Status: **Prototype** — regex on synthetic sample text, not uploaded PDF/OCR  
* Evidence: `detect_job` L130–170; comments Textract/Comprehend future  
* Resume treatment: Mention as prototype / pipeline foundation only  
* Planned: M6/M7  

### Manual redactions API

* Purpose: Store user redaction instructions  
* Status: **Partially Implemented** — API append-only; **no UI**  
* Evidence: `POST .../redactions` L255–288; not in `lib/api.ts`  
* Resume relevance: Medium  

### Review state API

* Purpose: Bundle detections + redactions for review UI  
* Status: **Partially Implemented** — API only; activity always `[]`  
* Evidence: `get_review_state` L409–460  
* Planned UI: M9  

### PDF export / true redaction

* Purpose: Produce downloadable redacted PDF  
* Status: **Prototype** — queues job; pikepdf rewrite without redact annotations; no S3 upload of bytes  
* Evidence: `export_job` L173–228; `redaction.py` L1–48  
* Resume treatment: Prototype / do not claim true redaction shipped  

### AI structured summaries

* Purpose: Mode-specific safe summaries  
* Status: **Prototype** — schema-shaped placeholder; Bedrock not called  
* Evidence: `summary_job`; `summary.py`; mode schema endpoint  
* Integrations: `BEDROCK_MODEL_ID` config only  
* Resume treatment: Planned / prototype only  

### Document modes schema

* Purpose: Contract for mode-specific summary fields  
* Status: **Implemented** (static JSON)  
* Evidence: `mode_schema` L463–513; validation tests  
* Note: Endpoint lacks `CurrentUser` dependency  

### Audit logging

* Purpose: Trace key document actions  
* Status: **Implemented** for write+list own events  
* Evidence: `log_event` usage; `GET /v1/audit`  
* No frontend consumer  

### OpenTelemetry hooks

* Purpose: Traces when OTLP endpoint set  
* Status: **Partially Implemented**  
* Evidence: api/worker `telemetry.py`; compose profile `observability`  
* Milestone: M14 in_progress  

### CI/CD + security scanning

* Purpose: Quality and vulnerability gates  
* Status: **Partially Implemented** — CI real; deploy chain incomplete; Cosign placeholder  
* Evidence: `.github/workflows/ci.yml`, `security.yml`  
* Milestones: M15 in_progress  

### Terraform AWS scaffold

* Purpose: Infra as code for S3/ECR/ECS  
* Status: **Partially Implemented** — buckets/ECR/cluster; no task defs/VPC/RDS  
* Evidence: `infra/terraform/main.tf`  
* Milestone: M16 in_progress  

### Helm chart

* Purpose: Optional K8s deploy  
* Status: **Prototype** scaffold  
* Milestone: M18 planned  

### Expo mobile client

* Purpose: Mobile upload  
* Status: **Prototype** / deferred  
* Evidence: `frontend/mobile/App.tsx`; README deferred note  
* Limitations: No Clerk headers; possible API drift  

### Legacy backend package

* Status: **Legacy / Unused**  
* Evidence: `backend/app/workers/detect.py` stub; ADR-0001; commit removing entrypoints  

### Creator directory / CMS / public SEO profiles / staff admin / AI chat

* Status: **Not present** (template leads do not apply)

---

## 2. Feature Status Matrix

| Feature | Frontend | Backend | Database | Permissions | Tests | Deployment Evidence | Overall Status | Confidence |
| ------- | -------- | ------- | -------- | ----------- | ----- | ------------------- | -------------- | ---------- |
| Compose local stack | Y | Y | Y | N/A | Smoke docs | Local only | Implemented | High |
| Clerk + JWT | Y | Y | N/A | AuthN | Thin | Config-dependent | Implemented | High |
| Demo auth | Y | Y | N/A | Local only | Unit | Local | Implemented | High |
| Upload + list | Y | Y | Y | Owner | Missing route tests | Local | Implemented | High |
| S3 presign/ingest | Y | Y | Y | Owner | Missing | Needs AWS buckets | Implemented / hardening WIP | High |
| Jobs + Celery | Partial UI status | Y | Y | Owner | Missing | Local compose | Partial | High |
| Detection | Status only | Stub | Y | Owner | Missing | Local | Prototype | High |
| Manual reded | N | Y | Y | Owner | N | — | Partial | High |
| Review UI | N | API only | Y | Owner | N | — | Planned/Partial | High |
| Export true redact | N | Stub | Y | Owner | Geometry only | — | Prototype | High |
| Summaries AI | N | Stub | Y | Owner | Schema unit | — | Prototype | High |
| Audit API | N | Y | Y | Own events | N | — | Implemented | High |
| OTel | N/A | Partial | N/A | N/A | N | Profile | Partial | Medium |
| CI | N/A | N/A | N/A | N/A | pytest in CI | GitHub Actions | Partial (no CD) | High |
| Terraform | N/A | N/A | N/A | N/A | N | Scaffold | Partial | High |
| Mobile | Prototype | Uses API | — | Weak/none | N | — | Prototype | High |
| SEO platform | Minimal | N/A | N/A | N/A | N | — | Minimal | High |
| CMS / directory | N | N | N | N | N | — | Not present | High |

---

## 3. Public-Facing Features

| Item | Status |
| ---- | ------ |
| Landing page | Implemented (static) |
| Directory / profile pages | Not present |
| Search/filters | Not present |
| Contact workflows | Not present |
| CMS pages | Not present |
| Legal/policy pages | Not present |
| Public media | Not present (private S3) |
| Sharing | Not present |

---

## 4. Creator or Member Features

Mapped to **authenticated document owner** (not “creator” role):

| Item | Status |
| ---- | ------ |
| Registration | Clerk sign-up (when enabled) |
| Onboarding | Not present beyond sign-up |
| Dashboard | Implemented (upload/list) |
| Profile/portfolio | Not present |
| Media management | Upload originals only |
| Account settings | Clerk-managed; no custom |
| Visibility controls | Private by ownership only |
| Approval workflows | Not present |
| Analytics | Not present |

---

## 5. Staff and Administrative Features

**Not present** — no staff dashboards, moderation, role management, CMS, or cross-user reporting UI. Audit list is self-scoped only.

---

## 6. SEO Feature Status

| Category | Detail |
| -------- | ------ |
| Completed | Static `title` + `description` in root layout |
| Partial | — |
| Planned | None specified in milestone docs as SEO program |
| Audit-supported metrics | **None** |
| Metrics requiring confirmation | Any claimed Lighthouse/SEO score |
| Pages lacking rich metadata | All beyond root defaults |
| Sitemap / robots / canonical / OG | Not present |
| Indexing concerns | Landing is indexable by default; dashboard should remain auth-gated (Clerk) |

**Resume:** Do not include SEO engineering bullets for this repo.

---

## 7. AI and Internal Tool Status

| Capability | Classification |
| ---------- | -------------- |
| Summary worker placeholder | Prototype |
| Mode schema + validation helpers | Development-connected foundation |
| Masking helper | Backend utility (unit-tested); not proven in live detect path |
| Bedrock / LangChain runtime | Planned / dependency only |
| Chat UI / streaming | Not present |
| Textract / Comprehend | Planned (docs + task comments) |

---

## 8. Incomplete and Broken Workflows

| Issue | Evidence |
| ----- | -------- |
| Review/export/summary APIs without frontend | `lib/api.ts` only create/list/ingest/upload |
| Detection ignores uploaded PDF content | `detect_job` synthetic `sample_text` |
| Export does not upload PDF to S3 | `export_job` updates DB only |
| True redaction not applied | `redaction.py` docstring |
| Summary not LLM-backed | placeholder markdown string |
| Soft delete unused by API handlers | columns exist; no delete route |
| `workspace_id` always None on create | `documents.py` create |
| Mobile may omit `mode` / auth | `frontend/mobile/App.tsx` |
| Modes schema unauthenticated | no CurrentUser on handler |
| Stale EXECUTION_PLAN “next = M3” | vs MILESTONE_STATUS M3 completed |
| Route/integration tests missing | only 7 unit tests |
| Cosign job placeholder | `security.yml` |

---

## 9. Dead, Legacy, and Duplicate Code

| Code Area | Why unused/legacy | Replacement | Risk | Evidence |
| --------- | ----------------- | ----------- | ---- | -------- |
| `backend/app/workers/detect.py` | Legacy layout | `services/worker` | Confusion if run | stub file + ADR-0001 |
| `apps/mobile/` empty dirs | Placeholder | `frontend/mobile` deferred | Low | empty scaffold |
| `ingestDone` alias | Compat duplicate | Prefer `ingest-complete` | Low drift | documents.py L237–240 |
| Document `user_id` + `owner_user_id` | Dual fields | Prefer owner_user_id | Sync bugs if diverged | models.py comments |

Do not delete in this audit.

---

## 10. Technical Debt

### Architecture

* Problem: Intelligence milestones stubbed behind production-shaped APIs  
* Evidence: tasks.py stubs  
* Impact: Callers may believe exports/summaries are real  
* Resolution: Feature flags or status labels; implement M6–M11  
* Priority: High  
* Complexity: Large  

### Backend

* Dual identity columns; append-only “upsert” reded  
* Priority: Medium · Complexity: Small–Medium  

### Frontend

* No review/export/summary UX; minimal design system  
* Priority: High for product completeness · Complexity: Large  

### Database

* Soft delete without API; workspace unused  
* Priority: Medium · Complexity: Medium  

### API design

* Public `modes/schema` under authenticated router prefix without auth dep  
* Priority: Low · Complexity: Small  

### Permissions

* No RBAC/workspaces yet despite columns  
* Priority: Medium · Complexity: Large  

### Security

* No rate limiting; demo auth footgun if mis-set ENVIRONMENT  
* Priority: High for prod · Complexity: Medium  

### Testing

* No HTTP/integration/e2e tests  
* Priority: High · Complexity: Medium  

### Performance

* No load evidence; offset pagination only  
* Priority: Low now · Complexity: Medium  

### SEO / Accessibility

* Minimal metadata; basic form labels only  
* Priority: Low for current private SaaS · Complexity: Small  

### Deployment

* Terraform/ECS incomplete; Cosign placeholder  
* Priority: High for prod · Complexity: Large / Requires external AWS  

### Documentation

* Some status docs disagree on “next milestone”  
* Priority: Medium · Complexity: Small  

### Developer experience

* Large uncommitted delta vs short Git history  
* Priority: Medium · Complexity: Small (commit hygiene)

---

## 11. Future and Planned Features

| Planned Feature | Evidence | Foundation | Missing Work | Dependencies | Blockers | Resume Treatment |
| --------------- | -------- | ---------- | ------------ | ------------ | -------- | ---------------- |
| Textract OCR (M6) | MILESTONE_STATUS, tasks comments | Job pipeline, detections table | AWS integration, layout | AWS account | Cost/credentials | Do not include as shipped |
| Comprehend PII (M7) | same | detections model | Real detector | AWS | same | Mention as designed |
| Policy engine (M8) | docs | mode + safe_mode fields | Rules engine | Product rules | Spec | Interview only |
| Review UI (M9) | docs; review-state API | API envelope | Overlay UI | Frontend time | — | Partially implemented (API) |
| True PDF export (M10) | redaction.py comments | pikepdf path, export table | Annotations + S3 put | pikepdf skill | Correctness | Mention as prototype |
| Bedrock summaries (M11) | config + stub | schema + summary table | LangChain/Bedrock path | AWS Bedrock | Cost/safety | Mention as integration-ready foundation |
| Notifications polish (M12) | docs | — | All | — | — | Do not include |
| SOC2 readiness (M13) | docs | some controls | Program | Org process | Requires external dependency | Do not include |
| OTel depth (M14) | telemetry + collector | hooks | Metrics/dashboards | Collector | — | Mention as partial |
| CI/CD completion (M15) | workflows | CI + scans | Deploy CD, real signing | Registry | — | Mention CI; not full CD |
| Terraform depth (M16) | main.tf | S3/ECR/cluster | Network/data/ECS services | AWS | — | Mention as scaffold |
| ECS deploy (M17) | README target | cluster resource | Services, IAM, networking | AWS | — | Do not claim deployed |
| Optional K8s (M18) | Helm chart | templates | Complete values/prod | Cluster | Optional | Do not include |

---

## 12. Recommended Roadmap

### Immediate Stabilization

| Item | Current → Desired | Foundation | Work | Risk | Priority | Files | Done when |
| ---- | ----------------- | ---------- | ---- | ---- | -------- | ----- | --------- |
| Mis-set ENVIRONMENT exposing demo auth | Local-only gate works → documented prod checklist | auth.py | Fail closed tests | Auth bypass | P0 | auth.py, config | Non-local rejects demo header (tested) |
| Export falsely “EXPORTED” without object | DB says ready → object exists or status honest | export_job | Upload or fail | User trust | P0 | tasks.py, s3 | HeadObject succeeds for download |
| Align status docs | Conflicting next milestone → single SoT | MILESTONE_STATUS | Fix EXECUTION_PLAN | Confusion | P1 | docs | Consistent |

### Feature Completion

| Item | Notes |
| ---- | ----- |
| Review UI against review-state | M9 |
| Wire detect to real PDF bytes | M6/M7 |
| True redaction + S3 put | M10 |
| Bedrock summaries with safe_mode masking | M11 |

### Testing and Reliability

| Item | Notes |
| ---- | ----- |
| API route tests for ownership 401/404 | Critical |
| Ingest integration with mocked S3 | M4 |
| Worker failure/retry tests | M5 |

### SEO and Public Platform

| Item | Notes |
| ---- | ----- |
| Only if public marketing site expands | robots/sitemap optional; not current product core |

### Operational / Admin

| Item | Notes |
| ---- | ----- |
| Workspace/RBAC if multi-tenant needed | uses existing columns |
| Cross-user admin audit | not started |

### AI and Automation

| Item | Notes |
| ---- | ----- |
| Replace stubs per M6–M11 only | keep placeholders out of “done” claims |

### Deployment and Observability

| Item | Notes |
| ---- | ----- |
| Complete Terraform ECS path | M16–M17 |
| Real image signing | replace Cosign placeholder |
| OTel dashboards | M14 |

---

## 13. Questions for the Project Owner

1. Production URL / environment existence?  
2. Which milestones are truly user-facing today beyond upload/list?  
3. Confirm whether any Bedrock calls exist outside this repo.  
4. SEO scores or marketing-site work elsewhere?  
5. Priority between review UI vs real detection next?  
6. Should mobile remain deferred on resume?  
7. Supabase project shared vs local-only Postgres?  
8. Business outcomes (users, documents processed) for metrics confirmation?

---

*Resume-safe wording and interview cards: [04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md](04_TLDR_RESUME_AND_INTERVIEW_GUIDE.md).*
