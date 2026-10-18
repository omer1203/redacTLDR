"""
SQLAlchemy ORM models representing the core product lifecycle.

These models are the canonical source for persisted state semantics in the API.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.db import Base
from services.api.app.enums import DocumentMode, DocumentStatus


def _uuid() -> uuid.UUID:
    """Use UUIDv4 for all primary keys."""
    return uuid.uuid4()


class Document(Base):
    """
    One user-uploaded file and its async processing state.

    M3: `owner_user_id` is the access-control column (list/get/update paths filter
    on it). `user_id` is the legacy `sub` string kept aligned with the owner for
    backcompat and any code still reading `user_id` only.
    """

    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_owner_created", "owner_user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True, default="")
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    document_type: Mapped[str] = mapped_column(String(128), default=DocumentMode.RESUME_ANONYMIZATION.value)
    s3_key_original: Mapped[str] = mapped_column(String(1024), unique=True, default="")
    user_id: Mapped[str] = mapped_column(
        String(128), index=True
    )  # legacy alias of owner; same Clerk subject
    filename: Mapped[str] = mapped_column(String(512))  # original client-provided filename
    content_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    s3_key: Mapped[str] = mapped_column(String(1024), unique=True)  # path in originals bucket
    mode: Mapped[str] = mapped_column(String(128), default=DocumentMode.RESUME_ANONYMIZATION.value)
    safe_mode: Mapped[bool] = mapped_column(Boolean, default=True)  # conservative redaction behavior toggle
    status: Mapped[str] = mapped_column(String(64), default=DocumentStatus.CREATED.value)  # async lifecycle stage
    # R2: which pipeline stage is active while status is PROCESSING (`ocr` or `detect`).
    processing_stage: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # Stable machine code plus a short message safe to show in the UI. Never store OCR text here.
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    textract_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True, default=None)
    # Key of the normalized OCR JSON in the originals bucket. The JSON itself is not stored in Postgres.
    ocr_s3_key: Mapped[str | None] = mapped_column(String(1024), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    # Child entities produced/managed as the document moves through processing.
    detections = relationship("Detection", back_populates="document", cascade="all, delete-orphan")
    redactions = relationship("ManualRedaction", back_populates="document", cascade="all, delete-orphan")
    exports = relationship("ExportArtifact", back_populates="document", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    """Page size and text-layer flag. Word text stays in the OCR JSON in S3."""

    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    page_number: Mapped[int] = mapped_column(Integer)
    width: Mapped[float] = mapped_column(Float, default=0.0)  # PDF points, from PyMuPDF
    height: Mapped[float] = mapped_column(Float, default=0.0)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    has_text_layer: Mapped[bool] = mapped_column(Boolean, default=False)

    document = relationship("Document", back_populates="pages")


class Detection(Base):
    """Machine-detected sensitive entity candidate extracted from a document."""

    __tablename__ = "detections"
    __table_args__ = (Index("ix_detections_document_page", "document_id", "page_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))  # e.g. NAME, SSN, EMAIL
    # R3: the masked value by default; the raw value only when STORE_RAW_DETECTIONS is on.
    detected_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int] = mapped_column(default=1)
    block_ref: Mapped[str] = mapped_column(String(128), default="")  # `p{page}:l{ocr line index}`
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[dict] = mapped_column(JSONB, default=dict)  # envelope of `rects`, kept for older readers
    # One normalized 0–1 rectangle per OCR line the entity covers.
    rects: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    # Span in the page text built by `services/worker/app/detection/page_text.py`.
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    masked_text: Mapped[str | None] = mapped_column(String(512), nullable=True, default=None)
    policy_action: Mapped[str | None] = mapped_column(String(16), nullable=True, default=None)  # auto | suggested
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)  # set when source == "rule"
    source: Mapped[str] = mapped_column(String(64), default="comprehend")  # comprehend | rule
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)  # reviewer inclusion toggle
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="detections")


class ManualRedaction(Base):
    """User-authored redaction instruction (bbox or text span)."""

    __tablename__ = "manual_redactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    redaction_kind: Mapped[str] = mapped_column(String(32), default="bbox")
    entity_type: Mapped[str] = mapped_column(String(64), default="CUSTOM")
    page_number: Mapped[int] = mapped_column(default=1)
    block_ref: Mapped[str] = mapped_column(String(128), default="")
    bbox: Mapped[dict] = mapped_column(JSONB, default=dict)  # geometric redaction target
    span: Mapped[dict] = mapped_column(JSONB, default=dict)  # text-range redaction target
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(128))  # auth subject that created instruction
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="redactions")


class ExportArtifact(Base):
    """One redacted PDF build. Each request gets its own row and its own S3 object (R5)."""

    __tablename__ = "exports"
    __table_args__ = (Index("ix_exports_document_created", "document_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    s3_key: Mapped[str] = mapped_column(String(1024))  # path in downloads bucket
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")  # QUEUED / PROCESSING / EXPORTED / FAILED
    # Request options, e.g. {"includeLabels": true}. The worker reads them from here.
    options: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    # Filled by the worker. Counts only; no document text.
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    redaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    verification: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="exports")


class Summary(Base):
    """AI-produced summary payload tied to a document and mode."""

    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    mode: Mapped[str] = mapped_column(String(128))  # determines output schema/sectioning
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")  # QUEUED / PROCESSING / SUMMARIZED / FAILED
    json_payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # machine-consumable summary content
    markdown: Mapped[str] = mapped_column(Text, default="")  # human-readable rendering
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)  # model id and token counts; no document text
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="summaries")


class Notification(Base):
    """One in-app notice. The body is a filename and an outcome, never a detected value."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class UserSetting(Base):
    """Per-user defaults. One row, created the first time settings are read."""

    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    default_mode: Mapped[str] = mapped_column(String(128), default="resume_anonymization")
    safe_mode: Mapped[bool] = mapped_column(default=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    # Ceiling is the deployment flag STORE_RAW_DETECTIONS. This cannot turn raw storage on by itself.
    store_raw_detections: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    """Immutable event log for user/document actions."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128))  # dot-namespaced event verb
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # event-specific context blob
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)


class Job(Base):
    """
    One queue unit for async work (detect / export / summary).

    Rows are created when the API enqueues Celery; the worker updates the latest
    row for `(document_id, job_type)` as it runs (see `tasks._update_job_status`).
    """

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    owner_user_id: Mapped[str] = mapped_column(String(128), index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)  # detect/export/summary
    status: Mapped[str] = mapped_column(String(32), index=True)  # QUEUED/PROCESSING/COMPLETED/FAILED
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="jobs")
