import os


def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_BACKEND_URL = env("CELERY_BACKEND_URL", "redis://localhost:6379/1")
DATABASE_URL = env("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/redactldr")
AWS_REGION = env("AWS_REGION", "us-east-1")
S3_BUCKET_ORIGINALS = env("S3_BUCKET_ORIGINALS", "redactldr-originals-dev")
S3_BUCKET_DOWNLOADS = env("S3_BUCKET_DOWNLOADS", "redactldr-downloads-dev")
