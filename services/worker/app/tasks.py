"""
Background job implementations for detection, export, and summary workflows.

M3: each enqueue creates a `jobs` row; `_update_job_status` moves the *latest*
row for a `(document_id, job_type)` through PROCESSING / COMPLETED / FAILED so
the dashboard and ops can see pipeline state without reading Celery only.

OCR (R2) reads the real PDF through Textract. Detection (R3) runs Comprehend
and custom rules on that OCR text and applies the mode policy. Export (R5)
removes the selected content and verifies the file before upload. Summary (R6)
sends the OCR text, with accepted values tokenized when safe mode is on, and
stores the structured result only after a leak check.
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from services.shared.log_json import bind_log_context
from services.worker.app.celery_app import celery
from services.worker.app.db import engine
from services.worker.app.detect import run_detection_for_document
from services.worker.app.metrics import stage_timer
from services.worker.app.detection.models import DetectionError
from services.worker.app.export import mark_export_failed, run_export
from services.worker.app.notify import notify
from services.worker.app.ocr import OcrError, run_ocr_for_document
from services.worker.app.redaction import ExportError
from services.worker.app.summary import SummaryError, mark_summary_failed, run_summary

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return UTC timestamp in ISO format for task response metadata."""
    return datetime.utcnow().isoformat() + "Z"


# Statuses that mean the pipeline has already finished OCR + detect.
# DETECTED is the pre-R2 name; the migration rewrites it to READY_FOR_REVIEW.
_PIPELINE_DONE_STATUSES = {
    "READY_FOR_REVIEW",
    "DETECTED",
    "EXPORT_QUEUED",
    "EXPORTED",
    "SUMMARY_QUEUED",
    "SUMMARIZED",
}


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
    """Fetch the document fields worker tasks branch on. No OCR text is selected."""
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT id, user_id, mode, safe_mode, filename, status, deleted_at, ocr_s3_key, processing_stage
                FROM documents
                WHERE id=CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).mappings().first()


