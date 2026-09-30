"""
Application settings (env-driven).

M3 note: Postgres can be reached via Supabase pooler for app traffic and a
direct host for migrations. Both are represented as URLs; see
`get_runtime_database_url` vs `get_migration_database_url`.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RedacTLDR API"
    app_version: str = "0.2.0"
    environment: str = "local"

    api_port: int = 8000
    # Runtime DB: typically pooler URL in Supabase (transaction mode on 6543).
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/redactldr",
        alias="DATABASE_URL",
    )
    # Migrations: direct Postgres (port 5432) — better for DDL than going through pooler.
    migration_database_url: str | None = Field(default=None, alias="MIGRATION_DATABASE_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_backend_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BACKEND_URL")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_originals: str = Field(default="redactldr-originals-dev", alias="S3_BUCKET_ORIGINALS")
    s3_bucket_downloads: str = Field(default="redactldr-downloads-dev", alias="S3_BUCKET_DOWNLOADS")

    clerk_issuer_url: str = Field(default="", alias="CLERK_ISSUER_URL")
    clerk_jwks_url: str = Field(default="", alias="CLERK_JWKS_URL")
    clerk_audience: str = Field(default="redactldr-api", alias="CLERK_AUDIENCE")
    upload_presign_ttl_seconds: int = Field(default=600, alias="UPLOAD_PRESIGN_TTL_SECONDS")
    max_upload_size_bytes: int = Field(default=20 * 1024 * 1024, alias="MAX_UPLOAD_SIZE_BYTES")
    # Comma-separated browser origins for FastAPI CORSMiddleware (API JSON calls).
    # Non-local deployments must set this to include every frontend origin that talks to the API.
    cors_allowed_origins_raw: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")

    retention_days: int = Field(default=7, alias="RETENTION_DAYS")
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-haiku-20240307-v1:0",
        alias="BEDROCK_MODEL_ID",
    )

    def validate_runtime_config(self) -> None:
        """
        Validate required runtime settings before serving traffic.

        Production-like environments must provide Clerk verification settings.
        """
        if self.environment == "local":
            return
        missing: list[str] = []
        if not self.clerk_jwks_url:
            missing.append("CLERK_JWKS_URL")
        if not self.clerk_issuer_url:
            missing.append("CLERK_ISSUER_URL")
        if not self.clerk_audience:
            missing.append("CLERK_AUDIENCE")
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required auth configuration: {names}")
        self.get_cors_allowed_origins()

    def get_cors_allowed_origins(self) -> list[str]:
        """Origins allowed to call this API from a browser (distinct from S3 bucket CORS)."""
        raw = self.cors_allowed_origins_raw.strip()
        if raw:
            return [part.strip() for part in raw.split(",") if part.strip()]
        if self.environment == "local":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        raise ValueError(
            "CORS_ALLOWED_ORIGINS must list every frontend origin (comma-separated) when ENVIRONMENT is not local."
        )

    def get_migration_database_url(self) -> str:
        """
        URL used by Alembic (`alembic/env.py`).

        Prefer `MIGRATION_DATABASE_URL` when set; otherwise reuse `DATABASE_URL`
        so single-URL local setups still work.
        """
        return self._normalize_database_url(self.migration_database_url or self.database_url)

    def get_runtime_database_url(self) -> str:
        """URL used by the API process and SQLAlchemy engine (`db.py`)."""
        return self._normalize_database_url(self.database_url)

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        """
        Normalize Postgres URLs to SQLAlchemy psycopg driver format.

        Supabase often provides `postgresql://...`; SQLAlchemy defaults that to
        psycopg2, while this project installs psycopg v3 (`psycopg`).
        """
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
