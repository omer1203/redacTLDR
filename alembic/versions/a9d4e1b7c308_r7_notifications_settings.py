"""r7_notifications_settings

Revision ID: a9d4e1b7c308
Revises: f1c8a4e6b072
Create Date: 2026-10-02 00:40:00.000000

R7: in-app notices and one settings row per user. Notices hold a title only.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "a9d4e1b7c308"
down_revision = "f1c8a4e6b072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_document_id", "notifications", ["document_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.String(length=128), primary_key=True),
        sa.Column("default_mode", sa.String(length=128), nullable=False),
        sa.Column("safe_mode", sa.Boolean(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("store_raw_detections", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_documents_owner_created", "documents", ["owner_user_id", "created_at"])
    op.create_index("ix_audit_logs_user_created", "audit_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user_created", table_name="audit_logs")
    op.drop_index("ix_documents_owner_created", table_name="documents")
    op.drop_table("user_settings")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_document_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
