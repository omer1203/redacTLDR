"""
Primary API orchestration router for document workflows.

This module is intentionally "application-service-like": each endpoint coordinates
database state, task queue dispatch, audit logging, and response shaping.
"""

import uuid
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.celery_client import enqueue_task
from services.api.app.config import get_settings
from services.api.app.db import get_db
from services.api.app.enums import DocumentStatus
from services.api.app.models import Detection, Document, DocumentPage, ExportArtifact, Job, ManualRedaction, Summary
from services.api.app.schemas import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DetectionBulkOut,
    DetectionBulkUpdate,
    DetectionGroupOut,
    DetectionListOut,
    DetectionOut,
    DetectionUpdate,
    DocumentOut,
    DocumentPageOut,
    ExportOut,
    ExportRequest,
    JobOut,
    ManualRedactionCreate,
    ManualRedactionOut,
    ManualRedactionUpdate,
    NormalizedRect,
    OriginalUrlOut,
    ReviewDetectionOut,
    ReviewGroupOut,
    ReviewStateOut,
    SummaryOut,
    SummaryRequest,
)
from services.api.app.services.audit import log_event
from services.api.app.services.rate_limit import rate_limit
from services.api.app.services.summary_schema import mode_summary_template
from services.api.app.services.s3 import (
    delete_stored_object,
    get_original_object_metadata,
    make_export_key,
    make_originals_key,
    presign_download,
    presign_original_get,
    presign_put,
    redacted_download_name,
)
from services.shared.policy import entity_type_info

router = APIRouter(prefix="/v1/documents", tags=["documents"])
logger = logging.getLogger(__name__)


def _require_document(db: Session, doc_id: str, user_id: str) -> Document:
    """
    Load one document the caller is allowed to see, or 404.

    Authorization in M3 is `owner_user_id` + not soft-deleted. That is the
    single gate for every handler below.
    """
    # Convert path string to UUID to match DB column type.
    try:
        document_uuid = uuid.UUID(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="document not found") from exc
    statement = select(Document).where(
        Document.id == document_uuid,
        Document.owner_user_id == user_id,
        Document.deleted_at.is_(None),
    )
    document = db.scalar(statement)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def _queue_job_record(db: Session, document: Document, owner_user_id: str, job_type: str, payload: dict[str, Any]) -> Job:
    """
    Insert a `QUEUED` job before Celery is invoked.

    The worker will advance this row; keeping enqueue + worker updates on the
    same `(document_id, job_type, newest)` contract avoids orphan queue entries.
    """
    job = Job(
        document_id=document.id,
        owner_user_id=owner_user_id,
        workspace_id=document.workspace_id,
        job_type=job_type,
        status="QUEUED",
        payload=payload,
    )
    db.add(job)
    return job


