import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from services.api.app.db import Base
from services.api.app.enums import DocumentMode, DocumentStatus


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/pdf")
    s3_key: Mapped[str] = mapped_column(String(1024), unique=True)
    mode: Mapped[str] = mapped_column(String(128), default=DocumentMode.RESUME_ANONYMIZATION.value)
    safe_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(64), default=DocumentStatus.CREATED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    detections = relationship("Detection", back_populates="document", cascade="all, delete-orphan")
    redactions = relationship("ManualRedaction", back_populates="document", cascade="all, delete-orphan")
    exports = relationship("ExportArtifact", back_populates="document", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="document", cascade="all, delete-orphan")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    detected_text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int] = mapped_column(default=1)
    block_ref: Mapped[str] = mapped_column(String(128), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[dict] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(String(64), default="comprehend")
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="detections")


class ManualRedaction(Base):
    __tablename__ = "manual_redactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    redaction_kind: Mapped[str] = mapped_column(String(32), default="bbox")
    entity_type: Mapped[str] = mapped_column(String(64), default="CUSTOM")
    page_number: Mapped[int] = mapped_column(default=1)
    block_ref: Mapped[str] = mapped_column(String(128), default="")
    bbox: Mapped[dict] = mapped_column(JSONB, default=dict)
    span: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="redactions")


class ExportArtifact(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    s3_key: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="exports")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), index=True)
    mode: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), default="QUEUED")
    json_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    markdown: Mapped[str] = mapped_column(Text, default="")
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="summaries")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
