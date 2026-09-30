# 04 — Resume and Interview Guide

> Companions: [Overview](01_TLDR_MASTER_OVERVIEW.md) · [Architecture](02_TLDR_ARCHITECTURE_AND_IMPLEMENTATION.md) · [Features](03_TLDR_FEATURES_STATUS_AND_ROADMAP.md) · [Handoff](05_TLDR_CONTEXT_HANDOFF.md)

**Rules used:** No invented metrics, users, SEO scores, or “production scale.” Ownership uses Git history + sole-author remote; large uncommitted WIP is called out. Prefer **safe wording** unless you personally confirm stronger claims.

---

## 1. Personal Contribution Analysis

### Git facts (verified 2026-07-27)

| Fact | Value |
| ---- | ----- |
| Total commits | 8 |
| Authors | `omer1203` (7), `Omer` (1) — same person/email |
| Remote | `github.com:omer1203/redacTLDR.git` |
| Branch | `main` |
| Co-authors | None observed |
| Uncommitted paths | ~56 (substantial M3/Clerk/docs/alembic WIP) |

### Commit themes

| Commit (short) | Theme |
| -------------- | ----- |
| Initial commit | Project setup |
| services API/worker foundation | Backend monorepo foundation |
| web dashboard + mobile update | Frontend workspace |
| CI + deployment scaffolding | DevOps |
| Remove legacy backend entrypoints | Layout cleanup |
| Trivy/security workflow fixes | CI security |

### Ownership matrix

| Feature | Repository Evidence | Git Evidence | Ownership Confidence | Confirmation Needed |
| ------- | ------------------- | ------------ | -------------------- | ------------------- |
| Monorepo services layout | `services/*` | Foundation commit | Verified personal contribution | Whether employment vs personal project title |
| Web dashboard upload/list | `apps/web` | Web commit + WIP | Verified / Strongly associated | WIP not all committed |
| Clerk JWT + demo auth | `auth.py`, middleware | WIP + prior web | Strongly associated | Confirm you authored Clerk JWT template setup |
| S3 presign + ingest | `s3.py`, documents routes | Foundation + WIP | Strongly associated | — |
| Alembic + RLS | `alembic/versions/*` | Mostly untracked at audit time | Strongly associated (working tree) | Commit before citing as “in main history” |
| Celery job stubs | `tasks.py` | Foundation + WIP | Verified personal | Do not overclaim intelligence |
| CI/Trivy/Syft | `.github/workflows` | Multiple commits | Verified personal contribution | — |
| Terraform scaffold | `infra/terraform` | CI/deploy commit | Verified personal | Not full prod |
| True redaction / Bedrock | stubs only | N/A complete feature | Should not claim personally as shipped | — |
| Team features | — | No other authors | Cannot determine team process | Ask if others contributed off-Git |

**Caveat:** Treat **committed** history as verified; treat **uncommitted** work as your likely contribution pending commit, but say “implemented in the codebase” rather than “merged to main on DATE” until committed.

---

## 2. Resume Evidence Matrix

| Proposed Claim | Code Evidence | Business Meaning | Completion | Ownership | Metric Evidence | Overstatement Risk | Safe Wording |
| -------------- | ------------- | ---------------- | ---------- | --------- | --------------- | ------------------ | ------------ |
| Built FastAPI document API with ownership checks | `documents.py`, `models.py` | Users only see own PDFs | Implemented | Sole author | — | Low | “Implemented FastAPI document APIs with owner-scoped access control” |
| Clerk JWT verification with JWKS caching | `auth.py` | Secure API auth | Implemented | Sole author | — | Low | “Integrated Clerk JWT verification with JWKS caching for the API” |
| Presigned S3 upload pipeline | `s3.py`, dashboard client | Direct secure uploads | Implemented | Sole author | — | Medium if claim “hardened production” | “Built PDF upload flow using S3 presigned URLs and ingest verification” |
| Celery async jobs with retries | `tasks.py` | Offload processing | Partial (stub logic) | Sole author | — | High if claim PII/OCR | “Designed Celery workers for detect/export/summary with retries and DB job status” |
| Postgres schema + Alembic + RLS policies | migrations | Data isolation posture | Implemented | Sole author (WIP commit state) | — | Medium | “Modeled document lifecycle in Postgres with Alembic migrations and restrictive RLS policies” |
| Next.js dashboard with React Query | dashboard-client | Usable upload UX | Implemented | Sole author | — | Low | “Built Next.js dashboard for PDF upload and status polling” |
| CI with lint, tests, image builds, vuln scan | workflows | Quality/security gates | Partial CD | Sole author | — | Medium if claim full CD | “Added GitHub Actions CI for pytest, web typecheck/build, Docker builds, and Trivy/Syft scans” |
| True PDF redaction product | redaction.py stub | Remove PII from PDFs | Prototype | Sole author | — | **Do not use** as shipped | “Prototyped PDF export pipeline with pikepdf (true redaction pending)” |
| Bedrock AI summaries | placeholder | Safe summaries | Prototype | Sole author | — | **Do not use** as shipped | “Scaffolded mode-specific summary schemas and worker stubs pending Bedrock integration” |
| Improved SEO by X% | none | Marketing | N/A | — | None | **Do not use** | Omit |
| Scaled to N users | none | Traction | Unknown | — | None | **Do not use** | Omit or confirm |
| Production ECS deployment | terraform cluster only | Cloud run | Planned/partial | Sole author | None | **Do not use** as live | “Scaffolded Terraform for S3, ECR, and ECS cluster” |
| Built entire platform alone | sole git author | Ownership | Foundation yes; product incomplete | Verified for git | — | Medium (product unfinished) | “Sole developer of the redacTLDR codebase to date” |

