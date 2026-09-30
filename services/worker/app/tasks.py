"""
Background job implementations for detection, export, and summary workflows.

M3: each enqueue creates a `jobs` row; `_update_job_status` moves the *latest*
row for a `(document_id, job_type)` through PROCESSING / COMPLETED / FAILED so
the dashboard and ops can see pipeline state without reading Celery only.

Stubs: detection/export/summary still use placeholder logic; they exist to
exercise status transitions, DB writes, and failure/retry behavior end-to-end.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import create_engine, text

from services.worker.app.celery_app import celery
from services.worker.app.config import DATABASE_URL
from services.worker.app.redaction import redact_pdf_bytes
from services.worker.app.summary import build_summary_payload

# Raw SQL engine used by worker jobs to update lifecycle state.
# `pool_pre_ping=True` helps recover stale DB connections in long-lived workers.
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)

# Placeholder entity matchers for synthetic detection output.
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return UTC timestamp in ISO format for task response metadata."""
    return datetime.utcnow().isoformat() + "Z"


_DETECT_DONE_STATUSES = {
    "DETECTED",
    "EXPORT_QUEUED",
    "EXPORTED",
    "SUMMARY_QUEUED",
    "SUMMARIZED",
}


def _insert_detection(document_id: str, entity_type: str, value: str, confidence: float) -> None:
    """
    Insert one detection row.

    Uses SQL text for explicit control over JSONB casting and to keep worker
    dependencies light (no ORM session lifecycle here).
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO detections
                (id, document_id, entity_type, detected_text, page_number, block_ref, confidence, bbox, source, accepted, created_at)
                VALUES
                (
                  CAST(:id AS UUID),
                  CAST(:document_id AS UUID),
                  CAST(:entity_type AS VARCHAR),
                  CAST(:detected_text AS TEXT),
                  CAST(:page_number AS INTEGER),
                  CAST(:block_ref AS VARCHAR),
                  CAST(:confidence AS DOUBLE PRECISION),
                  CAST(:bbox AS JSONB),
                  CAST(:source AS VARCHAR),
                  CAST(:accepted AS BOOLEAN),
                  CAST(:created_at AS TIMESTAMP)
                )
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
    """Persist document lifecycle status transition."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET status=CAST(:status AS VARCHAR),
                    updated_at=CAST(:updated_at AS TIMESTAMP)
                WHERE id=CAST(:document_id AS UUID)
                """
            ),
            {"status": status, "updated_at": datetime.utcnow(), "document_id": document_id},
        )


def _latest_document_row(document_id: str):
    """Fetch minimal document fields needed by worker tasks."""
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT id, mode, safe_mode, filename, status, deleted_at
                FROM documents
                WHERE id=CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).mappings().first()


def _update_job_status(document_id: str, job_type: str, status: str, error: str | None = None, result: dict | None = None) -> None:
    """
    Advance the latest non-deleted job for this document and type.

    Matches how the API inserts jobs at enqueue time. RLS in Supabase blocks
    `anon` / `authenticated`; the worker must connect with a service role (or
    other bypass) in deployed environments, same as the API backend.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE jobs
                SET status=CAST(:status AS VARCHAR),
                    started_at=CASE
                      WHEN CAST(:status AS VARCHAR)='PROCESSING' THEN COALESCE(started_at, CAST(:now AS TIMESTAMP))
                      ELSE started_at
                    END,
                    finished_at=CASE
                      WHEN CAST(:status AS VARCHAR) IN ('COMPLETED', 'FAILED') THEN CAST(:now AS TIMESTAMP)
                      ELSE finished_at
                    END,
                    updated_at=CAST(:now AS TIMESTAMP),
                    attempt_count=CASE
                      WHEN CAST(:status AS VARCHAR)='PROCESSING' THEN attempt_count + 1
                      ELSE attempt_count
                    END,
                    last_error=CAST(:last_error AS TEXT),
                    result=COALESCE(CAST(:result AS JSONB), result)
                WHERE id=(
                  SELECT id FROM jobs
                  WHERE document_id=CAST(:document_id AS UUID)
                    AND job_type=CAST(:job_type AS VARCHAR)
                    AND deleted_at IS NULL
                  ORDER BY created_at DESC
                  LIMIT 1
                )
                """
            ),
            {
                "status": status,
                "now": datetime.utcnow(),
                "document_id": document_id,
                "job_type": job_type,
                "last_error": error,
                "result": json.dumps(result) if result is not None else None,
            },
        )


@celery.task(name="detect_job", bind=True, max_retries=3)
def detect_job(self, document_id: str, user_id: str) -> dict:
    """
    M3 detection task stub with custom rules.

    Real Textract + Comprehend integration will replace this placeholder logic.
    """
    try:
        _update_job_status(document_id, "detect", "PROCESSING")
        # Guard against stale/missing document references.
        row = _latest_document_row(document_id)
        if not row or row["deleted_at"] is not None:
            logger.warning("detect_job missing document_id=%s", document_id)
            return {"ok": False, "error": "missing document"}
        if row["status"] in _DETECT_DONE_STATUSES:
            _update_job_status(document_id, "detect", "COMPLETED", result={"ok": True, "skipped": True})
            logger.info("detect_job skipped document_id=%s status=%s", document_id, row["status"])
            return {"ok": True, "document_id": document_id, "skipped": True}

        # Synthetic sample text lets us exercise regex + DB insertion behavior.
        sample_text = f"Contact {user_id}@example.com or 212-555-0199 for {row['filename']}."
        for match in EMAIL_RE.finditer(sample_text):
            _insert_detection(document_id, "EMAIL", match.group(0), 0.91)
        for match in PHONE_RE.finditer(sample_text):
            _insert_detection(document_id, "PHONE", match.group(0), 0.87)

        # Mark machine detection complete.
        _update_document_status(document_id, "DETECTED")
        _update_job_status(document_id, "detect", "COMPLETED", result={"ok": True})
        logger.info("detect_job completed document_id=%s", document_id)
        return {"ok": True, "document_id": document_id, "finished_at": _now_iso()}
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            countdown = min(60, 5 * (2 ** self.request.retries))
            logger.warning(
                "detect_job retry document_id=%s attempt=%s error=%s",
                document_id,
                self.request.retries + 1,
                exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)
        _update_document_status(document_id, "FAILED")
        _update_job_status(document_id, "detect", "FAILED", error=f"{exc.__class__.__name__}: {exc}")
        logger.exception("detect_job failed document_id=%s", document_id)
        return {"ok": False, "document_id": document_id, "error": "detect_job failed"}


@celery.task(name="export_job", bind=True, max_retries=3)
def export_job(self, document_id: str, user_id: str) -> dict:
    """
    M5 export task stub.

    Current implementation exercises true-redaction library path by rewriting
    synthetic bytes. Real implementation should fetch source PDF and apply
    review-approved coordinates.
    """
    try:
        _update_job_status(document_id, "export", "PROCESSING")
        row = _latest_document_row(document_id)
        if not row or row["deleted_at"] is not None:
            logger.warning("export_job missing document_id=%s", document_id)
            return {"ok": False, "error": "missing document"}
        if row["status"] == "EXPORTED":
            _update_job_status(document_id, "export", "COMPLETED", result={"ok": True, "skipped": True})
            logger.info("export_job skipped document_id=%s", document_id)
            return {"ok": True, "document_id": document_id, "skipped": True}

        # Placeholder PDF content to validate redaction pipeline execution path.
        fake_pdf = b"%PDF-1.4\n% redactldr placeholder\n"
        redacted = redact_pdf_bytes(fake_pdf, [{"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.04}])
        export_key = f"exports/{user_id}/{document_id}.pdf"
        with engine.begin() as conn:
            # Update the newest export row for this document as completed.
            conn.execute(
                text(
                    """
                    UPDATE exports
                    SET status=CAST('EXPORTED' AS VARCHAR),
                        s3_key=CAST(:s3_key AS VARCHAR)
                    WHERE id=(
                      SELECT id FROM exports
                      WHERE document_id=CAST(:document_id AS UUID)
                      ORDER BY created_at DESC
                      LIMIT 1
                    )
                    """
                ),
                {"s3_key": export_key, "document_id": document_id},
            )
        # Reflect completion on parent document lifecycle state.
        _update_document_status(document_id, "EXPORTED")
        _update_job_status(document_id, "export", "COMPLETED", result={"ok": True, "s3Key": export_key})
        logger.info("export_job completed document_id=%s", document_id)
        return {"ok": True, "document_id": document_id, "bytes": len(redacted), "s3_key": export_key}
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            countdown = min(60, 5 * (2 ** self.request.retries))
            logger.warning(
                "export_job retry document_id=%s attempt=%s error=%s",
                document_id,
                self.request.retries + 1,
                exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)
        _update_document_status(document_id, "FAILED")
        _update_job_status(document_id, "export", "FAILED", error="export_job failed")
        logger.exception("export_job failed document_id=%s", document_id)
        return {"ok": False, "document_id": document_id, "error": "export_job failed"}


@celery.task(name="summary_job", bind=True, max_retries=3)
def summary_job(self, document_id: str, user_id: str, include_markdown: bool = True) -> dict:
    """
    M6 summary task stub.

    This task builds schema-conformant payloads and stores citations/confidence.
    """
    try:
        _update_job_status(document_id, "summary", "PROCESSING")
        # Fetch mode/safe-mode because summary shape depends on these values.
        row = _latest_document_row(document_id)
        if not row or row["deleted_at"] is not None:
            logger.warning("summary_job missing document_id=%s", document_id)
            return {"ok": False, "error": "missing document"}
        if row["status"] == "SUMMARIZED":
            _update_job_status(document_id, "summary", "COMPLETED", result={"ok": True, "skipped": True})
            logger.info("summary_job skipped document_id=%s", document_id)
            return {"ok": True, "document_id": document_id, "skipped": True}

        # Summary helper returns mode-aware payload skeleton.
        summary = build_summary_payload(mode=row["mode"], safe_mode=bool(row["safe_mode"]))
        markdown = (
            f"## Summary\n\nSafe mode: `{summary['safeMode']}`.\n\n"
            f"- Document mode: `{summary['mode']}`\n"
            f"- Findings are placeholder data pending Bedrock integration."
            if include_markdown
            else ""
        )

        with engine.begin() as conn:
            # Store both machine JSON and optional markdown representation.
            conn.execute(
                text(
                    """
                    UPDATE summaries
                    SET status=CAST('SUMMARIZED' AS VARCHAR),
                        json_payload=CAST(:json_payload AS JSONB),
                        markdown=CAST(:markdown AS TEXT),
                        token_usage=CAST(:token_usage AS JSONB)
                    WHERE id=(
                      SELECT id FROM summaries
                      WHERE document_id=CAST(:document_id AS UUID)
                      ORDER BY created_at DESC
                      LIMIT 1
                    )
                    """
                ),
                {
                    "document_id": document_id,
                    "json_payload": json.dumps(summary["json"]),
                    "markdown": markdown,
                    "token_usage": json.dumps({"inputTokens": 0, "outputTokens": 0, "model": "placeholder"}),
                },
            )
        # Mark parent document summarized once latest summary row is updated.
        _update_document_status(document_id, "SUMMARIZED")
        _update_job_status(document_id, "summary", "COMPLETED", result={"ok": True})
        logger.info("summary_job completed document_id=%s", document_id)
        return {"ok": True, "document_id": document_id, "summary_id": str(UUID(summary["summaryId"]))}
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            countdown = min(60, 5 * (2 ** self.request.retries))
            logger.warning(
                "summary_job retry document_id=%s attempt=%s error=%s",
                document_id,
                self.request.retries + 1,
                exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=countdown)
        _update_document_status(document_id, "FAILED")
        _update_job_status(document_id, "summary", "FAILED", error="summary_job failed")
        logger.exception("summary_job failed document_id=%s", document_id)
        return {"ok": False, "document_id": document_id, "error": "summary_job failed"}


@celery.task(name="cleanup_stale_uploads")
def cleanup_stale_uploads(older_than_hours: int = 24) -> dict:
    """Soft-delete documents left in CREATED longer than the upload window."""
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                UPDATE documents
                SET deleted_at=CAST(:now AS TIMESTAMP),
                    updated_at=CAST(:now AS TIMESTAMP)
                WHERE status=CAST(:status AS VARCHAR)
                  AND deleted_at IS NULL
                  AND created_at < CAST(:cutoff AS TIMESTAMP)
                RETURNING id
                """
            ),
            {
                "now": datetime.utcnow(),
                "status": "CREATED",
                "cutoff": cutoff,
            },
        ).all()
    deleted = len(rows)
    logger.info("cleanup_stale_uploads soft_deleted=%s", deleted)
    return {"ok": True, "softDeleted": deleted}
