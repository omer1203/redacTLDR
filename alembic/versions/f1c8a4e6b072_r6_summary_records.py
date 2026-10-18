"""r6_summary_records

Revision ID: f1c8a4e6b072
Revises: e5b2c7f1a9d3
Create Date: 2026-10-01 23:30:00.000000

R6: a failed summary needs a user-safe error, and the row needs timestamps
for the history the page shows. The payload itself stays in `json_payload`.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "f1c8a4e6b072"
down_revision = "e5b2c7f1a9d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("summaries", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("summaries", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("summaries", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column("summaries", sa.Column("completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("summaries", "completed_at")
    op.drop_column("summaries", "updated_at")
    op.drop_column("summaries", "error_message")
    op.drop_column("summaries", "error_code")
