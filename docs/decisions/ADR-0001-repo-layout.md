# ADR-0001: Adopt Monorepo Layout for RedacTLDR

## Status

Accepted

## Context

RedacTLDR needs to ship a website-first product with API, asynchronous workers, shared operational tooling, and infrastructure-as-code. The current repository started as a small backend + mobile prototype and lacks clear boundaries for the full platform.

## Decision

Adopt this top-level layout:

- `apps/web`: Next.js App Router frontend.
- `frontend/mobile`: deferred secondary mobile surface (not in current critical path).
- `services/api`: FastAPI service.
- `services/worker`: Celery worker service.
- `ops/compose`: local container orchestration and OTel collector config.
- `infra/terraform`: AWS infrastructure definitions for staging/production.

## Consequences

### Positive

- Clear ownership boundaries between runtime components.
- Easier CI segmentation by app/service.
- Cleaner deployment story for ECS/Fargate and optional Kubernetes.

### Negative

- Initial migration effort from existing prototype paths.
- Temporary duplication risk while moving code incrementally.

## Rollout Notes

1. Keep behavior stable while introducing new directories.
2. Move production code to `services/*` before deleting legacy paths.
3. Add compatibility references in docs during transition.