def _update_document_progress(
    document_id: str,
    status: str,
    *,
    stage: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Set lifecycle status, the active stage, and a user-safe error pair."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET status=CAST(:status AS VARCHAR),
                    processing_stage=CAST(:stage AS VARCHAR),
                    error_code=CAST(:error_code AS VARCHAR),
                    error_message=CAST(:error_message AS TEXT),
                    updated_at=CAST(:updated_at AS TIMESTAMP)
                WHERE id=CAST(:document_id AS UUID)
                """
            ),
            {
                "status": status,
                "stage": stage,
                "error_code": error_code,
                "error_message": error_message,
                "updated_at": datetime.utcnow(),
                "document_id": document_id,
            },
        )


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


def _fail_process(document_id: str, code: str, message: str, *, stage: str | None, job_type: str = "process") -> dict:
    """Record a terminal pipeline failure. `message` must not contain document text.

    `stage` stays set so the document page can mark the step that stopped.
    """
    safe = message[:500]
    _update_document_progress(document_id, "FAILED", stage=stage, error_code=code, error_message=safe)
    _update_job_status(document_id, job_type, "FAILED", error=f"{code}: {safe}")
    logger.error("pipeline failed document_id=%s job_type=%s code=%s stage=%s", document_id, job_type, code, stage)
    failed = _latest_document_row(document_id)
    if failed:
        notify(failed["user_id"], document_id, "document.failed", f"{failed['filename']} could not be processed")
    return {"ok": False, "document_id": document_id, "error": code}


def _safe_error_text(exc: Exception) -> str:
    """Error text for the UI and job row.

    SQLAlchemy messages echo bound parameters, which can include detection
    values, so only the driver error class is kept for those.
    """
    if isinstance(exc, SQLAlchemyError):
        original = getattr(exc, "orig", None)
        return f"{exc.__class__.__name__}: {(original or exc).__class__.__name__}"
    return f"{exc.__class__.__name__}: {exc}"


def _retry_countdown(retries: int) -> int:
    return min(60, 5 * (2 ** retries))


def _run_stages(document_id: str, row) -> dict:
    """OCR (skipped when its JSON is stored), then detection, then READY_FOR_REVIEW.

    Returns the detection counts for the job row.
    """
    if row["ocr_s3_key"]:
        logger.info("pipeline ocr already stored document_id=%s", document_id)
    else:
        _update_document_progress(document_id, "PROCESSING", stage="ocr")
        with stage_timer("ocr"):
            run_ocr_for_document(document_id)

    _update_document_progress(document_id, "PROCESSING", stage="detect")
    with stage_timer("detect"):
        detections = run_detection_for_document(document_id)
    _update_document_progress(document_id, "READY_FOR_REVIEW", stage=None)
    return detections


def _run_pipeline_task(task, document_id: str, job_type: str) -> dict:
    """Shared body of `process_document` and the legacy `detect_job`.

    Typed stage errors carry a user-safe message and a retryable flag. Anything
    else is retried as a transient failure, then recorded with its class name.
    """
    task_name = task.name
    try:
        _update_job_status(document_id, job_type, "PROCESSING")
        row = _latest_document_row(document_id)
        if not row or row["deleted_at"] is not None:
            logger.warning("%s missing document_id=%s", task_name, document_id)
            return {"ok": False, "error": "missing document"}
        if row["status"] in _PIPELINE_DONE_STATUSES:
            _update_job_status(document_id, job_type, "COMPLETED", result={"ok": True, "skipped": True})
            logger.info("%s skipped document_id=%s status=%s", task_name, document_id, row["status"])
            return {"ok": True, "document_id": document_id, "skipped": True}

        detections = _run_stages(document_id, row)
        _update_job_status(document_id, job_type, "COMPLETED", result={"ok": True, "detections": detections})
        logger.info("%s completed document_id=%s", task_name, document_id)
        notify(row["user_id"], document_id, "document.ready", f"{row['filename']} is ready for review")
        return {"ok": True, "document_id": document_id, "finished_at": _now_iso()}
    except (OcrError, DetectionError) as exc:
        stage = "ocr" if isinstance(exc, OcrError) else "detect"
        if exc.retryable and task.request.retries < task.max_retries:
            logger.warning(
                "%s retry document_id=%s code=%s stage=%s attempt=%s",
                task_name,
                document_id,
                exc.code,
                stage,
                task.request.retries + 1,
            )
            raise task.retry(exc=exc, countdown=_retry_countdown(task.request.retries))
        return _fail_process(document_id, exc.code, exc.message, stage=stage, job_type=job_type)
    except Exception as exc:  # noqa: BLE001
        if task.request.retries < task.max_retries:
            logger.warning(
                "%s retry document_id=%s attempt=%s error=%s",
                task_name,
                document_id,
                task.request.retries + 1,
                exc.__class__.__name__,
            )
            raise task.retry(exc=exc, countdown=_retry_countdown(task.request.retries))
        failed_stage = "detect"
        latest = _latest_document_row(document_id)
        if latest and latest["processing_stage"] == "ocr":
            failed_stage = "ocr"
        return _fail_process(document_id, "PROCESS_FAILED", _safe_error_text(exc), stage=failed_stage, job_type=job_type)


@celery.task(name="process_document", bind=True, max_retries=3)
def process_document(self, document_id: str, user_id: str) -> dict:
    """Run OCR, then detection with the mode policy, then mark the document ready.

    Each stage is skipped or replaced when its output is already stored. A retry
    after a Textract start resumes that job instead of starting a second one
    (`run_ocr_for_document`); detection replaces its rows (`replace_detections`).
    `user_id` stays in the signature because the API enqueues it.
    """
    with bind_log_context(document_id=document_id, job_id=self.request.id or ""):
        return _run_pipeline_task(self, document_id, "process")


@celery.task(name="detect_job", bind=True, max_retries=3)
def detect_job(self, document_id: str, user_id: str) -> dict:
    """Legacy queue entry from before R2.

    New uploads enqueue `process_document`. A message already on the broker
    runs the same pipeline and records progress on its `detect` job row.
    """
    with bind_log_context(document_id=document_id, job_id=self.request.id or ""):
        return _run_pipeline_task(self, document_id, "detect")


def _fail_export(document_id: str, export_id: str | None, code: str, message: str, *, job_error: str) -> dict:
    """Terminal export failure. The document stays reviewable; only the export row is FAILED."""
    mark_export_failed(document_id, export_id, code, message)
    _update_job_status(document_id, "export", "FAILED", error=job_error[:500])
    logger.error("export_job failed document_id=%s export_id=%s code=%s", document_id, export_id, code)
    return {"ok": False, "document_id": document_id, "export_id": export_id, "error": code}


@celery.task(name="export_job", bind=True, max_retries=3)
def export_job(self, document_id: str, user_id: str, export_id: str | None = None) -> dict:
    """Build the redacted PDF for one `exports` row (R5; see `services/worker/app/export.py`).

    `export_id` is optional so messages queued before R5 still run; they use
    the newest export row. `user_id` stays in the signature because the API
    enqueues it. Verification failures are not retried: the same input gives
    the same output.
    """
    with bind_log_context(document_id=document_id, job_id=self.request.id or ""):
        return _export_job(self, document_id, export_id)


def _export_job(self, document_id: str, export_id: str | None) -> dict:
    try:
        _update_job_status(document_id, "export", "PROCESSING")
        with stage_timer("export"):
            result = run_export(document_id, export_id)
        _update_job_status(document_id, "export", "COMPLETED", result=result)
        logger.info("export_job completed document_id=%s export_id=%s", document_id, export_id)
        return {"ok": True, "document_id": document_id, "export_id": export_id, "finished_at": _now_iso()}
    except ExportError as exc:
        if exc.retryable and self.request.retries < self.max_retries:
            logger.warning(
                "export_job retry document_id=%s code=%s attempt=%s", document_id, exc.code, self.request.retries + 1
            )
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        return _fail_export(document_id, export_id, exc.code, exc.message, job_error=f"{exc.code}: {exc.message}")
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            logger.warning(
                "export_job retry document_id=%s attempt=%s error=%s",
                document_id,
                self.request.retries + 1,
                exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        return _fail_export(
            document_id,
            export_id,
            "EXPORT_FAILED",
            "The export could not be built. You can try again.",
            job_error=_safe_error_text(exc),
        )


def _fail_summary(document_id: str, summary_id: str | None, code: str, message: str, *, job_error: str) -> dict:
    """Terminal summary failure. The document stays reviewable; only the summary row is FAILED."""
    mark_summary_failed(document_id, summary_id, code, message)
    _update_job_status(document_id, "summary", "FAILED", error=job_error[:500])
    logger.error("summary_job failed document_id=%s summary_id=%s code=%s", document_id, summary_id, code)
    return {"ok": False, "document_id": document_id, "summary_id": summary_id, "error": code}


@celery.task(name="summary_job", bind=True, max_retries=3)
def summary_job(self, document_id: str, user_id: str, include_markdown: bool = True, summary_id: str | None = None) -> dict:
    """Build one summary (R6; see `services/worker/app/summary/run.py`).

    `summary_id` is optional so messages queued before R6 still run; they use
    the newest summary row. A leak or a schema failure is not retried.
    """
    with bind_log_context(document_id=document_id, job_id=self.request.id or ""):
        return _summary_job(self, document_id, include_markdown, summary_id)


def _summary_job(self, document_id: str, include_markdown: bool, summary_id: str | None) -> dict:
    try:
        _update_job_status(document_id, "summary", "PROCESSING")
        with stage_timer("summary"):
            result = run_summary(document_id, summary_id, include_markdown=include_markdown)
        _update_job_status(document_id, "summary", "COMPLETED", result=result)
        logger.info("summary_job completed document_id=%s summary_id=%s", document_id, summary_id)
        return {"ok": True, "document_id": document_id, "summary_id": summary_id, "finished_at": _now_iso()}
    except SummaryError as exc:
        if exc.retryable and self.request.retries < self.max_retries:
            logger.warning(
                "summary_job retry document_id=%s code=%s attempt=%s", document_id, exc.code, self.request.retries + 1
            )
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        return _fail_summary(document_id, summary_id, exc.code, exc.message, job_error=f"{exc.code}: {exc.message}")
    except Exception as exc:  # noqa: BLE001
        if self.request.retries < self.max_retries:
            logger.warning(
                "summary_job retry document_id=%s attempt=%s error=%s",
                document_id,
                self.request.retries + 1,
                exc.__class__.__name__,
            )
            raise self.retry(exc=exc, countdown=_retry_countdown(self.request.retries))
        return _fail_summary(
            document_id,
            summary_id,
            "SUMMARY_FAILED",
            "The summary could not be built. You can try again.",
            job_error=_safe_error_text(exc),
        )


@celery.task(name="purge_user_data")
def purge_user_data(user_id: str) -> dict:
    """Hard-delete one user's files and rows. Queued by DELETE account."""
    from services.worker.app.retention import purge_user

    return purge_user(user_id)


@celery.task(name="apply_retention")
def apply_retention() -> dict:
    """Drop documents older than the owner's retention setting."""
    from services.worker.app.retention import apply_retention as _apply

    return _apply()


@celery.task(name="publish_queue_depth")
def publish_queue_depth() -> dict:
    """Queue length for worker autoscaling. No-op unless a CloudWatch namespace is set."""
    from services.worker.app.metrics import publish_queue_depth as _publish

    return _publish()


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
