"""Export stage for R5: review state + original PDF → verified redacted PDF in the downloads bucket.

This is the I/O shell around `redaction`. One run handles one `exports` row:

1. Load the row and its document. A row already EXPORTED or FAILED is left alone,
   so a duplicate or late Celery delivery cannot overwrite a finished result.
2. Read the selection at run time: accepted detections and active drawn boxes.
3. Download the original PDF and the OCR JSON from the originals bucket.
4. Redact, then verify the output bytes. A failed check raises, so nothing is uploaded.
5. Upload to `exports.s3_key` in the downloads bucket, then mark the row EXPORTED.
   Upload comes first: a crash between the two leaves a retry that overwrites
   the same key, never a row pointing at a missing file.

Do not log OCR text, probe values, or PDF content. Counts and ids only.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text

from services.worker.app.config import AWS_REGION, S3_BUCKET_DOWNLOADS, S3_BUCKET_ORIGINALS
from services.worker.app.db import engine
from services.worker.app.notify import notify
from services.worker.app.ocr import S3Client
from services.worker.app.redaction import (
    ExportError,
    build_probes,
    build_targets,
    redact_pdf,
    verify_export,
)

logger = logging.getLogger(__name__)

EXPORT_FINISHED = {"EXPORTED", "FAILED"}
_MISSING_CODES = {"NoSuchKey", "404", "NotFound"}


def _default_s3() -> S3Client:
    return boto3.client("s3", region_name=AWS_REGION)


def _load_export(document_id: str, export_id: str | None) -> Mapping[str, Any] | None:
    """The export row plus the document fields this stage needs.

    `export_id` is None only for messages queued before R5; they take the newest row.
    """
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT e.id AS export_id, e.status, e.s3_key AS export_key, e.options,
                       e.deleted_at AS export_deleted_at,
                       d.id AS document_id, d.user_id, d.filename, d.s3_key_original, d.s3_key AS original_key,
                       d.ocr_s3_key, d.deleted_at AS document_deleted_at
                FROM exports e
                JOIN documents d ON d.id = e.document_id
                WHERE e.document_id = CAST(:document_id AS UUID)
                  AND (CAST(:export_id AS UUID) IS NULL OR e.id = CAST(:export_id AS UUID))
                ORDER BY e.created_at DESC
                LIMIT 1
                """
            ),
            {"document_id": document_id, "export_id": export_id},
        ).mappings().first()


def _load_selection(document_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Accepted detections and active drawn boxes, as the reviewer left them."""
    with engine.begin() as conn:
        detections = conn.execute(
            text(
                """
                SELECT entity_type, page_number, rects, bbox, char_start, char_end
                FROM detections
                WHERE document_id = CAST(:document_id AS UUID)
                  AND deleted_at IS NULL
                  AND accepted = TRUE
                ORDER BY page_number, char_start
                """
            ),
            {"document_id": document_id},
        ).mappings().all()
        manual = conn.execute(
            text(
                """
                SELECT entity_type, page_number, bbox
                FROM manual_redactions
                WHERE document_id = CAST(:document_id AS UUID)
                  AND deleted_at IS NULL
                  AND status = CAST('ACTIVE' AS VARCHAR)
                ORDER BY page_number, created_at
                """
            ),
            {"document_id": document_id},
        ).mappings().all()
    return [dict(row) for row in detections], [dict(row) for row in manual]


def _storage_error(exc: Exception, *, missing: ExportError) -> ExportError:
    if isinstance(exc, ClientError) and (exc.response.get("Error", {}).get("Code") or "") in _MISSING_CODES:
        return missing
    return ExportError("STORAGE_ERROR", "Storage was unavailable. The export will be retried.", retryable=True)


def _download_original(s3: S3Client, key: str) -> bytes:
    missing = ExportError("ORIGINAL_MISSING", "The original file is no longer in storage.", retryable=False)
    if not key:
        raise missing
    try:
        return s3.get_object(Bucket=S3_BUCKET_ORIGINALS, Key=key)["Body"].read()
    except (ClientError, BotoCoreError) as exc:
        raise _storage_error(exc, missing=missing) from exc


def _ocr_missing() -> ExportError:
    return ExportError(
        "OCR_MISSING",
        "The extracted text is needed to check the export but was not found. Reprocess the document, then export again.",
        retryable=False,
    )


def _download_ocr(s3: S3Client, key: str) -> dict[str, Any]:
    try:
        payload = json.loads(s3.get_object(Bucket=S3_BUCKET_ORIGINALS, Key=key)["Body"].read())
    except (ClientError, BotoCoreError) as exc:
        raise _storage_error(exc, missing=_ocr_missing()) from exc
    except ValueError as exc:
        raise _ocr_missing() from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        raise _ocr_missing()
    return payload


def _upload(s3: S3Client, key: str, body: bytes) -> None:
    try:
        s3.put_object(Bucket=S3_BUCKET_DOWNLOADS, Key=key, Body=body, ContentType="application/pdf")
    except (ClientError, BotoCoreError) as exc:
        raise ExportError("STORAGE_ERROR", "Storage was unavailable. The export will be retried.", retryable=True) from exc


def _audit(conn, *, user_id: str, document_id: str, event_type: str, payload: dict[str, Any]) -> None:
    conn.execute(
        text(
            """
            INSERT INTO audit_logs (id, user_id, document_id, event_type, payload, created_at)
            VALUES (CAST(:id AS UUID), CAST(:user_id AS VARCHAR), CAST(:document_id AS UUID),
                    CAST(:event_type AS VARCHAR), CAST(:payload AS JSONB), CAST(:now AS TIMESTAMP))
            """
        ),
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "document_id": document_id,
            "event_type": event_type,
            "payload": json.dumps(payload),
            "now": datetime.utcnow(),
        },
    )


def _mark_processing(export_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE exports
                SET status = CAST('PROCESSING' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:export_id AS UUID)
                """
            ),
            {"export_id": export_id, "now": datetime.utcnow()},
        )


