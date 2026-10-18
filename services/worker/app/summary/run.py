"""Summary stage for R6: OCR text in, one `summaries` row updated.

One run handles one row:

1. A row already SUMMARIZED or FAILED is left alone, so a duplicate delivery
   cannot overwrite a finished result.
2. The text is built from the OCR JSON. Safe mode replaces accepted detections
   and active drawn boxes with tokens before anything is sent.
3. The model result is validated and checked for those removed values.
4. The row is marked SUMMARIZED and the document follows, in one transaction.
   A failure marks only the summary FAILED and returns the document to
   READY_FOR_REVIEW. It never marks the document FAILED.

Do not log page text, prompts, or model output. Counts and ids only.
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

from services.shared.policy import UnknownModeError, get_mode_policy
from services.worker.app.config import AWS_REGION, BEDROCK_MODEL_ID, S3_BUCKET_ORIGINALS, SUMMARY_MAX_PAGES
from services.worker.app.db import engine
from services.worker.app.notify import notify
from services.worker.app.ocr import S3Client
from services.worker.app.summary.engine import Summarizer, envelope, generate_summary
from services.worker.app.summary.errors import SummaryError
from services.worker.app.summary.markdown import render_markdown
from services.worker.app.summary.model import BedrockSummarizer
from services.worker.app.summary.source import build_source

logger = logging.getLogger(__name__)

SUMMARY_FINISHED = {"SUMMARIZED", "FAILED"}
_MISSING_CODES = {"NoSuchKey", "404", "NotFound"}


def _default_s3() -> S3Client:
    return boto3.client("s3", region_name=AWS_REGION)


def _load(document_id: str, summary_id: str | None) -> Mapping[str, Any] | None:
    """The summary row plus the document. `summary_id` None takes the newest row."""
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT s.id AS summary_id, s.status, s.deleted_at AS summary_deleted_at,
                       d.id AS document_id, d.user_id, d.filename, d.mode, d.safe_mode, d.ocr_s3_key,
                       d.deleted_at AS document_deleted_at
                FROM summaries s
                JOIN documents d ON d.id = s.document_id
                WHERE s.document_id = CAST(:document_id AS UUID)
                  AND (CAST(:summary_id AS UUID) IS NULL OR s.id = CAST(:summary_id AS UUID))
                ORDER BY s.created_at DESC
                LIMIT 1
                """
            ),
            {"document_id": document_id, "summary_id": summary_id},
        ).mappings().first()


