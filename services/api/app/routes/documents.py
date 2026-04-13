import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.celery_client import celery_client
from services.api.app.db import get_db
from services.api.app.enums import DocumentStatus
from services.api.app.models import Detection, Document, ExportArtifact, ManualRedaction, Summary
from services.api.app.schemas import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DetectionOut,
    DocumentOut,
    ExportOut,
    ExportRequest,
    ManualRedactionUpsert,
    SummaryOut,
    SummaryRequest,
)
from services.api.app.services.audit import log_event
from services.api.app.services.s3 import make_originals_key, presign_download, presign_put

router = APIRouter(prefix="/v1/documents", tags=["documents"])


def _require_document(db: Session, doc_id: str, user_id: str) -> Document:
    statement = select(Document).where(Document.id == uuid.UUID(doc_id), Document.user_id == user_id)
    document = db.scalar(statement)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.post("", response_model=CreateDocumentResponse)
def create_document(payload: CreateDocumentRequest, db: Session = Depends(get_db), user=CurrentUser):
    if payload.contentType != "application/pdf":
        raise HTTPException(status_code=400, detail="only pdf uploads are supported in v1")

    s3_key = make_originals_key(user.user_id, payload.filename)
    presigned_put = presign_put(s3_key, payload.contentType)
    record = Document(
        user_id=user.user_id,
        filename=payload.filename,
        content_type=payload.contentType,
        mode=payload.mode.value,
        safe_mode=payload.safeMode,
        s3_key=s3_key,
        status=DocumentStatus.CREATED.value,
    )
    db.add(record)
    db.flush()
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
    statement = (
        select(Document)
        .where(Document.user_id == user.user_id)
        .order_by(desc(Document.created_at))
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement).all())


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    return _require_document(db, doc_id, user.user_id)


@router.post("/{doc_id}/ingestDone")
def ingest_done(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    document = _require_document(db, doc_id, user.user_id)
    document.status = DocumentStatus.UPLOADED.value
    celery_client.send_task("detect_job", args=[str(document.id), user.user_id])
    document.status = DocumentStatus.DETECT_QUEUED.value
    log_event(
        db,
        user_id=user.user_id,
        event_type="document.detect.queued",
        payload={"documentId": str(document.id)},
        document_id=document.id,
    )
    db.commit()
    return {"id": str(document.id), "status": document.status}


@router.get("/{doc_id}/detections", response_model=list[DetectionOut])
def list_detections(doc_id: str, db: Session = Depends(get_db), user=CurrentUser):
    document = _require_document(db, doc_id, user.user_id)
    statement = select(Detection).where(Detection.document_id == document.id).order_by(Detection.page_number)
    return list(db.scalars(statement).all())


@router.post("/{doc_id}/redactions")
def upsert_manual_redaction(
    doc_id: str,
    payload: ManualRedactionUpsert,
    db: Session = Depends(get_db),
    user=CurrentUser,
):
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
    document = _require_document(db, doc_id, user.user_id)
    if document.status == DocumentStatus.EXPORTED.value and not payload.forceRegenerate:
        existing = db.scalar(
            select(ExportArtifact).where(ExportArtifact.document_id == document.id).order_by(desc(ExportArtifact.created_at))
        )
        if existing:
            return ExportOut(id=existing.id, status=existing.status, downloadUrl=presign_download(existing.s3_key))

    artifact = ExportArtifact(document_id=document.id, s3_key=f"exports/{user.user_id}/{document.id}.pdf")
    db.add(artifact)
    document.status = DocumentStatus.EXPORT_QUEUED.value
    celery_client.send_task("export_job", args=[str(document.id), user.user_id])
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
    document = _require_document(db, doc_id, user.user_id)
    summary = Summary(document_id=document.id, mode=document.mode, status="QUEUED")
    db.add(summary)
    document.status = DocumentStatus.SUMMARY_QUEUED.value
    celery_client.send_task("summary_job", args=[str(document.id), user.user_id, payload.includeMarkdown])
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
    document = _require_document(db, doc_id, user.user_id)
    detections = list(
        db.scalars(select(Detection).where(Detection.document_id == document.id).order_by(Detection.page_number)).all()
    )
    redactions = list(
        db.scalars(
            select(ManualRedaction).where(ManualRedaction.document_id == document.id).order_by(ManualRedaction.created_at)
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
