from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from services.api.app.config import get_settings
from services.api.app.db import Base, engine, ensure_database_exists
from services.api.app.routes import auth, documents
from services.api.app.routes.audit import router as audit_router
from services.api.app.telemetry import setup_telemetry

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)
setup_telemetry(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    # For local/dev bootstrap we auto-create tables.
    # Production should use migrations.
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as exc:
        if "does not exist" not in str(exc):
            raise
        ensure_database_exists(settings.database_url)
        Base.metadata.create_all(bind=engine)


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(audit_router)


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
