"""Shared SQLAlchemy engine for worker tasks.

Tasks and the OCR stage both write through raw SQL. One engine keeps the pool
and the Postgres URL normalization in a single place.
"""

from sqlalchemy import create_engine

from services.worker.app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
