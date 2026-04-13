from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "redactldr API"
    app_version: str = "0.2.0"
    environment: str = "local"

    api_port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/redactldr",
        alias="DATABASE_URL",
    )
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_backend_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BACKEND_URL")

    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket_originals: str = Field(default="redactldr-originals-dev", alias="S3_BUCKET_ORIGINALS")
    s3_bucket_downloads: str = Field(default="redactldr-downloads-dev", alias="S3_BUCKET_DOWNLOADS")

    clerk_issuer_url: str = Field(default="", alias="CLERK_ISSUER_URL")
    clerk_jwks_url: str = Field(default="", alias="CLERK_JWKS_URL")
    clerk_audience: str = Field(default="redactldr-api", alias="CLERK_AUDIENCE")

    retention_days: int = Field(default=7, alias="RETENTION_DAYS")
    bedrock_model_id: str = Field(
        default="anthropic.claude-3-haiku-20240307-v1:0",
        alias="BEDROCK_MODEL_ID",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
