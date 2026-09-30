# M3 Validation Playbook (Supabase + Models + Migrations)

This runbook validates milestone M3 end-to-end.

## Preconditions

- `ops/compose/.env` has:
  - `DATABASE_URL` (runtime pooler)
  - `MIGRATION_DATABASE_URL` (direct migration URL)
- Project virtualenv exists:
  - `python -m venv .venv`
  - `.venv/bin/pip install -r requirements.txt`

## 1) Migration State

```bash
set -a && source ops/compose/.env && set +a
.venv/bin/alembic current
```

Expected:

- `eb35da4c4c2e (head)` (or newer head if additional migrations were added)

## 2) Apply Migrations

```bash
set -a && source ops/compose/.env && set +a
.venv/bin/alembic upgrade head
```

Expected:

- migration applies cleanly without SQL errors.

## 3) Schema Verification

```bash
set -a && source ops/compose/.env && set +a
.venv/bin/python -c "from services.api.app.config import get_settings; from sqlalchemy import create_engine,text; e=create_engine(get_settings().get_migration_database_url()); c=e.connect(); print(c.execute(text('select version_num from alembic_version')).fetchall()); print(c.execute(text(\"select to_regclass('public.jobs')\")).scalar()); c.close()"
```

Expected:

- alembic version contains latest revision
- `jobs` table exists

## 4) RLS Policy Verification

```bash
set -a && source ops/compose/.env && set +a
.venv/bin/python -c "from services.api.app.config import get_settings; from sqlalchemy import create_engine,text; e=create_engine(get_settings().get_migration_database_url()); c=e.connect(); print(c.execute(text(\"select tablename, policyname from pg_policies where schemaname='public' and policyname like '%deny_anon_authenticated' order by tablename\")).fetchall()); c.close()"
```

Expected:

- deny policy exists for all core tables:
  - `documents`, `detections`, `manual_redactions`, `exports`, `summaries`, `audit_logs`, `jobs`

## 5) Seed Data

```bash
set -a && source ops/compose/.env && set +a
.venv/bin/python scripts/seed_m3_demo.py
```

Expected:

- seeded document + job IDs are printed (or "already present")

## 6) Regression Checks

```bash
pytest services/api/tests services/worker/tests
npm run web:typecheck
```

Expected:

- tests pass
- typecheck passes

## 7) Security Review Checklist

- runtime and migration URLs are split correctly.
- non-local API startup does not auto-create schema.
- RLS enabled and restrictive policy present on core tables.
- no secrets committed to repo files.