@router.post("", response_model=CreateDocumentResponse)
def create_document(
    payload: CreateDocumentRequest,
    db: Session = Depends(get_db),
    user=CurrentUser,
    _limit=rate_limit("create", 60),
):
    """
    Create a new document record and return a presigned S3 PUT URL for client upload.

    API flow:
    - Validate media type.
    - Build stable storage key under originals bucket namespace.
    - Persist initial Document row with CREATED status.
    - Emit audit event.
    """
    filename = payload.filename.strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    since = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    created_today = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.owner_user_id == user.user_id, Document.created_at >= since)
    )
    if created_today is not None and created_today >= 50:
        raise HTTPException(status_code=429, detail="Daily document limit reached. Try again tomorrow.")

    # The backend owns key naming so clients never choose arbitrary S3 paths.
    document_id = uuid.uuid4()
    s3_key = make_originals_key(user.user_id, document_id, filename)
    try:
        presigned_put = presign_put(s3_key, payload.contentType, payload.sizeBytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record = Document(
        id=document_id,
        owner_user_id=user.user_id,
        workspace_id=None,
        # `document_type` and `mode` start identical; `mode` is the product toggle.
        document_type=payload.mode.value,
        s3_key_original=s3_key,
        user_id=user.user_id,
        filename=filename,
        content_type=payload.contentType,
        mode=payload.mode.value,
        safe_mode=payload.safeMode,
        s3_key=s3_key,
        status=DocumentStatus.CREATED.value,
    )
    db.add(record)
    db.flush()  # make `record.id` visible for audit + response without a round-trip
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.created",
        payload={"documentId": str(record.id), "mode": payload.mode.value},
        document_id=record.id,
    )
    db.commit()
    return CreateDocumentResponse(
        id=record.id,
        s3Key=s3_key,
        presignedPutUrl=presigned_put,
        status=DocumentStatus.CREATED,
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """List the caller's documents, newest first, with cursor-like limit/offset paging."""
    statement = (
        select(Document)
        .where(Document.owner_user_id == user.user_id)
        .where(Document.deleted_at.is_(None))
        .order_by(desc(Document.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Return a single document owned by the caller."""
    return _require_document(db, doc_id, user.user_id)


_PROCESS_ACTIVE = {"QUEUED", "PROCESSING"}
# Past OCR+detect. DETECTED is the pre-R2 name and is still accepted.
_PROCESS_ALREADY_DONE = {
    DocumentStatus.READY_FOR_REVIEW.value,
    DocumentStatus.DETECTED.value,
    DocumentStatus.EXPORT_QUEUED.value,
    DocumentStatus.EXPORTED.value,
    DocumentStatus.SUMMARY_QUEUED.value,
    DocumentStatus.SUMMARIZED.value,
}


def _latest_process_job(db: Session, document_id: uuid.UUID) -> Job | None:
    return db.scalar(
        select(Job)
        .where(Job.document_id == document_id, Job.job_type == "process", Job.deleted_at.is_(None))
        .order_by(desc(Job.created_at))
    )


def _enqueue_process(db: Session, document: Document, user_id: str) -> None:
    """Insert a process job row, commit it, then hand OCR+detect to Celery.

    The commit happens first so a fast worker can see the job row. The stage
    starts at detect when OCR JSON is already stored, so a retry does not show
    the reading step again.
    """
    job = _queue_job_record(
        db,
        document=document,
        owner_user_id=user_id,
        job_type="process",
        payload={"documentId": str(document.id)},
    )
    document.status = DocumentStatus.PROCESSING.value
    document.processing_stage = "detect" if document.ocr_s3_key else "ocr"
    document.error_code = None
    document.error_message = None
    db.commit()
    try:
        enqueue_task("process_document", str(document.id), user_id)
        db.expire_all()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for document process task: %s", document.id)
        job.status = "FAILED"
        job.last_error = "failed to queue ingestion job"
        document.status = DocumentStatus.FAILED.value
        document.error_code = "QUEUE_FAILED"
        document.error_message = "Failed to queue document processing."
        db.commit()
        raise HTTPException(status_code=503, detail="failed to queue ingestion job") from exc


@router.get("/{doc_id}/jobs", response_model=list[JobOut])
def list_jobs(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """List queue rows for one document, newest first."""
    document = _require_document(db, doc_id, user.user_id)
    statement = (
        select(Job)
        .where(Job.document_id == document.id, Job.deleted_at.is_(None))
        .order_by(desc(Job.created_at))
    )
    return list(db.scalars(statement).all())


@router.post("/{doc_id}/process")
def reprocess_document(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """
    Re-run OCR and detection for a failed or stuck document.

    Calling this on a document that is already queued or already ready is a no-op.
    OCR is skipped inside the worker when the OCR object is already stored.
    """
    document = _require_document(db, doc_id, user.user_id)
    if document.status == DocumentStatus.CREATED.value:
        raise HTTPException(status_code=409, detail="document has not been uploaded")
    if document.status in _PROCESS_ALREADY_DONE:
        return {"id": str(document.id), "status": document.status}

    latest = _latest_process_job(db, document.id)
    if document.status in {DocumentStatus.PROCESSING.value, DocumentStatus.DETECT_QUEUED.value} and latest and latest.status in _PROCESS_ACTIVE:
        return {"id": str(document.id), "status": document.status}

    _enqueue_process(db, document, user.user_id)
    document = _require_document(db, doc_id, user.user_id)
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.process.requeued",
        payload={"documentId": str(document.id)},
        document_id=document.id,
    )
    db.commit()
    return {"id": str(document.id), "status": document.status}


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Soft-delete the document row and remove its stored objects."""
    document = _require_document(db, doc_id, user.user_id)
    settings_buckets = _document_storage_keys(db, document)
    for bucket, key in settings_buckets:
        try:
            delete_stored_object(bucket, key)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to delete stored object for document=%s", document.id)
            raise HTTPException(status_code=502, detail="failed to delete stored file") from exc

    now = datetime.utcnow()
    document.deleted_at = now
    document.updated_at = now
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.deleted",
        payload={"documentId": str(document.id)},
        document_id=document.id,
    )
    db.commit()
    return None


def _document_storage_keys(db: Session, document: Document) -> list[tuple[str, str]]:
    settings = get_settings()
    keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key in (document.s3_key_original, document.s3_key, document.ocr_s3_key):
        pair = (settings.s3_bucket_originals, key)
        if key and pair not in seen:
            seen.add(pair)
            keys.append(pair)
    exports = db.scalars(select(ExportArtifact).where(ExportArtifact.document_id == document.id)).all()
    for artifact in exports:
        pair = (settings.s3_bucket_downloads, artifact.s3_key)
        if artifact.s3_key and pair not in seen:
            seen.add(pair)
            keys.append(pair)
    return keys


def _ingest_complete(doc_id: str, db: Session, user_id: str) -> dict[str, str]:
    """
    Mark upload ingestion complete and queue OCR plus detection.

    The client calls this after it successfully uploads the original PDF to S3.
    """
    document = _require_document(db, doc_id, user_id)
    if document.status in {
        DocumentStatus.PROCESSING.value,
        DocumentStatus.DETECT_QUEUED.value,
        DocumentStatus.READY_FOR_REVIEW.value,
        DocumentStatus.DETECTED.value,
        DocumentStatus.EXPORT_QUEUED.value,
        DocumentStatus.EXPORTED.value,
        DocumentStatus.SUMMARY_QUEUED.value,
        DocumentStatus.SUMMARIZED.value,
    }:
        return {"id": str(document.id), "status": document.status}

    object_meta = get_original_object_metadata(document.s3_key)
    if object_meta is None:
        raise HTTPException(status_code=409, detail="uploaded file not found in storage")
    s3_ct = (object_meta.get("content_type") or "").strip()
    db_ct = (document.content_type or "").strip()
    # Unsigned Content-Type uploads store as octet-stream in S3; still treat as the declared DB type.
    benign_mimes = {"", "binary/octet-stream", "application/octet-stream"}
    if s3_ct and s3_ct not in benign_mimes and s3_ct != db_ct:
        raise HTTPException(status_code=409, detail="uploaded file content type mismatch")

    # Commit success path to S3 *before* queueing: retries must not re-upload.
    document.status = DocumentStatus.UPLOADED.value
    log_event(
        db,
        user_id=user_id,
        event_type="document.upload.completed",
        payload={"documentId": str(document.id), "bytes": object_meta["content_length"]},
        document_id=document.id,
    )
    db.commit()

    # Job row + Celery: row first so a failure to enqueue is still auditable in DB.
    _enqueue_process(db, document, user_id)

    document = _require_document(db, doc_id, user_id)
    log_event(
        db,
        user_id=user_id,
        event_type="document.process.queued",
        payload={"documentId": str(document.id)},
        document_id=document.id,
    )
    db.commit()
    return {"id": str(document.id), "status": document.status}


@router.post("/{doc_id}/ingest-complete")
def ingest_complete(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Canonical ingest completion endpoint for M2 upload pipeline."""
    return _ingest_complete(doc_id, db, user.user_id)


@router.post("/{doc_id}/ingestDone")
def ingest_done(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Backward-compatible alias for existing clients. Prefer ingest-complete."""
    return _ingest_complete(doc_id, db, user.user_id)


@router.get("/{doc_id}/original-url", response_model=OriginalUrlOut)
def get_original_url(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Short-lived URL for the original PDF. Used by the review viewer, not for export."""
    document = _require_document(db, doc_id, user.user_id)
    key = document.s3_key_original or document.s3_key
    if not key:
        raise HTTPException(status_code=404, detail="original file not found")
    return OriginalUrlOut(url=presign_original_get(key))


@router.get("/{doc_id}/pages", response_model=list[DocumentPageOut])
def list_pages(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Page sizes and word counts. Extracted text stays in the OCR object in S3."""
    document = _require_document(db, doc_id, user.user_id)
    statement = (
        select(DocumentPage)
        .where(DocumentPage.document_id == document.id)
        .order_by(DocumentPage.page_number)
    )
    return list(db.scalars(statement).all())


def _detection_groups(detections: list[Detection]) -> list[DetectionGroupOut]:
    counts: dict[str, list[int]] = {}
    for item in detections:
        bucket = counts.setdefault(item.entity_type, [0, 0])
        bucket[0] += 1
        bucket[1] += 1 if item.accepted else 0
    groups = []
    for entity_type, (count, accepted_count) in sorted(counts.items()):
        info = entity_type_info(entity_type)
        groups.append(
            DetectionGroupOut(
                entity_type=entity_type,
                label=info.label,
                color=info.color,
                count=count,
                accepted_count=accepted_count,
            )
        )
    return groups


def _require_reviewable(document: Document) -> None:
    """Toggles are only meaningful once detection finished; a running pipeline replaces the rows."""
    if document.status not in _PROCESS_ALREADY_DONE:
        raise HTTPException(status_code=409, detail="document is still being processed")


@router.get("/{doc_id}/detections", response_model=DetectionListOut)
def list_detections(
    doc_id: str,
    page: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Detections in reading order, optionally for one page.

    `groups` always counts the whole document, so sidebar totals stay put while paging.
    """
    document = _require_document(db, doc_id, user.user_id)
    statement = (
        select(Detection)
        .where(Detection.document_id == document.id, Detection.deleted_at.is_(None))
        .order_by(Detection.page_number, Detection.char_start, Detection.created_at)
    )
    detections = list(db.scalars(statement).all())
    items = [item for item in detections if page is None or item.page_number == page]
    return DetectionListOut(
        document_id=document.id,
        mode=document.mode,
        safe_mode=document.safe_mode,
        page=page,
        total=len(items),
        items=[DetectionOut.model_validate(item) for item in items],
        groups=_detection_groups(detections),
    )


@router.patch("/{doc_id}/detections/{detection_id}", response_model=DetectionOut)
def update_detection(
    doc_id: str,
    detection_id: str,
    payload: DetectionUpdate,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Accept or reject one detection."""
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    try:
        detection_uuid = uuid.UUID(detection_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="detection not found") from exc
    detection = db.scalar(
        select(Detection).where(
            Detection.id == detection_uuid,
            Detection.document_id == document.id,
            Detection.deleted_at.is_(None),
        )
    )
    if not detection:
        raise HTTPException(status_code=404, detail="detection not found")
    detection.accepted = payload.accepted
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.detection.updated",
        payload={
            "documentId": str(document.id),
            "detectionId": str(detection.id),
            "entityType": detection.entity_type,
            "accepted": payload.accepted,
        },
        document_id=document.id,
    )
    db.commit()
    db.refresh(detection)
    return detection


@router.post("/{doc_id}/detections/bulk", response_model=DetectionBulkOut)
def bulk_update_detections(
    doc_id: str,
    payload: DetectionBulkUpdate,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Accept or reject every detection of one entity type."""
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    result = db.execute(
        update(Detection)
        .where(
            Detection.document_id == document.id,
            Detection.entity_type == payload.entityType,
            Detection.deleted_at.is_(None),
        )
        .values(accepted=payload.accepted)
    )
    updated = int(result.rowcount or 0)
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.detection.bulk_updated",
        payload={
            "documentId": str(document.id),
            "entityType": payload.entityType,
            "accepted": payload.accepted,
            "updated": updated,
        },
        document_id=document.id,
    )
    db.commit()
    return DetectionBulkOut(entity_type=payload.entityType, accepted=payload.accepted, updated=updated)


def _rect_payload(rect: NormalizedRect) -> dict[str, float]:
    """Store drawn boxes at the same precision as detection rects."""
    return {key: round(value, 6) for key, value in rect.model_dump().items()}


def _redaction_out(item: ManualRedaction) -> ManualRedactionOut:
    info = entity_type_info(item.entity_type)
    return ManualRedactionOut(
        id=item.id,
        page_number=item.page_number,
        entity_type=item.entity_type,
        label=info.label,
        color=info.color,
        kind=item.redaction_kind,
        bbox=item.bbox or {},
        status=item.status,
        created_at=item.created_at,
    )


def _require_page(document: Document, page_number: int) -> None:
    # Documents from before R2 have no page count; their boxes are not range-checked.
    if document.page_count is not None and page_number > document.page_count:
        raise HTTPException(status_code=422, detail="page number is past the end of the document")


def _require_redaction(db: Session, document: Document, redaction_id: str) -> ManualRedaction:
    try:
        redaction_uuid = uuid.UUID(redaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="redaction not found") from exc
    redaction = db.scalar(
        select(ManualRedaction).where(
            ManualRedaction.id == redaction_uuid,
            ManualRedaction.document_id == document.id,
            ManualRedaction.deleted_at.is_(None),
        )
    )
    if not redaction:
        raise HTTPException(status_code=404, detail="redaction not found")
    return redaction


def _replayed_redaction(db: Session, document: Document, redaction_id: uuid.UUID) -> ManualRedactionOut | None:
    """The stored row for a repeated create, or None when the id is new."""
    existing = db.get(ManualRedaction, redaction_id)
    if existing is None:
        return None
    if existing.document_id != document.id or existing.deleted_at is not None:
        raise HTTPException(status_code=409, detail="redaction id is already in use")
    return _redaction_out(existing)


@router.post("/{doc_id}/redactions", response_model=ManualRedactionOut, status_code=201)
def create_manual_redaction(
    doc_id: str,
    payload: ManualRedactionCreate,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Save a box the reviewer drew.

    Replaying a create with the same client id returns the stored row unchanged,
    so the browser can retry a save without producing a second box.
    """
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    _require_page(document, payload.page_number)
    if payload.id is not None:
        replay = _replayed_redaction(db, document, payload.id)
        if replay is not None:
            return replay
    redaction = ManualRedaction(
        document_id=document.id,
        redaction_kind="bbox",
        entity_type=payload.entity_type,
        page_number=payload.page_number,
        bbox=_rect_payload(payload.bbox),
        span={},
        status="ACTIVE",
        created_by=user.user_id,
    )
    if payload.id is not None:
        redaction.id = payload.id
    db.add(redaction)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent retry with the same id won the insert.
        db.rollback()
        replay = _replayed_redaction(db, document, payload.id) if payload.id is not None else None
        if replay is None:
            raise
        return replay
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.redaction.saved",
        payload={
            "documentId": str(document.id),
            "redactionId": str(redaction.id),
            "kind": redaction.redaction_kind,
            "pageNumber": redaction.page_number,
        },
        document_id=document.id,
    )
    db.commit()
    db.refresh(redaction)
    return _redaction_out(redaction)


@router.patch("/{doc_id}/redactions/{redaction_id}", response_model=ManualRedactionOut)
def update_manual_redaction(
    doc_id: str,
    redaction_id: str,
    payload: ManualRedactionUpdate,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Move, resize, or relabel a drawn box. The page cannot change."""
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    redaction = _require_redaction(db, document, redaction_id)
    changed: list[str] = []
    if payload.bbox is not None:
        redaction.bbox = _rect_payload(payload.bbox)
        changed.append("bbox")
    if payload.entity_type is not None:
        redaction.entity_type = payload.entity_type
        changed.append("entityType")
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.redaction.updated",
        payload={"documentId": str(document.id), "redactionId": str(redaction.id), "changed": changed},
        document_id=document.id,
    )
    db.commit()
    db.refresh(redaction)
    return _redaction_out(redaction)


@router.delete("/{doc_id}/redactions/{redaction_id}", status_code=204)
def delete_manual_redaction(
    doc_id: str,
    redaction_id: str,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Soft-delete a drawn box. Export ignores deleted rows; the audit trail keeps them."""
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    redaction = _require_redaction(db, document, redaction_id)
    redaction.deleted_at = datetime.utcnow()
    redaction.status = "DELETED"
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.redaction.deleted",
        payload={"documentId": str(document.id), "redactionId": str(redaction.id)},
        document_id=document.id,
    )
    db.commit()
    return None


_EXPORT_ACTIVE = {"QUEUED", "PROCESSING"}
# Download links are short-lived; the web asks for a fresh one on every click.
_DOWNLOAD_URL_TTL_SECONDS = 300


def _export_out(document: Document, artifact: ExportArtifact) -> ExportOut:
    url = None
    if artifact.status == DocumentStatus.EXPORTED.value:
        url = presign_download(
            artifact.s3_key,
            expires=_DOWNLOAD_URL_TTL_SECONDS,
            filename=redacted_download_name(document.filename),
        )
    return ExportOut(
        id=artifact.id,
        document_id=document.id,
        status=artifact.status,
        include_labels=bool((artifact.options or {}).get("includeLabels", False)),
        page_count=artifact.page_count,
        redaction_count=artifact.redaction_count,
        size_bytes=artifact.size_bytes,
        error_code=artifact.error_code,
        error_message=artifact.error_message,
        created_at=artifact.created_at,
        completed_at=artifact.completed_at,
        download_url=url,
    )


def _exports_query(document: Document):
    return (
        select(ExportArtifact)
        .where(ExportArtifact.document_id == document.id, ExportArtifact.deleted_at.is_(None))
        .order_by(desc(ExportArtifact.created_at))
    )


@router.post("/{doc_id}/export", response_model=ExportOut)
def queue_export(
    doc_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    user=CurrentUser,
    _limit=rate_limit("export", 30),
):
    """
    Queue a new redacted PDF built from the review as it is when the worker runs.

    Every call creates a new export (its own row and S3 object), except while
    one is already queued or running: then that one is returned, so a double
    click does not build twice. The row is committed before Celery is called
    so the worker always finds it.
    """
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    # Serialize concurrent requests for this document so the in-flight check holds.
    db.execute(select(Document.id).where(Document.id == document.id).with_for_update())
    active = db.scalar(_exports_query(document).where(ExportArtifact.status.in_(_EXPORT_ACTIVE)))
    if active:
        db.commit()
        return _export_out(document, active)

    export_id = uuid.uuid4()
    artifact = ExportArtifact(
        id=export_id,
        document_id=document.id,
        s3_key=make_export_key(user.user_id, str(document.id), str(export_id)),
        status="QUEUED",
        options={"includeLabels": payload.include_labels},
    )
    db.add(artifact)
    previous_status = document.status
    document.status = DocumentStatus.EXPORT_QUEUED.value
    job = _queue_job_record(
        db,
        document=document,
        owner_user_id=user.user_id,
        job_type="export",
        payload={"documentId": str(document.id), "exportId": str(export_id), "includeLabels": payload.include_labels},
    )
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.export.queued",
        payload={"documentId": str(document.id), "exportId": str(export_id), "includeLabels": payload.include_labels},
        document_id=document.id,
    )
    db.commit()
    try:
        enqueue_task("export_job", str(document.id), user.user_id, str(export_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for export task document=%s", document.id)
        artifact.status = "FAILED"
        artifact.error_code = "QUEUE_FAILED"
        artifact.error_message = "The export could not be queued. You can try again."
        job.status = "FAILED"
        job.last_error = "failed to queue export job"
        if document.status == DocumentStatus.EXPORT_QUEUED.value:
            document.status = previous_status
        db.commit()
        raise HTTPException(status_code=503, detail="failed to queue export job") from exc
    # The worker may already have finished (eager mode, or a fast worker).
    db.refresh(artifact)
    db.refresh(document)
    return _export_out(document, artifact)


@router.get("/{doc_id}/export", response_model=ExportOut)
def get_export(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Latest export; `downloadUrl` only when its verified file is stored."""
    document = _require_document(db, doc_id, user.user_id)
    artifact = db.scalar(_exports_query(document))
    if not artifact:
        raise HTTPException(status_code=404, detail="export not found")
    return _export_out(document, artifact)


@router.get("/{doc_id}/exports", response_model=list[ExportOut])
def list_exports(
    doc_id: str,
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """Export history, newest first."""
    document = _require_document(db, doc_id, user.user_id)
    return [_export_out(document, artifact) for artifact in db.scalars(_exports_query(document).limit(limit)).all()]


@router.get("/{doc_id}/exports/{export_id}", response_model=ExportOut)
def get_export_by_id(doc_id: str, export_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """One export. The web polls this while it runs and calls it again for a fresh download link."""
    document = _require_document(db, doc_id, user.user_id)
    try:
        export_uuid = uuid.UUID(export_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="export not found") from exc
    artifact = db.scalar(_exports_query(document).where(ExportArtifact.id == export_uuid))
    if not artifact:
        raise HTTPException(status_code=404, detail="export not found")
    return _export_out(document, artifact)


_SUMMARY_ACTIVE = {"QUEUED", "PROCESSING"}


def _summary_out(summary: Summary) -> SummaryOut:
    body = summary.json_payload or {}
    return SummaryOut(
        id=summary.id,
        mode=summary.mode,
        status=summary.status,
        schema_version=int(body.get("schemaVersion") or 1),
        safe_mode=body.get("safeMode"),
        json_payload=body,
        markdown=summary.markdown or "",
        token_usage=summary.token_usage or {},
        error_code=summary.error_code,
        error_message=summary.error_message,
        created_at=summary.created_at,
        completed_at=summary.completed_at,
    )


def _summaries_query(document: Document):
    return (
        select(Summary)
        .where(Summary.document_id == document.id, Summary.deleted_at.is_(None))
        .order_by(desc(Summary.created_at))
    )


@router.post("/{doc_id}/summaries", response_model=SummaryOut)
def queue_summary(
    doc_id: str,
    payload: SummaryRequest,
    db: Session = Depends(get_db),
    user=CurrentUser,
    _limit=rate_limit("summary", 20),
):
    """
    Queue a summary of the document as reviewed now.

    Safe mode is read from the document when the worker runs, not from this
    request. A summary already queued or running is returned instead of
    starting a second one. The row is committed before Celery is called.
    """
    document = _require_document(db, doc_id, user.user_id)
    _require_reviewable(document)
    db.execute(select(Document.id).where(Document.id == document.id).with_for_update())
    active = db.scalar(_summaries_query(document).where(Summary.status.in_(_SUMMARY_ACTIVE)))
    if active:
        db.commit()
        return _summary_out(active)

    summary_id = uuid.uuid4()
    summary = Summary(id=summary_id, document_id=document.id, mode=document.mode, status="QUEUED")
    db.add(summary)
    previous_status = document.status
    document.status = DocumentStatus.SUMMARY_QUEUED.value
    job = _queue_job_record(
        db,
        document=document,
        owner_user_id=user.user_id,
        job_type="summary",
        payload={
            "documentId": str(document.id),
            "summaryId": str(summary_id),
            "includeMarkdown": payload.includeMarkdown,
        },
    )
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.summary.queued",
        payload={"documentId": str(document.id), "summaryId": str(summary_id), "mode": document.mode},
        document_id=document.id,
    )
    db.commit()
    try:
        enqueue_task("summary_job", str(document.id), user.user_id, payload.includeMarkdown, str(summary_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for summary task document=%s", document.id)
        summary.status = "FAILED"
        summary.error_code = "QUEUE_FAILED"
        summary.error_message = "The summary could not be queued. You can try again."
        job.status = "FAILED"
        job.last_error = "failed to queue summary job"
        if document.status == DocumentStatus.SUMMARY_QUEUED.value:
            document.status = previous_status
        db.commit()
        raise HTTPException(status_code=503, detail="failed to queue summary job") from exc
    db.refresh(summary)
    return _summary_out(summary)


@router.get("/{doc_id}/summaries/latest", response_model=SummaryOut)
def get_latest_summary(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Most recent summary. Poll this while `status` is QUEUED or PROCESSING."""
    document = _require_document(db, doc_id, user.user_id)
    summary = db.scalar(_summaries_query(document))
    if not summary:
        raise HTTPException(status_code=404, detail="summary not found")
    return _summary_out(summary)


@router.get("/{doc_id}/review-state", response_model=ReviewStateOut)
def get_review_state(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """
    Serve everything the review screen needs in one call.

    Denormalizes the document, page sizes, detections, per-type counts, and drawn
    boxes. Works in any status so the screen can show "still processing";
    `reviewable` tells the client whether edits are allowed yet.
    """
    document = _require_document(db, doc_id, user.user_id)
    pages = list(
        db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document.id).order_by(DocumentPage.page_number)
        ).all()
    )
    detections = list(
        db.scalars(
            select(Detection)
            .where(Detection.document_id == document.id, Detection.deleted_at.is_(None))
            .order_by(Detection.page_number, Detection.char_start, Detection.created_at)
        ).all()
    )
    redactions = list(
        db.scalars(
            select(ManualRedaction)
            .where(ManualRedaction.document_id == document.id, ManualRedaction.deleted_at.is_(None))
            .order_by(ManualRedaction.created_at)
        ).all()
    )
    return ReviewStateOut(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        processing_stage=document.processing_stage,
        mode=document.mode,
        safe_mode=document.safe_mode,
        page_count=document.page_count,
        reviewable=document.status in _PROCESS_ALREADY_DONE,
        pages=[DocumentPageOut.model_validate(page) for page in pages],
        groups=[
            ReviewGroupOut(
                entity_type=group.entity_type,
                label=group.label,
                color=group.color,
                count=group.count,
                accepted_count=group.accepted_count,
            )
            for group in _detection_groups(detections)
        ],
        detections=[
            ReviewDetectionOut(
                id=item.id,
                entity_type=item.entity_type,
                page_number=item.page_number,
                block_ref=item.block_ref,
                bbox=item.bbox or {},
                rects=item.rects or [],
                masked_text=item.masked_text,
                policy_action=item.policy_action,
                confidence=item.confidence,
                accepted=item.accepted,
                source=item.source,
            )
            for item in detections
        ],
        manual_redactions=[_redaction_out(item) for item in redactions],
    )


@router.get("/modes/schema")
def mode_schema() -> dict[str, list[str]]:
    """Field names of each mode's summary. Same list the worker validates against."""
    from services.api.app.enums import DocumentMode

    return {mode.value: list(mode_summary_template(mode)) for mode in DocumentMode}