---

## 3. Verified Skills

### Languages

| Skill | Classification |
| ----- | -------------- |
| Python | Strongly demonstrated |
| TypeScript / TSX | Strongly demonstrated |
| SQL (via SQLAlchemy/Alembic/raw SQL) | Strongly demonstrated |
| Bash (dev scripts) | Moderately demonstrated |

### Backend

| Skill | Classification |
| ----- | -------------- |
| FastAPI | Strongly demonstrated |
| Pydantic schemas | Strongly demonstrated |
| Celery | Strongly demonstrated |
| Redis as broker | Moderately demonstrated |
| Django / DRF | **Do not claim** |

### Frontend

| Skill | Classification |
| ----- | -------------- |
| Next.js App Router | Strongly demonstrated |
| React | Strongly demonstrated |
| TanStack Query | Moderately demonstrated |
| Tailwind CSS | Moderately demonstrated |
| Zustand | Lightly demonstrated / dependency |
| Expo / React Native | Lightly demonstrated (prototype) |

### Database

| Skill | Classification |
| ----- | -------------- |
| PostgreSQL | Strongly demonstrated |
| SQLAlchemy 2 | Strongly demonstrated |
| Alembic | Strongly demonstrated |
| RLS concepts (Supabase-oriented) | Moderately demonstrated |

### APIs / Auth

| Skill | Classification |
| ----- | -------------- |
| REST API design | Strongly demonstrated |
| Clerk authentication | Strongly demonstrated |
| JWT / JWKS | Strongly demonstrated |
| Ownership-based authorization | Strongly demonstrated |
| RBAC staff roles | **Do not claim** |

### SEO

| Skill | Classification |
| ----- | -------------- |
| Next metadata basics | Lightly demonstrated |
| Advanced SEO engineering | **Do not claim** |

### Media / storage

| Skill | Classification |
| ----- | -------------- |
| S3 presigned URLs | Strongly demonstrated |
| PDF handling (pikepdf) | Moderately demonstrated (prototype) |

### AI / LLM

| Skill | Classification |
| ----- | -------------- |
| LLM app architecture (designed) | Planned only / lightly (stubs) |
| LangChain / Bedrock production | **Dependency only / Do not claim** |
| Chat/streaming UIs | **Do not claim** |

### Testing / DevOps / Cloud / Security

| Skill | Classification |
| ----- | -------------- |
| pytest unit tests | Moderately demonstrated (thin) |
| Docker / Compose | Strongly demonstrated |
| GitHub Actions | Strongly demonstrated |
| Trivy / Syft | Moderately demonstrated |
| Terraform | Moderately demonstrated (scaffold) |
| Helm | Lightly demonstrated |
| ECS production ops | Planned only |
| OTel | Moderately / lightly |
| Security-minded upload/auth design | Strongly demonstrated |

---

## 4. ATS Keyword Mapping

### Software Engineer / Full-Stack / Backend / Python / React

