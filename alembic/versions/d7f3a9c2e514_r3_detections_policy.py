"""r3_detections_policy

Revision ID: d7f3a9c2e514
Revises: c4a1e2b8d091
Create Date: 2026-10-01 00:30:00.000000

R3: detections carry one rectangle per OCR line (`rects`), the character
span in the page text, the masked display value, the policy action that set
the default, and the custom rule id when a rule (not Comprehend) found it.
Existing rows keep their values; the new columns are empty for them.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d7f3a9c2e514"
down_revision = "c4a1e2b8d091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "detections",
        sa.Column("rects", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column("detections", sa.Column("char_start", sa.Integer(), nullable=True))
    op.add_column("detections", sa.Column("char_end", sa.Integer(), nullable=True))
    op.add_column("detections", sa.Column("masked_text", sa.String(length=512), nullable=True))
    op.add_column("detections", sa.Column("policy_action", sa.String(length=16), nullable=True))
    op.add_column("detections", sa.Column("rule_id", sa.String(length=64), nullable=True))
    op.create_index("ix_detections_document_page", "detections", ["document_id", "page_number"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_detections_document_page", table_name="detections")
    op.drop_column("detections", "rule_id")
    op.drop_column("detections", "policy_action")
    op.drop_column("detections", "masked_text")
    op.drop_column("detections", "char_end")
    op.drop_column("detections", "char_start")
    op.drop_column("detections", "rects")
