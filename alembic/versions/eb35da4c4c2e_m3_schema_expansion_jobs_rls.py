"""m3_schema_expansion_jobs_rls

Revision ID: eb35da4c4c2e
Revises: 0e64b6ccff04
Create Date: 2026-04-26 22:57:40.859899

M3: jobs table, soft deletes on core tables, canonical document fields with
data backfill, unique `s3_key_original`, and RLS deny policies for PostgREST
roles so only the app service user hits these tables.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'eb35da4c4c2e'
down_revision = '0e64b6ccff04'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=128), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("queued_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_deleted_at"), "jobs", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_jobs_document_id"), "jobs", ["document_id"], unique=False)
    op.create_index(op.f("ix_jobs_job_type"), "jobs", ["job_type"], unique=False)
    op.create_index(op.f("ix_jobs_owner_user_id"), "jobs", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_jobs_queued_at"), "jobs", ["queued_at"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_workspace_id"), "jobs", ["workspace_id"], unique=False)

    op.add_column("audit_logs", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_audit_logs_deleted_at"), "audit_logs", ["deleted_at"], unique=False)
    op.add_column("detections", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_detections_deleted_at"), "detections", ["deleted_at"], unique=False)

    # Add new canonical columns as nullable first, backfill, then enforce constraints.
    op.add_column("documents", sa.Column("owner_user_id", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("workspace_id", sa.UUID(), nullable=True))
    op.add_column("documents", sa.Column("document_type", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("s3_key_original", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.execute("UPDATE documents SET owner_user_id = user_id WHERE owner_user_id IS NULL")
    op.execute("UPDATE documents SET document_type = mode WHERE document_type IS NULL")
    op.execute("UPDATE documents SET s3_key_original = s3_key WHERE s3_key_original IS NULL")

    op.alter_column("documents", "owner_user_id", nullable=False)
    op.alter_column("documents", "document_type", nullable=False)
    op.alter_column("documents", "s3_key_original", nullable=False)
    op.create_index(op.f("ix_documents_deleted_at"), "documents", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_documents_owner_user_id"), "documents", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_documents_workspace_id"), "documents", ["workspace_id"], unique=False)
    op.create_unique_constraint("uq_documents_s3_key_original", "documents", ["s3_key_original"])

    op.add_column("exports", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_exports_deleted_at"), "exports", ["deleted_at"], unique=False)
    op.add_column("manual_redactions", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_manual_redactions_deleted_at"), "manual_redactions", ["deleted_at"], unique=False)
    op.add_column("summaries", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_summaries_deleted_at"), "summaries", ["deleted_at"], unique=False)

    # Harden all application tables in public schema by enabling RLS and denying direct API roles.
    for table_name in (
        "documents",
        "detections",
        "manual_redactions",
        "exports",
        "summaries",
        "audit_logs",
        "jobs",
    ):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname='public'
                  AND tablename='{table_name}'
                  AND policyname='{table_name}_deny_anon_authenticated'
              ) THEN
                CREATE POLICY {table_name}_deny_anon_authenticated
                  ON public.{table_name}
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
    for table_name in (
        "jobs",
        "audit_logs",
        "summaries",
        "exports",
        "manual_redactions",
        "detections",
        "documents",
    ):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_deny_anon_authenticated ON public.{table_name}")

    op.drop_index(op.f("ix_summaries_deleted_at"), table_name="summaries")
    op.drop_column("summaries", "deleted_at")
    op.drop_index(op.f("ix_manual_redactions_deleted_at"), table_name="manual_redactions")
    op.drop_column("manual_redactions", "deleted_at")
    op.drop_index(op.f("ix_exports_deleted_at"), table_name="exports")
    op.drop_column("exports", "deleted_at")
    op.drop_constraint("uq_documents_s3_key_original", "documents", type_="unique")
    op.drop_index(op.f("ix_documents_workspace_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_owner_user_id"), table_name="documents")
    op.drop_index(op.f("ix_documents_deleted_at"), table_name="documents")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "s3_key_original")
    op.drop_column("documents", "document_type")
    op.drop_column("documents", "workspace_id")
    op.drop_column("documents", "owner_user_id")
    op.drop_index(op.f("ix_detections_deleted_at"), table_name="detections")
    op.drop_column("detections", "deleted_at")
    op.drop_index(op.f("ix_audit_logs_deleted_at"), table_name="audit_logs")
    op.drop_column("audit_logs", "deleted_at")
    op.drop_index(op.f("ix_jobs_workspace_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_status"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_queued_at"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_owner_user_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_job_type"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_document_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_deleted_at"), table_name="jobs")
    op.drop_table("jobs")