| Keyword | Placement |
| ------- | --------- |
| FastAPI, Python, PostgreSQL, SQLAlchemy, Alembic | Skills, Experience, Projects |
| Next.js, React, TypeScript | Skills, Projects |
| Celery, Redis, async jobs | Skills, Projects |
| AWS S3, presigned URLs | Skills, Projects |
| Clerk, JWT, JWKS | Skills, Projects |
| Docker, Docker Compose, GitHub Actions | Skills, Experience |
| OpenTelemetry | Skills or Interview only |
| Terraform, ECR, ECS | Skills (scaffold honesty) / Interview only for “deployed” |
| pikepdf, PDF redaction | Projects with “prototype” honesty |
| LangChain, Bedrock, Textract, Comprehend | Interview only / Planned — **not Skills as production** |
| Django, SEO audit, GraphQL, Kafka | **Do not use** |

### Data Analyst / Business Analyst

Mostly **Do not use** this project as primary evidence (no analytics product). Optional: “document lifecycle status tracking” as light process data — Interview only.

### AI Application Engineer

Use carefully: architecture intent + stubs. Keywords like “LLM summarization” → Interview only / Projects with “in progress.”

### Technical Operations

Docker, CI, Trivy, Compose, Terraform scaffold → Skills / Projects.

---

## 5. Verified Metrics

### Directly verified

- 8 Git commits; sole author identities  
- 7 ORM models; 2 Alembic migrations; 16 API endpoints; 4 web pages; 4 test files; 7 test functions  
- App version string `0.2.0` in config (version label, not users)

### Safely derived

- ~56 uncommitted paths at audit time (`git status --short | wc -l`)  
- Calculation: working tree breadth ≫ commit count → resume should not imply tiny project from commit count alone

### Requires owner confirmation

- Production users, documents processed, uptime, traffic  
- SEO scores / meta description remediation counts  
- Time saved, conversion, revenue  
- Whether Supabase production project is live  
- Employment relationship / company name  

---

## 6. Resume Bullet Bank

For each bullet: Evidence · Roles · Confidence · Risk · Confirm · Interview Qs

### Software Engineering Bullets (12–20)

1. **Designed and implemented a FastAPI document orchestration API** with create/list/get, ingest completion, and owner-scoped queries.  
   Evidence: `documents.py` · Roles: SE/Backend · Confidence: high · Risk: low · Confirm: — · Q: How does ownership 404 work?

2. **Integrated Clerk JWT authentication** with JWKS caching and explicit audience validation for API requests.  
   Evidence: `auth.py` · high · low · Confirm JWT template name ok to mention · Q: Why cache JWKS?

3. **Added a local-only demo auth path** (`x-demo-user`) to speed development without disabling production auth gates.  
   Evidence: auth + dashboard · high · low · Q: How do you prevent demo auth in prod?

4. **Built an S3-backed PDF upload pipeline** using presigned PUT URLs, server-side key naming, and HeadObject ingest checks.  
   Evidence: `s3.py`, ingest · high · medium · Confirm max size/TTL values if cited · Q: Why not proxy uploads?

5. **Modeled a multi-table document lifecycle** (documents, detections, redactions, exports, summaries, jobs, audit_logs) in SQLAlchemy.  
   Evidence: `models.py` · high · low · Q: Why soft deletes?

6. **Introduced Alembic migrations** including jobs table, soft deletes, and restrictive RLS deny policies for PostgREST roles.  
   Evidence: alembic versions · high · medium (commit WIP) · Confirm applied to which env · Q: What does USING (false) achieve?

7. **Implemented Celery workers** for detect/export/summary with exponential backoff retries and job status updates.  
   Evidence: `tasks.py` · high · medium · Do not imply real OCR · Q: How are jobs correlated to DB rows?

8. **Persisted audit events** for document create/upload/detect/export/summary queue actions.  
   Evidence: audit service + routes · high · low · Q: What’s in payload?

9. **Shipped a Next.js App Router dashboard** with React Query polling for in-flight document statuses.  
   Evidence: dashboard-client · high · low · Q: When does polling stop?

10. **Containerized local development** with Docker Compose for web, API, worker, Postgres, and Redis.  
    Evidence: compose · high · low · Q: How do services discover DB/broker?

11. **Added GitHub Actions CI** running pytest, ESLint, TypeScript checks, Next build, and Docker image builds.  
    Evidence: ci.yml · high · low · Q: What fails the PR?

12. **Added SBOM generation and Trivy vulnerability scanning** uploading SARIF to GitHub code scanning.  
    Evidence: security.yml · high · medium · Q: What severity fails?

13. **Scaffolded Terraform** for dual S3 buckets (SSE, public access block, CORS), ECR repos, and an ECS cluster.  
    Evidence: terraform · high · medium · Q: What’s still missing for prod?

