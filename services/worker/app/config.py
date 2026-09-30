"""
Worker process configuration (env only, no Pydantic).

Mirrors the API’s `DATABASE_URL` normalization: Supabase and others often emit
`postgresql://` while SQLAlchemy should use the psycopg v3 driver for this app.
"""

import os


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def normalize_database_url(url: str) -> str:
    """Map bare `postgresql://` URLs to `postgresql+psycopg://` for SQLAlchemy 2."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_BACKEND_URL = env("CELERY_BACKEND_URL", "redis://localhost:6379/1")
DATABASE_URL = normalize_database_url(env("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/redactldr"))
AWS_REGION = env("AWS_REGION", "us-east-1")
S3_BUCKET_ORIGINALS = env("S3_BUCKET_ORIGINALS", "redactldr-originals-dev")
S3_BUCKET_DOWNLOADS = env("S3_BUCKET_DOWNLOADS", "redactldr-downloads-dev")
