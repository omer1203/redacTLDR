# RedacTLDR

Website-first, cloud-native, privacy-preserving document intelligence.

RedacTLDR helps users upload sensitive PDFs, detect/redact PII, generate structured AI summaries, and share safer outputs. The platform is designed as a production-grade SaaS system with strong security and explainable processing stages.

## Product Scope

Core user flow:

1. upload PDF
2. detect sensitive entities
3. review and adjust redactions
4. export truly redacted document
5. generate structured summaries by document mode

Supported modes:

- resume anonymization
- employment documents
- medical documents
- legal contracts
- terms and conditions

## Architecture (Current Runtime Shape)

- `apps/web`: Next.js App Router frontend (primary product surface)
- `services/api`: FastAPI orchestration API
- `services/worker`: Celery async processing workers
- `ops/compose`: local runtime stack
- `infra/terraform`: cloud infrastructure definitions
- `docs`: architecture, milestones, and implementation tracking

## Canonical Plan

This project follows the milestone plan in:

- `docs/EXECUTION_PLAN.md` (canonical execution contract)
- `docs/MILESTONES_DETAILED.md` (detailed M1-M18 specification)
- `docs/MILESTONE_STATUS.json` (machine-readable progress)

## Local Development Quick Start

### Prerequisites

- Docker Desktop
- Docker Compose

### Start

```bash
bash scripts/dev-up.sh
```

This script creates `ops/compose/.env` from `ops/compose/.env.example` on first run.

- No Clerk values: local demo auth mode (no repeated login for local development).
- Clerk values present: full sign-in/sign-up protected flow.

### Verify

- Web: `http://localhost:3000`
- API health: `http://localhost:8000/v1/health`
- Browser uploads send `PUT` requests straight to S3. If the console shows an S3 CORS error, configure bucket CORS: `bash scripts/apply-s3-cors.sh` (AWS CLI credentials required), or apply Terraform which sets CORS on managed buckets.
- After creating buckets, confirm identity + bucket access with: `bash scripts/verify-local-s3.sh`

### Stop

```bash
bash scripts/dev-down.sh
```

Optional full cleanup:

```bash
bash scripts/dev-down.sh -v
```

## Security and Privacy Principles

- API ownership checks on document resources
- JWT verification with Clerk JWKS caching
- policy-driven safe mode for AI processing
- presigned URL-based direct object transfer (short TTL; never share full URLs—they embed temporary signing credentials)
- async processing to isolate heavy and sensitive workflows
- audit-oriented event capture for key actions

## Repository Notes

- Mobile is deferred while the website path is prioritized.
- ECS Fargate is the primary deployment target; Kubernetes is optional later.

## Current Focus

Immediate objective: progress from `M4` onward (upload flow hardening and pipeline depth), with `M1`-`M3` kept regression-safe.

Validation runbook:

- `docs/M1_M2_VALIDATION_PLAYBOOK.md`
- `docs/M3_VALIDATION_PLAYBOOK.md`
