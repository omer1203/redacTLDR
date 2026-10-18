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
# Off by default: `detections.detected_text` holds the masked value. There is no
# per-user settings table yet, so this is a deployment-wide switch until one exists.
STORE_RAW_DETECTIONS = env("STORE_RAW_DETECTIONS", "false").strip().lower() in {"1", "true", "yes"}
# Same env var the API reads. The compose example overrides this default.
BEDROCK_MODEL_ID = env("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
# Cost cap. Pages past this are omitted and the summary says it was truncated.
SUMMARY_MAX_PAGES = int(env("SUMMARY_MAX_PAGES", "30"))
