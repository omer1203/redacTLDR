"""r5_export_records

Revision ID: e5b2c7f1a9d3
Revises: d7f3a9c2e514
Create Date: 2026-10-01 18:00:00.000000

R5: every export is its own row with request options, the worker's counts
(pages, boxes, bytes, verification), a user-safe error pair, and timestamps.
Rows written by the M5 stub keep their values; the new columns stay empty
except `options`, which defaults to `{}`.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e5b2c7f1a9d3"
down_revision = "d7f3a9c2e514"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exports",
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("exports", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("exports", sa.Column("redaction_count", sa.Integer(), nullable=True))
    op.add_column("exports", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("exports", sa.Column("verification", postgresql.JSONB(), nullable=True))
    op.add_column("exports", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("exports", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("exports", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("exports", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_exports_document_created", "exports", ["document_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_exports_document_created", table_name="exports")
    op.drop_column("exports", "completed_at")
    op.drop_column("exports", "updated_at")
    op.drop_column("exports", "error_message")
    op.drop_column("exports", "error_code")
    op.drop_column("exports", "verification")
    op.drop_column("exports", "size_bytes")
    op.drop_column("exports", "redaction_count")
    op.drop_column("exports", "page_count")
    op.drop_column("exports", "options")
