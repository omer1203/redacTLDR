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
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.celery_client import enqueue_task
from services.api.app.config import get_settings
from services.api.app.db import get_db
from services.api.app.enums import DocumentStatus
from services.api.app.models import Detection, Document, ExportArtifact, Job, ManualRedaction, Summary
from services.api.app.schemas import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DetectionOut,
    DocumentOut,
    ExportOut,
    ExportRequest,
    JobOut,
    ManualRedactionUpsert,
    SummaryOut,
    SummaryRequest,
)
from services.api.app.services.audit import log_event
from services.api.app.services.s3 import (
    delete_stored_object,
    get_original_object_metadata,
    make_originals_key,
    presign_download,
    presign_put,
)

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
def create_document(payload: CreateDocumentRequest, db: Session = Depends(get_db), user=CurrentUser):
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
    limit: int = Query(default=20, ge=1, le=100),
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


_DETECT_ACTIVE = {"QUEUED", "PROCESSING"}
_DETECT_ALREADY_DONE = {
    DocumentStatus.DETECTED.value,
    DocumentStatus.EXPORT_QUEUED.value,
    DocumentStatus.EXPORTED.value,
    DocumentStatus.SUMMARY_QUEUED.value,
    DocumentStatus.SUMMARIZED.value,
}


def _latest_detect_job(db: Session, document_id: uuid.UUID) -> Job | None:
    return db.scalar(
        select(Job)
        .where(Job.document_id == document_id, Job.job_type == "detect", Job.deleted_at.is_(None))
        .order_by(desc(Job.created_at))
    )


