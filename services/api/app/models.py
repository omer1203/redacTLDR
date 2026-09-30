"""
SQLAlchemy ORM models representing the core product lifecycle.

These models are the canonical source for persisted state semantics in the API.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    # Child entities produced/managed as the document moves through processing.
    detections = relationship("Detection", back_populates="document", cascade="all, delete-orphan")
    redactions = relationship("ManualRedaction", back_populates="document", cascade="all, delete-orphan")
    exports = relationship("ExportArtifact", back_populates="document", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="document", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="document", cascade="all, delete-orphan")


class Detection(Base):
    """Machine-detected sensitive entity candidate extracted from a document."""

    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))  # e.g. NAME, SSN, EMAIL
    detected_text: Mapped[str] = mapped_column(Text)  # raw snippet identified by detector
    page_number: Mapped[int] = mapped_column(default=1)
    block_ref: Mapped[str] = mapped_column(String(128), default="")  # OCR/parse reference key
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[dict] = mapped_column(JSONB, default=dict)  # bounding box for UI overlay
    source: Mapped[str] = mapped_column(String(64), default="comprehend")  # detector backend name
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
    """Generated downloadable output artifact for a document revision."""

    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    s3_key: Mapped[str] = mapped_column(String(1024))  # path in downloads bucket
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")  # QUEUED/EXPORTED/FAILED, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="exports")


class Summary(Base):
    """AI-produced summary payload tied to a document and mode."""

    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    mode: Mapped[str] = mapped_column(String(128))  # determines output schema/sectioning
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")
    json_payload: Mapped[dict] = mapped_column(JSONB, default=dict)  # machine-consumable summary content
    markdown: Mapped[str] = mapped_column(Text, default="")  # human-readable rendering
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)  # LLM accounting/debug metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None, index=True)

    document = relationship("Document", back_populates="summaries")


class AuditLog(Base):
    """Immutable event log for user/document actions."""

    __tablename__ = "audit_logs"

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
