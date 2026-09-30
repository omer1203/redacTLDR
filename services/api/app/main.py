"""
FastAPI runtime entry point.

This module wires together infrastructure concerns (telemetry, CORS, DB bootstrap)
and HTTP surface area (routers + health endpoint).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from services.api.app.config import get_settings
from services.api.app.db import Base, engine, ensure_database_exists
from services.api.app.routes import auth, documents
from services.api.app.routes.audit import router as audit_router
from services.api.app.telemetry import setup_telemetry

# Read process-level configuration once at import time.
settings = get_settings()

# Create the ASGI application object used by uvicorn/gunicorn workers.
app = FastAPI(title=settings.app_name, version=settings.app_version)

# Install OpenTelemetry / tracing / metrics hooks (implementation lives in telemetry.py).
setup_telemetry(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    """
    Validate settings and ensure the process can talk to Postgres.

    - **local** (`ENVIRONMENT=local`): create tables on demand for zero-setup dev.
      M3 production and staging do not use this—schema is applied by Alembic.
    - **else**: assume migrations have been applied; only run `SELECT 1` to fail
      fast if the DB is unreachable.
    """
    settings.validate_runtime_config()
    if settings.environment == "local":
        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError as exc:
            # Only handle the specific "database missing" case.
            # Any other operational error (permissions, network, bad SQL, etc.) is re-raised.
            if "does not exist" not in str(exc):
                raise
            ensure_database_exists(settings.get_runtime_database_url())
            Base.metadata.create_all(bind=engine)
        return

    # In non-local environments, schema changes must come from Alembic migrations.
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


# Register versioned API routers. Each router owns a functional domain.
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(audit_router)


@app.get("/v1/health")
def health() -> dict[str, str]:
    """Lightweight liveness/version probe used by local checks and deploy monitors."""
    return {"status": "ok", "version": settings.app_version}