14. **Prototyped PDF rewrite utilities with pikepdf** and bbox clamping ahead of true redaction.  
    Evidence: redaction.py · medium · high if overstated · Q: What’s missing for true redaction?

15. **Defined mode-specific summary schemas** for resume, employment, medical, legal, and terms workflows.  
    Evidence: mode_schema + validation · high · medium · Q: How is safe mode supposed to interact?

16. **Separated API vs worker dependency sets** (`requirements-api.txt`, `requirements-worker.txt`) for slimmer images.  
    Evidence: requirements-* · medium · low · Q: Why split?

17. **Documented milestone-driven delivery** (M1–M18) with machine-readable status JSON.  
    Evidence: docs · medium · low · Q: What’s done vs planned?

18. **Migrated away from legacy backend entrypoints** toward a `services/` layout (ADR-0001).  
    Evidence: commit + ADR · high · low · Q: Why monorepo split?

### Full-Stack Bullets (10–15)

Pick from SE bullets 1–4, 9–11 plus:

19. **Connected Clerk-protected Next.js pages to FastAPI** by minting audience-specific JWT templates server-side.  
20. **Implemented end-to-end upload UX**: create document → browser PUT to S3 → ingest-complete → status list.  
21. **Supported dual auth modes** in one codebase (Clerk production path + local demo) without separate apps.

### Backend Bullets (8–12)

Prefer SE 1–8, 12–13, 16.

### Frontend Bullets (8–12)

22. **Built TypeScript API client helpers** centralizing auth headers and error parsing. Evidence: `lib/api.ts`  
23. **Implemented Clerk middleware route protection** for `/dashboard`. Evidence: `middleware.ts`  
24. **Added sign-in and sign-up App Router catch-all routes** for Clerk components.  
25. **Handled loading/error/empty states** for document queries.  
26. **Expo prototype** for health + upload (defer on resume unless asked). Risk: high if claimed production mobile.

### SEO-Focused Bullets

**Do not ship SEO-focused bullets** for this repository. Only static metadata exists.

### Data / Analytics Bullets

Omit unless you confirm reporting work elsewhere. Optional conservative: “Implemented audit event listing API for per-user action history.”

### AI Application Bullets (only honest)

27. **Scaffolded async summary generation** with JSON/markdown storage and mode templates pending Bedrock. Risk: medium–high — label as in progress.  
28. **Implemented deterministic text masking helpers** with unit tests for typed placeholders. Evidence: masking.py + tests.

### Conservative Bullets (8–10)

C1. Developed a full-stack PDF document workflow app using Next.js, FastAPI, Postgres, and Docker Compose.  
C2. Secured API access with Clerk JWTs and owner-based document authorization.  
C3. Implemented direct-to-S3 PDF uploads via presigned URLs.  
C4. Built background job processing with Celery and Redis.  
C5. Created database migrations for document lifecycle entities.  
C6. Added CI pipelines for tests, web builds, and container image builds.  
C7. Integrated vulnerability scanning into GitHub Actions.  
C8. Wrote unit tests for auth demo path, masking, summary schema validation, and geometry helpers.  
C9. Maintained architecture and milestone documentation for phased delivery.  
C10. Prototyped worker pipelines for detection, export, and summarization.

### Bullets Requiring Confirmation

- “Deployed redacTLDR to production on ECS”  
- “Processed N documents / served N users”  
- “Reduced PII leakage by X%”  
- “Improved SEO from A to B”  
- “Delivered SOC 2 controls”  
- “Shipped true redaction and Bedrock summaries”  
- “Led a team building…” (no Git coauthors)

---

## 7. Recommended Resume Sets

### General Software Engineer

1. C2 auth/ownership · 2. C3 S3 upload · 3. C4 Celery · 4. C6 CI  
Why: Balanced systems skills; ATS: FastAPI implied via project blurb. Study: `_require_document`, ingest flow.

### Full-Stack Developer

1. Bullet 20 E2E upload · 2. Bullet 19 Clerk↔API · 3. Bullet 5 data model · 4. C6 CI  
Study: dashboard-client mutation chain.

### Backend Engineer

1. Bullet 1 API · 2. Bullet 4 S3 · 3. Bullet 6 Alembic/RLS · 4. Bullet 7 Celery  
Study: job row + worker update SQL.

### Frontend Engineer