def _load_selection(document_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with engine.begin() as conn:
        detections = conn.execute(
            text(
                """
                SELECT entity_type, page_number, rects, bbox, char_start, char_end
                FROM detections
                WHERE document_id = CAST(:document_id AS UUID)
                  AND deleted_at IS NULL AND accepted = TRUE
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
                  AND deleted_at IS NULL AND status = CAST('ACTIVE' AS VARCHAR)
                ORDER BY page_number, created_at
                """
            ),
            {"document_id": document_id},
        ).mappings().all()
    return [dict(row) for row in detections], [dict(row) for row in manual]


def _download_ocr(s3: S3Client, key: str) -> dict[str, Any]:
    missing = SummaryError(
        "OCR_MISSING",
        "The extracted text was not found, so the summary was not sent. Reprocess the document.",
        retryable=False,
    )
    if not key:
        raise missing
    try:
        payload = json.loads(s3.get_object(Bucket=S3_BUCKET_ORIGINALS, Key=key)["Body"].read())
    except (ClientError, BotoCoreError) as exc:
        code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else ""
        if code in _MISSING_CODES:
            raise missing from exc
        raise SummaryError("STORAGE_ERROR", "Storage was unavailable. The summary will be retried.", retryable=True) from exc
    except ValueError as exc:
        raise missing from exc
    if not isinstance(payload, dict):
        raise missing
    return payload


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


def _mark_processing(summary_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE summaries
                SET status = CAST('PROCESSING' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:summary_id AS UUID) AND status = CAST('QUEUED' AS VARCHAR)
                """
            ),
            {"summary_id": summary_id, "now": datetime.utcnow()},
        )


def _mark_done(
    row: Mapping[str, Any],
    *,
    payload: dict[str, Any],
    markdown: str,
    token_usage: dict[str, Any],
) -> None:
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE summaries
                SET status = CAST('SUMMARIZED' AS VARCHAR),
                    json_payload = CAST(:payload AS JSONB),
                    markdown = CAST(:markdown AS TEXT),
                    token_usage = CAST(:token_usage AS JSONB),
                    error_code = NULL,
                    error_message = NULL,
                    completed_at = CAST(:now AS TIMESTAMP),
                    updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:summary_id AS UUID)
                """
            ),
            {
                "summary_id": str(row["summary_id"]),
                "payload": json.dumps(payload),
                "markdown": markdown,
                "token_usage": json.dumps(token_usage),
                "now": now,
            },
        )
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('SUMMARIZED' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID) AND deleted_at IS NULL
                """
            ),
            {"document_id": str(row["document_id"]), "now": now},
        )
        _audit(
            conn,
            user_id=row["user_id"],
            document_id=str(row["document_id"]),
            event_type="document.summary.completed",
            payload={
                "documentId": str(row["document_id"]),
                "summaryId": str(row["summary_id"]),
                "safeMode": bool(row["safe_mode"]),
                "calls": token_usage.get("calls"),
            },
        )
    notify(row["user_id"], str(row["document_id"]), "document.summarized", f"{row['filename']} summary is ready")


def mark_summary_failed(document_id: str, summary_id: str | None, code: str, message: str) -> None:
    """Record a terminal failure. The document returns to review instead of FAILED."""
    row = _load(document_id, summary_id)
    if not row:
        return
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE summaries
                SET status = CAST('FAILED' AS VARCHAR),
                    error_code = CAST(:code AS VARCHAR),
                    error_message = CAST(:message AS TEXT),
                    completed_at = CAST(:now AS TIMESTAMP),
                    updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:summary_id AS UUID)
                """
            ),
            {"summary_id": str(row["summary_id"]), "code": code, "message": message[:500], "now": now},
        )
        conn.execute(
            text(
                """
                UPDATE documents
                SET status = CAST('READY_FOR_REVIEW' AS VARCHAR), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID) AND status = CAST('SUMMARY_QUEUED' AS VARCHAR)
                """
            ),
            {"document_id": str(row["document_id"]), "now": now},
        )
        _audit(
            conn,
            user_id=row["user_id"],
            document_id=str(row["document_id"]),
            event_type="document.summary.failed",
            payload={"documentId": str(row["document_id"]), "summaryId": str(row["summary_id"]), "code": code},
        )
    notify(row["user_id"], str(row["document_id"]), "document.summary_failed", f"{row['filename']} summary failed")


def run_summary(
    document_id: str,
    summary_id: str | None = None,
    *,
    include_markdown: bool = True,
    model: Summarizer | None = None,
    s3_client: S3Client | None = None,
) -> dict[str, Any]:
    row = _load(document_id, summary_id)
    if not row or row["document_deleted_at"] is not None or row["summary_deleted_at"] is not None:
        raise SummaryError("SUMMARY_MISSING", "The summary request no longer exists.", retryable=False)
    if row["status"] in SUMMARY_FINISHED:
        return {"skipped": True, "summaryId": str(row["summary_id"]), "status": row["status"]}

    _mark_processing(str(row["summary_id"]))
    s3 = s3_client or _default_s3()
    ocr = _download_ocr(s3, row["ocr_s3_key"] or "")
    detections, manual = _load_selection(document_id)
    source = build_source(ocr, detections, manual, safe_mode=bool(row["safe_mode"]))
    generated = generate_summary(
        mode=row["mode"],
        pages=source.pages,
        forbidden=source.forbidden,
        model=model or BedrockSummarizer(),
        max_pages=SUMMARY_MAX_PAGES,
    )
    payload = envelope(mode=row["mode"], safe_mode=bool(row["safe_mode"]), generated=generated)
    try:
        label = get_mode_policy(row["mode"]).label
    except UnknownModeError:
        label = row["mode"]
    markdown = (
        render_markdown(label, generated.payload, safe_mode=bool(row["safe_mode"]), truncated=generated.truncated)
        if include_markdown
        else ""
    )
    usage = {
        "inputTokens": generated.input_tokens,
        "outputTokens": generated.output_tokens,
        "calls": generated.calls,
        "model": getattr(model, "model_id", None) or BEDROCK_MODEL_ID,
    }
    _mark_done(row, payload=payload, markdown=markdown, token_usage=usage)
    logger.info(
        "summary completed document_id=%s summary_id=%s calls=%s pages=%s",
        document_id,
        row["summary_id"],
        generated.calls,
        generated.pages_used,
    )
    return {
        "summaryId": str(row["summary_id"]),
        "pages": generated.pages_used,
        "calls": generated.calls,
        "truncated": generated.truncated,
    }

