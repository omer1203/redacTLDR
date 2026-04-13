import json
import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from services.worker.app.celery_app import celery
from services.worker.app.config import DATABASE_URL
from services.worker.app.redaction import redact_pdf_bytes
from services.worker.app.summary import build_summary_payload

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _insert_detection(document_id: str, entity_type: str, value: str, confidence: float) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO detections
                (id, document_id, entity_type, detected_text, page_number, block_ref, confidence, bbox, source, accepted, created_at)
                VALUES
                (:id, :document_id, :entity_type, :detected_text, :page_number, :block_ref, :confidence, CAST(:bbox AS JSONB), :source, :accepted, :created_at)
                """
            ),
            {
                "id": str(uuid4()),
                "document_id": document_id,
                "entity_type": entity_type,
                "detected_text": value,
                "page_number": 1,
                "block_ref": "block-1",
                "confidence": confidence,
                "bbox": json.dumps({"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.03}),
                "source": "custom_rule",
                "accepted": True,
                "created_at": datetime.utcnow(),
            },
        )


def _update_document_status(document_id: str, status: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE documents SET status=:status, updated_at=:updated_at WHERE id=:document_id"),
            {"status": status, "updated_at": datetime.utcnow(), "document_id": document_id},
        )


def _latest_document_row(document_id: str):
    with engine.begin() as conn:
        return conn.execute(
            text("SELECT id, mode, safe_mode, filename FROM documents WHERE id=:document_id"),
            {"document_id": document_id},
        ).mappings().first()


@celery.task(name="detect_job")
def detect_job(document_id: str, user_id: str) -> dict:
    """
    M3 detection task stub with custom rules.

    Real Textract + Comprehend integration will replace this placeholder logic.
    """
    row = _latest_document_row(document_id)
    if not row:
        return {"ok": False, "error": "missing document"}

    sample_text = f"Contact {user_id}@example.com or 212-555-0199 for {row['filename']}."
    for match in EMAIL_RE.finditer(sample_text):
        _insert_detection(document_id, "EMAIL", match.group(0), 0.91)
    for match in PHONE_RE.finditer(sample_text):
        _insert_detection(document_id, "PHONE", match.group(0), 0.87)

    _update_document_status(document_id, "DETECTED")
    return {"ok": True, "document_id": document_id, "finished_at": _now_iso()}


@celery.task(name="export_job")
def export_job(document_id: str, user_id: str) -> dict:
    """
    M5 export task stub.

    Current implementation exercises true-redaction library path by rewriting
    synthetic bytes. Real implementation should fetch source PDF and apply
    review-approved coordinates.
    """
    row = _latest_document_row(document_id)
    if not row:
        return {"ok": False, "error": "missing document"}

    fake_pdf = b"%PDF-1.4\n% redactldr placeholder\n"
    redacted = redact_pdf_bytes(fake_pdf, [{"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.04}])
    export_key = f"exports/{user_id}/{document_id}.pdf"
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE exports SET status='EXPORTED', s3_key=:s3_key WHERE document_id=:document_id"),
            {"s3_key": export_key, "document_id": document_id},
        )
    _update_document_status(document_id, "EXPORTED")
    return {"ok": True, "document_id": document_id, "bytes": len(redacted), "s3_key": export_key}


@celery.task(name="summary_job")
def summary_job(document_id: str, user_id: str, include_markdown: bool = True) -> dict:
    """
    M6 summary task stub.

    This task builds schema-conformant payloads and stores citations/confidence.
    """
    row = _latest_document_row(document_id)
    if not row:
        return {"ok": False, "error": "missing document"}

    summary = build_summary_payload(mode=row["mode"], safe_mode=bool(row["safe_mode"]))
    markdown = (
        f"## Summary\n\nSafe mode: `{summary['safeMode']}`.\n\n"
        f"- Document mode: `{summary['mode']}`\n"
        f"- Findings are placeholder data pending Bedrock integration."
        if include_markdown
        else ""
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE summaries
                SET status='SUMMARIZED',
                    json_payload=CAST(:json_payload AS JSONB),
                    markdown=:markdown,
                    token_usage=CAST(:token_usage AS JSONB)
                WHERE document_id=:document_id
                """
            ),
            {
                "document_id": document_id,
                "json_payload": json.dumps(summary["json"]),
                "markdown": markdown,
                "token_usage": json.dumps({"inputTokens": 0, "outputTokens": 0, "model": "placeholder"}),
            },
        )
    _update_document_status(document_id, "SUMMARIZED")
    return {"ok": True, "document_id": document_id, "summary_id": str(UUID(summary["summaryId"]))}