1. Bullet 9 dashboard · 2. Bullet 22 API client · 3. Bullet 23 middleware · 4. Bullet 25 states  
Study: token empty vs Clerk token paths.

### Python Developer

1. Bullet 1 · 2. Bullet 7 · 3. Bullet 6 · 4. Bullet 28 masking  
Study: SQLAlchemy models + raw worker SQL.

### SEO-Oriented Web Engineer

**Not supported** by this repo — skip set.

### AI Application Engineer

1. Bullet 15 mode schemas · 2. Bullet 27 summary scaffold · 3. Bullet 28 masking · 4. Bullet 7 async workers  
**Must know:** stubs vs live Bedrock; never claim production LLM.

---

## 8. Experience and Project Titles

| Use | Recommendation |
| ---- | -------------- |
| Project name | RedacTLDR (or “Privacy-preserving PDF intelligence platform”) |
| Role title | Software Engineer / Full-Stack Engineer (Personal Project) — confirm employment |
| LinkedIn | “RedacTLDR — Full-Stack Engineer (Project)” |
| Portfolio heading | “RedacTLDR: Secure PDF upload, redaction pipeline, and AI summary foundation” |
| Avoid | “Staff Engineer,” “Founding CTO,” “Lead of 10 engineers” without confirmation |

---

## 9. Project Descriptions

1. **One sentence:** RedacTLDR is a full-stack SaaS codebase for uploading sensitive PDFs, orchestrating async privacy workflows, and preparing safe summaries.  
2. **Two sentences:** RedacTLDR helps users process sensitive PDFs through authenticated upload, detection, redaction, and summarization stages. The current codebase delivers auth, S3 upload, Postgres lifecycle tracking, and Celery job orchestration, with OCR/PII/LLM stages still stubbed.  
3. **50-word LinkedIn:** Built RedacTLDR, a Next.js and FastAPI platform for privacy-preserving PDF workflows. Implemented Clerk auth, owner-scoped APIs, S3 presigned uploads, Postgres/Alembic models with RLS hardening, and Celery workers. Added Docker Compose and GitHub Actions CI with vulnerability scanning. Intelligence features (OCR, true redaction, Bedrock) are scaffolded next.  
4. **100-word LinkedIn:** (Expand 50-word with modes list, audit logging, Terraform scaffold, explicit “sole developer to date,” and “not claiming production LLM.”)  
5. **Technical portfolio:** Include architecture diagram from doc 02; link API inventory; show upload sequence; call out stub boundaries.  
6. **Recruiter-friendly:** Full-stack Python/TypeScript project combining secure uploads, background jobs, and cloud storage for a privacy document product.  
7. **Nontechnical:** A secure place to upload private PDFs and eventually black out sensitive info and get a safer summary.  
8. **30-second / 60-second:** Use scripts in [01 §1](01_TLDR_MASTER_OVERVIEW.md).  
9. **Detailed “Tell me about TLDR”:** Product goal → architecture → what you shipped (M1–M3) → what’s stubbed → security choices (presign, ownership, RLS) → what’s next (M6–M11).

---

## 10. Technical Interview Guide (major claims)

### Owner-scoped document API

* What: CRUD-ish document APIs filtered by `owner_user_id`  
* Why: Multi-user data isolation  
* Architecture: FastAPI + SQLAlchemy + UUID PKs  
* Frontend: list/create via `lib/api.ts`  
* Backend: `_require_document`  
* Auth: Clerk JWT / demo  
* Permissions: ownership only  
* Validation: UUID path, soft-delete filter  
* Errors: 404 hides existence cross-user  
* Testing: missing route tests — admit gap  
* Tradeoffs: 404 vs 403  
* Files: `documents.py` L44–64, L141–163  
* Avoid: claiming RBAC/admin roles  

### S3 presigned upload

* What: Server mints PUT URL; browser uploads; ingest verifies object  
* Why: Scalability + less API bandwidth for large PDFs  
* Security: short TTL, server-owned keys, type/size checks  
* Tradeoffs: CORS complexity; unsigned content-type on PUT  
* Files: `s3.py`, ingest in `documents.py`  
* Avoid: “zero-trust storage” hype; claiming KMS if not in code (KMS planned in docs only)

### Celery job system

* What: API inserts `jobs` row then enqueues task; worker updates status  
* Why: Durable visibility + async  
* Limitation: business logic stubs  
* Files: `_queue_job_record`, `_update_job_status`, `tasks.py`  
* Avoid: “built production OCR pipeline”

