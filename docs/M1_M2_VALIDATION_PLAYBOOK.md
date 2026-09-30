# M1/M2 Validation Playbook

This runbook gives both automated and manual verification for milestones `M1` and `M2`.

## 1) Automated Checks

Run from repo root:

```bash
npm run web:lint
npm run web:typecheck
pytest services/api/tests services/worker/tests
```

Expected:

- web lint: no errors
- typecheck: no TypeScript errors
- pytest: all tests pass

## 2) Start Local Stack

```bash
bash scripts/dev-up.sh
```

Expected services:

- `web` on port `3000`
- `api` on port `8000`
- `worker`
- `postgres`
- `redis`

## 3) M1 Runtime Smoke Checks

### Health endpoint

```bash
curl -sS "http://localhost:8000/v1/health"
```

Expected:

```json
{"status":"ok","version":"0.2.0"}
```

### Worker task registration

Check worker logs for registered task names:

- `detect_job`
- `export_job`
- `summary_job`

## 4) M2 Local Demo Auth Checks (No Clerk Required)

### Dashboard access

- Open `http://localhost:3000/dashboard`
- Expected: dashboard loads in "Local Demo Auth" mode without login.

### API ownership path using local header

```bash
curl -sS -H "x-demo-user: demo-user" "http://localhost:8000/v1/documents"
```

Expected:

- HTTP 200 and JSON array response.

## 5) M2 Clerk Auth Checks (Real Integration Mode)

Populate `ops/compose/.env` with Clerk values:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_JWT_TEMPLATE`
- `CLERK_ISSUER_URL`
- `CLERK_JWKS_URL`
- `CLERK_AUDIENCE`

Then restart stack and verify:

1. `/dashboard` redirects signed-out users.
2. `/sign-in` and `/sign-up` pages render.
3. After sign-in, dashboard loads.
4. API identity endpoint works with bearer token:

```bash
curl -sS -H "Authorization: Bearer <token>" "http://localhost:8000/v1/auth/me"
```

Expected:

- user payload with `id`, and optional `email`/`sessionId`.

## 6) Upload Flow Verification (M2 + M4 Entry Path)

Requires valid AWS/S3 configuration.

From dashboard:

1. choose PDF
2. submit upload
3. verify document appears in list
4. verify status reaches `DETECT_QUEUED` then worker-updated states

API/worker log signals:

- API logs task queueing (`Queued task ...`)
- worker logs completion (`detect_job completed document_id=...`)

## 7) Failure-Mode Checks

- Remove/blank `CLERK_JWT_TEMPLATE` while Clerk is enabled:
  - expected: dashboard route fails fast with config error.
- Call protected API without bearer or demo header:
  - expected: `401` missing bearer token.
- Break Redis connection:
  - expected: queue calls return `503` from API enqueue handling.

## 8) Evidence Capture Template

For milestone closure attach:

- command output snippets
- screenshots for dashboard auth states
- API/worker log excerpts for queue + task completion
- list of env configuration used for the run (without secrets)
