from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from services.api.app.enums import DocumentMode, DocumentStatus


class UserPrincipal(BaseModel):
    user_id: str
    email: str | None = None
    session_id: str | None = None


class CreateDocumentRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    contentType: str = Field(default="application/pdf", min_length=1, max_length=128)
    mode: DocumentMode
    safeMode: bool = True
    sizeBytes: int | None = Field(default=None, ge=1)


class CreateDocumentResponse(BaseModel):
    id: UUID
    s3Key: str
    presignedPutUrl: str
    status: DocumentStatus


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    job_type: str = Field(alias="jobType")
    status: str
    attempt_count: int = Field(alias="attemptCount")
    last_error: str | None = Field(default=None, alias="lastError")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    mode: DocumentMode
    safe_mode: bool
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DetectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    detected_text: str
    page_number: int
    block_ref: str
    confidence: float
    bbox: dict[str, Any]
    accepted: bool


class ManualRedactionUpsert(BaseModel):
    redaction_kind: str = Field(default="bbox")
    entity_type: str = Field(default="CUSTOM")
    page_number: int
    block_ref: str = ""
    bbox: dict[str, Any] = Field(default_factory=dict)
    span: dict[str, Any] = Field(default_factory=dict)
    status: str = "ACTIVE"


class ExportRequest(BaseModel):
    forceRegenerate: bool = False


class ExportOut(BaseModel):
    id: UUID
    status: str
    downloadUrl: str | None = None


class SummaryRequest(BaseModel):
    includeMarkdown: bool = True


class SummaryOut(BaseModel):
    id: UUID
    mode: DocumentMode
    status: str
    json_payload: dict[str, Any] = Field(alias="json")
    markdown: str
    token_usage: dict[str, Any] = Field(alias="tokenUsage")


class ErrorEnvelope(BaseModel):
    error: dict[str, Any]
