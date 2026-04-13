import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from services.api.app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_database_exists(database_url: str) -> None:
    url = make_url(database_url)
    db_name = url.database
    if not db_name:
        return
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", db_name):
        raise ValueError(f"Unsupported database name: {db_name}")

    admin_url = url.set(database="postgres")
    admin_engine = create_engine(
        admin_url,
        future=True,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