def _enqueue_detect(db: Session, document: Document, user_id: str) -> None:
    """Insert a detect job row, commit it, then hand the work to Celery.

    The commit happens first so a fast worker can see the job row.
    """
    job = _queue_job_record(
        db,
        document=document,
        owner_user_id=user_id,
        job_type="detect",
        payload={"documentId": str(document.id)},
    )
    document.status = DocumentStatus.DETECT_QUEUED.value
    db.commit()
    try:
        enqueue_task("detect_job", str(document.id), user_id)
        db.expire_all()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for document detect task: %s", document.id)
        job.status = "FAILED"
        job.last_error = "failed to queue ingestion job"
        document.status = DocumentStatus.FAILED.value
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
    Re-run detection for a failed or stuck document.

    Calling this on a document that is already queued or already detected is a no-op.
    """
    document = _require_document(db, doc_id, user.user_id)
    if document.status == DocumentStatus.CREATED.value:
        raise HTTPException(status_code=409, detail="document has not been uploaded")
    if document.status in _DETECT_ALREADY_DONE:
        return {"id": str(document.id), "status": document.status}

    latest = _latest_detect_job(db, document.id)
    if document.status == DocumentStatus.DETECT_QUEUED.value and latest and latest.status in _DETECT_ACTIVE:
        return {"id": str(document.id), "status": document.status}

    _enqueue_detect(db, document, user.user_id)
    document = _require_document(db, doc_id, user.user_id)
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.detect.requeued",
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
    for key in (document.s3_key_original, document.s3_key):
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
    Mark upload ingestion complete and queue async detection.

    The client calls this after it successfully uploads the original PDF to S3.
    """
    document = _require_document(db, doc_id, user_id)
    if document.status in {
        DocumentStatus.DETECT_QUEUED.value,
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
    _enqueue_detect(db, document, user_id)

    document = _require_document(db, doc_id, user_id)
    log_event(
        db,
        user_id=user_id,
        event_type="document.detect.queued",
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


@router.get("/{doc_id}/detections", response_model=list[DetectionOut])
def list_detections(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Return machine detections for the document, ordered by page."""
    document = _require_document(db, doc_id, user.user_id)
    statement = (
        select(Detection)
        .where(Detection.document_id == document.id, Detection.deleted_at.is_(None))
        .order_by(Detection.page_number)
    )
    return list(db.scalars(statement).all())


@router.post("/{doc_id}/redactions")
def upsert_manual_redaction(
    doc_id: str,
    payload: ManualRedactionUpsert,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """
    Persist a manual redaction instruction provided by the user/reviewer.

    Note: despite "upsert" naming, current behavior is append-only (new row each call).
    """
    document = _require_document(db, doc_id, user.user_id)
    redaction = ManualRedaction(
        document_id=document.id,
        redaction_kind=payload.redaction_kind,
        entity_type=payload.entity_type,
        page_number=payload.page_number,
        block_ref=payload.block_ref,
        bbox=payload.bbox,
        span=payload.span,
        status=payload.status,
        created_by=user.user_id,
    )
    db.add(redaction)
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.redaction.saved",
        payload={"documentId": str(document.id), "kind": payload.redaction_kind},
        document_id=document.id,
    )
    db.commit()
    return {"id": str(redaction.id), "status": redaction.status}


@router.post("/{doc_id}/export", response_model=ExportOut)
def queue_export(
    doc_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """
    Queue PDF export generation and return export status metadata.

    If an exported artifact already exists and regeneration is not forced, this
    endpoint returns the existing artifact with a fresh presigned download URL.
    """
    document = _require_document(db, doc_id, user.user_id)
    if document.status == DocumentStatus.EXPORTED.value and not payload.forceRegenerate:
        existing = db.scalar(
            select(ExportArtifact).where(ExportArtifact.document_id == document.id).order_by(desc(ExportArtifact.created_at))
        )
        if existing:
            return ExportOut(id=existing.id, status=existing.status, downloadUrl=presign_download(existing.s3_key))

    # New export request -> create artifact row and queue background worker.
    artifact = ExportArtifact(document_id=document.id, s3_key=f"exports/{user.user_id}/{document.id}.pdf")
    db.add(artifact)
    document.status = DocumentStatus.EXPORT_QUEUED.value
    _queue_job_record(
        db,
        document=document,
        owner_user_id=user.user_id,
        job_type="export",
        payload={"documentId": str(document.id), "forceRegenerate": payload.forceRegenerate},
    )
    try:
        enqueue_task("export_job", str(document.id), user.user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for export task document=%s", document.id)
        raise HTTPException(status_code=503, detail="failed to queue export job") from exc
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.export.queued",
        payload={"documentId": str(document.id)},
        document_id=document.id,
    )
    db.commit()
    return ExportOut(id=artifact.id, status="QUEUED")


@router.get("/{doc_id}/export", response_model=ExportOut)
def get_export(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Fetch latest export record; include download URL only when artifact is ready."""
    document = _require_document(db, doc_id, user.user_id)
    artifact = db.scalar(
        select(ExportArtifact).where(ExportArtifact.document_id == document.id).order_by(desc(ExportArtifact.created_at))
    )
    if not artifact:
        raise HTTPException(status_code=404, detail="export not found")
    url = presign_download(artifact.s3_key) if artifact.status == "EXPORTED" else None
    return ExportOut(id=artifact.id, status=artifact.status, downloadUrl=url)


@router.post("/{doc_id}/summaries")
def queue_summary(
    doc_id: str,
    payload: SummaryRequest,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    """
    Queue AI summary generation for the given document/mode.

    Summary content is generated asynchronously and can be polled via
    `/summaries/latest`.
    """
    document = _require_document(db, doc_id, user.user_id)
    summary = Summary(document_id=document.id, mode=document.mode, status="QUEUED")
    db.add(summary)
    document.status = DocumentStatus.SUMMARY_QUEUED.value
    _queue_job_record(
        db,
        document=document,
        owner_user_id=user.user_id,
        job_type="summary",
        payload={"documentId": str(document.id), "includeMarkdown": payload.includeMarkdown},
    )
    try:
        enqueue_task("summary_job", str(document.id), user.user_id, payload.includeMarkdown)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed enqueue for summary task document=%s", document.id)
        raise HTTPException(status_code=503, detail="failed to queue summary job") from exc
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.summary.queued",
        payload={"documentId": str(document.id), "mode": document.mode},
        document_id=document.id,
    )
    db.commit()
    return {"id": str(summary.id), "status": "QUEUED"}


@router.get("/{doc_id}/summaries/latest", response_model=SummaryOut)
def get_latest_summary(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """Return most recent summary payload for this document."""
    document = _require_document(db, doc_id, user.user_id)
    summary = db.scalar(select(Summary).where(Summary.document_id == document.id).order_by(desc(Summary.created_at)))
    if not summary:
        raise HTTPException(status_code=404, detail="summary not found")
    return SummaryOut(
        id=summary.id,
        mode=document.mode,
        status=summary.status,
        json_payload=summary.json_payload,
        markdown=summary.markdown,
        token_usage=summary.token_usage,
    )


@router.get("/{doc_id}/review-state")
def get_review_state(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    """
    Serve a collaborative-ready payload shape.

    Presence/comment streams can be added later without breaking this envelope.
    """
    # This endpoint intentionally denormalizes multiple tables into one UI-friendly shape.
    document = _require_document(db, doc_id, user.user_id)
    detections = list(
        db.scalars(
            select(Detection)
            .where(Detection.document_id == document.id, Detection.deleted_at.is_(None))
            .order_by(Detection.page_number)
        ).all()
    )
    redactions = list(
        db.scalars(
            select(ManualRedaction)
            .where(ManualRedaction.document_id == document.id, ManualRedaction.deleted_at.is_(None))
            .order_by(ManualRedaction.created_at)
        ).all()
    )
    return {
        "documentId": str(document.id),
        "status": document.status,
        "detections": [
            {
                "id": str(item.id),
                "entityType": item.entity_type,
                "pageNumber": item.page_number,
                "blockRef": item.block_ref,
                "bbox": item.bbox,
                "confidence": item.confidence,
                "accepted": item.accepted,
            }
            for item in detections
        ],
        "manualRedactions": [
            {
                "id": str(item.id),
                "kind": item.redaction_kind,
                "entityType": item.entity_type,
                "pageNumber": item.page_number,
                "bbox": item.bbox,
                "span": item.span,
                "status": item.status,
            }
            for item in redactions
        ],
        "activity": [],
    }


@router.get("/modes/schema")
def mode_schema() -> dict[str, Any]:
    """
    Return expected summary schema fields by document mode.

    Frontend can use this contract to render mode-specific summary sections.
    """
    return {
        "resume_anonymization": [
            "skills",
            "experienceSummary",
            "yearsExperience",
            "citations",
            "confidence",
        ],
        "employment_paperwork_review": [
            "compensation",
            "deadlines",
            "restrictions",
            "risks",
            "citations",
            "confidence",
        ],
        "medical_paperwork_safe_sharing": [
            "instructions",
            "followUps",
            "billing",
            "importantDates",
            "citations",
            "confidence",
        ],
        "legal_contract_review": [
            "obligations",
            "fees",
            "penalties",
            "termination",
            "renewal",
            "riskyClauses",
            "citations",
            "confidence",
        ],
        "terms_and_conditions_summarization": [
            "cancellation",
            "refunds",
            "autoRenewal",
            "dataUse",
            "liability",
            "citations",
            "confidence",
        ],
    }
