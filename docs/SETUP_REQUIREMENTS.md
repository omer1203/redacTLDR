# RedacTLDR Setup Requirements

This checklist is optimized for `M1` and `M2` validation.

## Local Software

- Docker Desktop
- Docker Compose
- Optional (non-container workflows): Node 22, npm, Python 3.11+

## Accounts and Integrations

For minimal local boot:

- none strictly required beyond local Docker stack

For real M2 auth + upload integration:

- Clerk project and keys
- AWS credentials and S3 buckets

## Environment Variables (Compose)

Primary file: `ops/compose/.env` (auto-created from `ops/compose/.env.example` by `scripts/dev-up.sh` if missing).

Important keys:

- web:
  - `NEXT_PUBLIC_API_URL`
  - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  - `NEXT_PUBLIC_DEMO_USER`
  - `CLERK_SECRET_KEY`
  - `CLERK_JWT_TEMPLATE`
- API:
  - `ENVIRONMENT`
  - `DATABASE_URL`
  - `MIGRATION_DATABASE_URL`
  - `CELERY_BROKER_URL`
  - `CELERY_BACKEND_URL`
  - `CLERK_ISSUER_URL`
  - `CLERK_JWKS_URL`
  - `CLERK_AUDIENCE`
- worker:
  - `DATABASE_URL`
  - `CELERY_BROKER_URL`
  - `CELERY_BACKEND_URL`

Optional for upload and downstream pipeline:

- `AWS_REGION`
- `S3_BUCKET_ORIGINALS`
- `S3_BUCKET_DOWNLOADS`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_SESSION_TOKEN`

## Quick Start

```bash
bash scripts/dev-up.sh
```

## Quick Stop

```bash
bash scripts/dev-down.sh
```

## M1/M2 Verification Endpoints

- `GET /v1/health`
- `GET /v1/auth/me` (with bearer token)
- `GET /v1/documents` (with bearer token)
- `GET /v1/documents` (with `x-demo-user` header in local demo mode)

## M3 Migration Commands

From repo root (using project virtualenv):

```bash
.venv/bin/alembic revision --autogenerate -m "<message>"
.venv/bin/alembic upgrade head
```

Notes:

- runtime app traffic uses `DATABASE_URL`
- Alembic uses `MIGRATION_DATABASE_URL` (falls back to `DATABASE_URL` if unset)
- worker runtime normalizes `postgresql://` URLs to psycopg v3 SQLAlchemy format.

## M3 Seed and Validation

```bash
.venv/bin/python scripts/seed_m3_demo.py
```

Full M3 verification runbook:

- `docs/M3_VALIDATION_PLAYBOOK.md`

## Troubleshooting

- If API starts but auth fails:
  - verify Clerk issuer/JWKS/audience values.
  - verify `CLERK_JWT_TEMPLATE` is set when Clerk is enabled.
- If uploads fail:
  - verify AWS credentials, bucket names, and S3 permissions.
- If queue stalls:
  - verify Redis service and worker container health.
- For full M1/M2 validation steps and expected logs:
  - see `docs/M1_M2_VALIDATION_PLAYBOOK.md`.
