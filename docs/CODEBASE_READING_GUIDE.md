# RedacTLDR Codebase Reading Guide

Use this order to understand the system like an owner, not just a contributor.

## 1) Runtime and Configuration

- `ops/compose/docker-compose.yml`
- `scripts/dev-up.sh`
- `services/api/app/config.py`
- `services/worker/app/config.py`

Why first: these files define how processes start and connect.

## 2) Entrypoints

- `apps/web/app/layout.tsx`
- `apps/web/app/page.tsx`
- `apps/web/app/dashboard/page.tsx`
- `services/api/app/main.py`
- `services/worker/app/celery_app.py`

Why: gives high-level service boundaries immediately.

## 3) Authentication Boundary

- `apps/web/middleware.ts`
- `services/api/app/auth.py`
- `services/api/app/routes/auth.py`

Why: ownership and security decisions start here.

## 4) Core Workflow Orchestration

- `services/api/app/routes/documents.py`
- `services/api/app/celery_client.py`
- `services/api/app/services/s3.py`
- `services/api/app/services/audit.py`

Why: this is where upload/list/queue orchestration lives.

## 5) Data Model and Contracts

- `services/api/app/models.py`
- `services/api/app/schemas.py`
- `services/api/app/enums.py`
- `apps/web/lib/types.ts`
- `apps/web/lib/api.ts`

Why: understand domain model before deeper implementation.

## 6) Worker Behavior

- `services/worker/app/tasks.py`
- `services/worker/app/redaction.py`
- `services/worker/app/summary.py`
- `services/worker/app/geometry.py`

Why: this is the async engine core.

## 7) Frontend Workflow State

- `apps/web/components/dashboard-client.tsx`
- `apps/web/lib/query-client.ts`

Why: links backend state transitions to user-visible behavior.

## 8) Testing Baseline

- `services/api/tests/test_auth.py`
- `services/api/tests/test_masking.py`
- `services/api/tests/test_summary_validation.py`
- `services/worker/tests/test_geometry.py`

Why: tests communicate expected behavior and confidence scope.

## 9) Milestone Execution Context

- `docs/EXECUTION_PLAN.md`
- `docs/MILESTONES_DETAILED.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/MILESTONE_STATUS.json`

Why: these define what we are building now, next, and why.
