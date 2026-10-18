"""r2_ocr_pages

Revision ID: c4a1e2b8d091
Revises: eb35da4c4c2e
Create Date: 2026-09-30 23:10:00.000000

R2: page geometry for OCR, plus document columns that track the Textract job
and where the normalized OCR JSON lives in S3. Extracted text is not added to
Postgres. Existing DETECTED / DETECT_QUEUED rows move onto the R2 lifecycle.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4a1e2b8d091"
down_revision = "eb35da4c4c2e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("processing_stage", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("error_code", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("textract_job_id", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("ocr_s3_key", sa.String(length=1024), nullable=True))

    op.execute("UPDATE documents SET status = 'READY_FOR_REVIEW' WHERE status = 'DETECTED'")
    op.execute(
        """
        UPDATE documents
        SET status = 'PROCESSING', processing_stage = 'detect'
        WHERE status = 'DETECT_QUEUED'
        """
    )

    op.create_table(
        "document_pages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("height", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("has_text_layer", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
    )
    op.create_index(op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False)

    op.execute("ALTER TABLE public.document_pages ENABLE ROW LEVEL SECURITY")
    # Supabase has `anon` and `authenticated`. Local Postgres does not, so the
    # deny policy is created only when those roles exist. The table owner used
    # by the API bypasses RLS unless it is forced.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
             AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
             AND NOT EXISTS (
               SELECT 1 FROM pg_policies
               WHERE schemaname='public'
                 AND tablename='document_pages'
                 AND policyname='document_pages_deny_anon_authenticated'
             ) THEN
            CREATE POLICY document_pages_deny_anon_authenticated
              ON public.document_pages
              FOR ALL
              TO anon, authenticated
              USING (false)
              WITH CHECK (false);
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS document_pages_deny_anon_authenticated ON public.document_pages")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_table("document_pages")

    op.execute("UPDATE documents SET status = 'DETECTED' WHERE status = 'READY_FOR_REVIEW'")
    op.execute("UPDATE documents SET status = 'DETECT_QUEUED' WHERE status = 'PROCESSING'")

    op.drop_column("documents", "ocr_s3_key")
    op.drop_column("documents", "textract_job_id")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "error_code")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "processing_stage")