def _mark_exported(row: Mapping[str, Any], result: dict[str, Any]) -> None:
    """Row, document status, and audit event in one transaction."""
    now = datetime.utcnow()
    export_id, document_id = str(row["export_id"]), str(row["document_id"])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE exports
                SET status = CAST('EXPORTED' AS VARCHAR),
                    page_count = CAST(:page_count AS INTEGER),
                    redaction_count = CAST(:redaction_count AS INTEGER),
                    size_bytes = CAST(:size_bytes AS BIGINT),
                    verification = CAST(:verification AS JSONB),
                    error_code = NULL,
                    error_message = NULL,
                    completed_at = CAST(:now AS TIMESTAMP),
                    updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:export_id AS UUID)
                """
            ),
            {
                "export_id": export_id,
                "page_count": result["pageCount"],
                "redaction_count": result["boxes"],
                "size_bytes": result["sizeBytes"],
                "verification": json.dumps(result["verification"]),
                "now": now,
            },
        )
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('EXPORTED' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID) AND deleted_at IS NULL
                """
            ),
            {"document_id": document_id, "now": now},
        )
        _audit(
            conn,
            user_id=row["user_id"],
            document_id=document_id,
            event_type="document.export.completed",
            payload={"documentId": document_id, "exportId": export_id, "boxes": result["boxes"]},
        )
    notify(row["user_id"], str(row["document_id"]), "document.exported", f"{row['filename']} export is ready")


def mark_export_failed(document_id: str, export_id: str | None, code: str, message: str) -> None:
    """Record a terminal failure. `message` must not contain document text.

    The document returns to READY_FOR_REVIEW only if this export had put it in
    EXPORT_QUEUED, so a failed re-export never hides an earlier good one and
    never blocks review the way a document-level FAILED would.
    """
    row = _load_export(document_id, export_id)
    if not row:
        return
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE exports
                SET status = CAST('FAILED' AS VARCHAR),
                    error_code = CAST(:code AS VARCHAR),
                    error_message = CAST(:message AS TEXT),
                    completed_at = CAST(:now AS TIMESTAMP),
                    updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:export_id AS UUID)
                """
            ),
            {"export_id": str(row["export_id"]), "code": code, "message": message[:500], "now": now},
        )
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('READY_FOR_REVIEW' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID) AND status = CAST('EXPORT_QUEUED' AS VARCHAR)
                """
            ),
            {"document_id": str(row["document_id"]), "now": now},
        )
        _audit(
            conn,
            user_id=row["user_id"],
            document_id=str(row["document_id"]),
            event_type="document.export.failed",
            payload={"documentId": str(row["document_id"]), "exportId": str(row["export_id"]), "code": code},
        )
    notify(row["user_id"], str(row["document_id"]), "document.export_failed", f"{row['filename']} export failed")


def run_export(document_id: str, export_id: str | None = None, *, s3_client: S3Client | None = None) -> dict[str, Any]:
    """Build, verify, and store one export. Returns counts for the job row.

    Raises `ExportError` with a user-safe message; the task decides retry vs. failure.
    """
    row = _load_export(document_id, export_id)
    if not row or row["export_deleted_at"] is not None:
        raise ExportError("MISSING_EXPORT", "This export no longer exists.", retryable=False)
    if row["document_deleted_at"] is not None:
        raise ExportError("MISSING_DOCUMENT", "Document is no longer available.", retryable=False)
    if row["status"] in EXPORT_FINISHED:
        logger.info("export skipped export_id=%s status=%s", row["export_id"], row["status"])
        return {"ok": True, "skipped": True, "status": row["status"]}

    export_key = str(row["export_key"])
    _mark_processing(str(row["export_id"]))
    options = row["options"] or {}
    include_labels = bool(options.get("includeLabels", False))

    detections, manual = _load_selection(document_id)
    boxes = build_targets(detections, manual)

    s3 = s3_client or _default_s3()
    original = _download_original(s3, row["s3_key_original"] or row["original_key"])
    ocr_payload = None
    if boxes:
        # Fail closed: without the OCR text the text half of the verification cannot run.
        if not row["ocr_s3_key"]:
            raise _ocr_missing()
        ocr_payload = _download_ocr(s3, row["ocr_s3_key"])
    probes, probes_skipped = build_probes(ocr_payload, detections, manual, boxes)

    redacted = redact_pdf(original, boxes, include_labels=include_labels)
    report = verify_export(redacted, boxes, probes, probes_skipped=probes_skipped)

    _upload(s3, export_key, redacted.final)
    result = {
        "ok": True,
        "skipped": False,
        "exportId": str(row["export_id"]),
        "pageCount": redacted.page_count,
        "boxes": redacted.boxes_applied,
        "detections": len(detections),
        "manualRedactions": len(manual),
        "labelsDrawn": redacted.labels_drawn,
        "sizeBytes": len(redacted.final),
        "verification": report.as_dict(),
    }
    _mark_exported(row, result)
    logger.info(
        "export stored export_id=%s pages=%s boxes=%s probes=%s",
        row["export_id"],
        redacted.page_count,
        redacted.boxes_applied,
        report.probes_checked,
    )
    return result
