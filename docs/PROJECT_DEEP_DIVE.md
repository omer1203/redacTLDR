# RedacTLDR Project Deep Dive

This document explains the system as an engineering ownership guide with emphasis on production architecture decisions.

## 1) Product Intent

RedacTLDR is a website-first SaaS for privacy-preserving document intelligence.

Primary workflow:

1. upload PDF
2. detect sensitive entities
3. human review and redaction control
4. export true-redacted PDF
5. generate structured AI summary

Document modes:

- resume anonymization
- employment
- medical
- legal
- terms and conditions

Each mode changes redaction defaults and summary schema.

## 2) Design Principles

- async processing for heavy stages
- thin orchestration API
- worker-owned compute pipeline
- policy-driven privacy behavior
- secure-by-default storage and transport
- explicit observability and auditability

## 3) Current Runtime Architecture

- web: Next.js App Router (`apps/web`)
- API: FastAPI (`services/api`)
- workers: Celery (`services/worker`)
- queue/backend: Redis
- DB: Postgres (Supabase strategy in milestone plan)
- storage: S3 (presigned URL pattern)

## 4) Auth and Ownership

- web uses Clerk for route protection and session/token handling
- API verifies JWT signatures via cached Clerk JWKS
- API scopes document access by authenticated user ownership
- local developer bypass exists for non-production workflows

## 5) Data and Lifecycle Model

Core entities:

- `documents`
- `detections`
- `manual_redactions`
- `exports`
- `summaries`
- `audit_logs`

Lifecycle evolves from `CREATED` toward processing and delivery statuses.

## 6) Async Processing Pattern

API does not perform heavy document compute synchronously. It:

- accepts requests
- validates ownership/policy constraints
- persists state
- enqueues background tasks

Workers handle detection, export, and summary workloads with retry behavior and explicit status updates.

## 7) Security and Privacy Posture

- direct-to-S3 upload/download with presigned URLs
- short-lived tokenized access patterns
- policy-driven masking and OCR storage behavior (milestone-driven rollout)
- intended KMS-backed encryption controls
- audit event strategy for sensitive actions

## 8) What Is Strong Today

- local runtime stack coherence
- modular service boundaries
- auth verification baseline in API
- upload/list orchestration path
- queue and worker skeleton with retries

## 9) What Is Not Finished Yet

- production-grade migrations and Supabase operational split
- full OCR + PII + true-redaction data plane
- complete summary engine with Bedrock/LangChain
- robust SOC2-style controls and operational runbooks
- cloud deployment hardening to ECS production standards

## 10) Execution Contract

All forward development follows:

- `docs/EXECUTION_PLAN.md`
- `docs/MILESTONES_DETAILED.md`
- `docs/MILESTONE_STATUS.json`

## 11) Interview Positioning

This project demonstrates:

- full-stack architecture ownership
- async systems design
- security-aware product design
- cloud and platform engineering maturity

The strongest narrative is not "we use many tools"; it is "we made explicit tradeoffs, staged risk, and validated each milestone with evidence."