### Alembic + RLS

* What: Migrations add jobs/soft delete/canonical fields; RLS deny anon/authenticated  
* Why: Supabase PostgREST lockdown; app role used by API  
* Avoid: claiming row-level per-user RLS policies (policies are blanket deny)

### Next.js + Clerk dashboard

* What: Server mints JWT template token into client queries  
* Why: Browser calls API with correct audience  
* Dual mode without Clerk keys  
* Avoid: claiming complex design system / a11y program

---

## 11. SEO Interview Preparation

**Honest answer:** This product is an authenticated SaaS, not an SEO content platform. Only static Next.js `metadata` title/description exist. No sitemap, robots, canonical, OG, or Lighthouse artifacts were found. **Do not discuss fabricated score improvements.** If asked about SEO generally, speak from general knowledge, not this repo.

---

## 12. Architecture Interview Preparation

Be ready to whiteboard:

1. Clients → API → Postgres / S3 / Redis → Celery  
2. AuthN (Clerk JWKS) vs AuthZ (ownership)  
3. Upload sequence diagram  
4. Why stubs exist (milestone plan M6–M11)  
5. Compose vs future ECS  
6. Test gaps you would close first (API ownership tests)

Django/React CMS answers **do not apply**.

---

## 13. STAR Story Frameworks

### Implementing full-stack upload

* **S/T:** Need secure PDF ingest without Clerk friction locally  
* **A (repo-supported):** Presign create, client PUT, ingest-complete, dashboard polling, demo auth  
* **R:** Working local workflow per playbooks — confirm personal validation results  
* Must provide: your debugging stories (CORS, JWT template)  
* Do not invent: user counts  

### Building role-based experiences

* Reframe: **ownership-based**, not RBAC roles  
* Avoid “built role matrix for staff/creators”

### Media uploads

* Use S3 STAR; mention validation and key namespacing  

### AI chat/streaming

* **Do not use** — not in repo  

### Incomplete requirements / stubs

* Strong STAR: shipping orchestration first, stubbing intelligence, documenting milestones  

### Working in a team codebase

* Git shows sole author — say personal project unless you confirm collaborators  

---

## 14. Claims to Avoid (and safer alternatives)

| Avoid | Safer |
| ----- | ----- |
| Built the entire finished product | Sole developer of an in-progress SaaS foundation |
| Production Bedrock/Textract/Comprehend | Scaffolded workers pending AWS intelligence integrations |
| True redaction shipped | Prototyped pikepdf export path; annotations not applied yet |
| Custom CMS / creator marketplace | (Omit — wrong product) |
| Improved SEO by X | (Omit) |
| Scaled to thousands of users | (Omit or confirm) |
| Full ECS production deployment | Terraform scaffold for S3/ECR/ECS cluster |
| SOC 2 certified | Early security controls (JWT, ownership, RLS deny, CI scans) |
| RBAC admin system | Owner-scoped authorization |
| Comprehensive test coverage | Unit tests for auth/masking/schema/geometry; route tests pending |

---

## 15. Final Recommendations

* **Strongest features:** Auth, owner-scoped API, S3 upload orchestration, data model/migrations/RLS, Celery job skeleton, Compose+CI  
* **Strongest contributions:** Sole Git author of foundation + CI; large personal WIP for M3/Clerk  
* **Best resume angle:** Full-stack / backend-leaning privacy SaaS foundation engineer  
* **Best target roles:** Software Engineer, Full-Stack, Backend/Python, Cloud-curious SE  
* **Top 5 safest claims:** C2, C3, C4, C5/C6, sole-developer-of-codebase  
* **Top 5 stronger needing confirmation:** Production deploy, real AWS AI integrations complete, user metrics, “led team,” true redaction complete  
* **Study topics:** JWT/JWKS, presigned URL security, Celery retries, RLS vs app roles, soft deletes, Next.js server auth  
* **Biggest risks:** Claiming AI/redaction/SEO/prod scale  
* **Questions before final resume use:** See §1 confirmation + owner questions in docs 01/03  
* **Recommended final four bullets:** (1) Clerk JWT + owner-scoped FastAPI documents API (2) S3 presigned PDF upload + ingest verification (3) Postgres/Alembic lifecycle models + RLS hardening (4) Celery workers + Docker/GitHub Actions CI with vuln scanning  

---

*Compressed memory for future sessions: [05_TLDR_CONTEXT_HANDOFF.md](05_TLDR_CONTEXT_HANDOFF.md).*
