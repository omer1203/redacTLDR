from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from services.api.app.enums import DocumentMode, DocumentStatus
from services.shared.policy import MANUAL_ENTITY_TYPE


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
    page_count: int | None = None
    processing_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentPageOut(BaseModel):
    """Page geometry for the viewer. This payload has no extracted text."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    page_number: int = Field(alias="pageNumber")
    width: float
    height: float
    word_count: int = Field(alias="wordCount")
    has_text_layer: bool = Field(alias="hasTextLayer")


class OriginalUrlOut(BaseModel):
    url: str


class DetectionOut(BaseModel):
    """One detection. `detected_text` is masked unless raw storage is enabled on the worker."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    detected_text: str
    page_number: int
    block_ref: str
    confidence: float
    bbox: dict[str, Any]
    accepted: bool
    source: str
    rects: list[dict[str, Any]] = Field(default_factory=list)
    char_start: int | None = None
    char_end: int | None = None
    masked_text: str | None = None
    policy_action: str | None = None
    rule_id: str | None = None


class DetectionGroupOut(BaseModel):
    """Per-type counts for the review sidebar. Always covers the whole document."""

    entity_type: str
    label: str
    color: str
    count: int
    accepted_count: int


class DetectionListOut(BaseModel):
    document_id: UUID
    mode: DocumentMode
    safe_mode: bool
    page: int | None = None
    total: int
    items: list[DetectionOut]
    groups: list[DetectionGroupOut]


class DetectionUpdate(BaseModel):
    accepted: bool


class DetectionBulkUpdate(BaseModel):
    entityType: str = Field(min_length=1, max_length=64)
    accepted: bool


class DetectionBulkOut(BaseModel):
    entity_type: str
    accepted: bool
    updated: int


# Smallest side a drawn box may have, as a fraction of the page (about 1.5 pt on
# US Letter). Anything smaller is an accidental click, not a redaction.
MIN_RECT_SIDE = 0.002
# Float slack for x + width landing a hair past 1.0 after client-side rounding.
_EDGE_TOLERANCE = 1e-6


class NormalizedRect(BaseModel):
    """A box in fractions of page width and height, origin top-left.

    Same coordinate space as detection `rects`, so the viewer and the R5 export
    treat drawn boxes and detected boxes identically.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_page(self) -> "NormalizedRect":
        if self.width < MIN_RECT_SIDE or self.height < MIN_RECT_SIDE:
            raise ValueError("box is too small")
        if self.x + self.width > 1 + _EDGE_TOLERANCE or self.y + self.height > 1 + _EDGE_TOLERANCE:
            raise ValueError("box extends past the page edge")
        return self


_ENTITY_TYPE_PATTERN = r"^[A-Z][A-Z0-9_]*$"


class ManualRedactionCreate(BaseModel):
    """A box drawn by the reviewer.

    `id` is optional and client-generated. Sending the same id again returns the
    existing row instead of creating a duplicate, so a retried save is harmless.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: UUID | None = None
    page_number: int = Field(alias="pageNumber", ge=1)
    bbox: NormalizedRect
    entity_type: str = Field(
        default=MANUAL_ENTITY_TYPE, alias="entityType", min_length=1, max_length=64, pattern=_ENTITY_TYPE_PATTERN
    )


class ManualRedactionUpdate(BaseModel):
    """Move/resize a drawn box or relabel it. At least one field is required."""

    model_config = ConfigDict(populate_by_name=True)

    bbox: NormalizedRect | None = None
    entity_type: str | None = Field(
        default=None, alias="entityType", min_length=1, max_length=64, pattern=_ENTITY_TYPE_PATTERN
    )

    @model_validator(mode="after")
    def _has_change(self) -> "ManualRedactionUpdate":
        if self.bbox is None and self.entity_type is None:
            raise ValueError("nothing to update")
        return self


class ManualRedactionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    page_number: int = Field(alias="pageNumber")
    entity_type: str = Field(alias="entityType")
    label: str
    color: str
    kind: str
    bbox: dict[str, Any]
    status: str
    created_at: datetime = Field(alias="createdAt")


class ReviewGroupOut(BaseModel):
    """Per-type detection counts for the review sidebar (camelCase twin of DetectionGroupOut)."""

    model_config = ConfigDict(populate_by_name=True)

    entity_type: str = Field(alias="entityType")
    label: str
    color: str
    count: int
    accepted_count: int = Field(alias="acceptedCount")


class ReviewDetectionOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    entity_type: str = Field(alias="entityType")
    page_number: int = Field(alias="pageNumber")
    block_ref: str = Field(alias="blockRef")
    bbox: dict[str, Any]
    rects: list[dict[str, Any]]
    masked_text: str | None = Field(alias="maskedText")
    policy_action: str | None = Field(alias="policyAction")
    confidence: float
    accepted: bool
    source: str


class ReviewStateOut(BaseModel):
    """Everything the review screen needs in one call. No raw document text."""

    model_config = ConfigDict(populate_by_name=True)

    document_id: UUID = Field(alias="documentId")
    filename: str
    status: DocumentStatus
    processing_stage: str | None = Field(alias="processingStage")
    mode: DocumentMode
    safe_mode: bool = Field(alias="safeMode")
    page_count: int | None = Field(alias="pageCount")
    reviewable: bool
    pages: list[DocumentPageOut]
    groups: list[ReviewGroupOut]
    detections: list[ReviewDetectionOut]
    manual_redactions: list[ManualRedactionOut] = Field(alias="manualRedactions")
    # Reserved for collaboration events; always empty today.
    activity: list[dict[str, Any]] = Field(default_factory=list)


class ExportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Draw the entity type ("Email") in white on each black box.
    include_labels: bool = Field(default=False, alias="includeLabels")
    # Accepted from older clients. Every request builds a new export from the
    # current review, so this no longer changes anything.
    forceRegenerate: bool = False


class ExportOut(BaseModel):
    """One export build. `downloadUrl` is set only when the verified file is stored."""

    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    document_id: UUID = Field(alias="documentId")
    status: str  # QUEUED / PROCESSING / EXPORTED / FAILED
    include_labels: bool = Field(alias="includeLabels")
    page_count: int | None = Field(default=None, alias="pageCount")
    redaction_count: int | None = Field(default=None, alias="redactionCount")
    size_bytes: int | None = Field(default=None, alias="sizeBytes")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime = Field(alias="createdAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")
    download_url: str | None = Field(default=None, alias="downloadUrl")


class SummaryRequest(BaseModel):
    includeMarkdown: bool = True


class SummaryOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    mode: DocumentMode
    status: str
    schema_version: int = Field(default=1, alias="schemaVersion")
    safe_mode: bool | None = Field(default=None, alias="safeMode")
    json_payload: dict[str, Any] = Field(alias="json")
    markdown: str
    token_usage: dict[str, Any] = Field(alias="tokenUsage")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class ErrorEnvelope(BaseModel):
    error: dict[str, Any]
