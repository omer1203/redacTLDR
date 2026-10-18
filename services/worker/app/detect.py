"""Detect stage for R3: OCR JSON in S3 → detections rows in Postgres.

This is the I/O shell around `detection.engine`. Re-running it replaces the
document's detections in one transaction, so a retry never duplicates rows.

Do not log detected values, page text, or `Finding` objects. Counts only.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text

from services.shared.policy import UnknownModeError
from services.worker.app.config import AWS_REGION, S3_BUCKET_ORIGINALS, STORE_RAW_DETECTIONS
from services.worker.app.db import engine
from services.worker.app.detection.comprehend import ComprehendPiiDetector, PiiDetector
from services.worker.app.detection.engine import DetectionResult, detect_document
from services.worker.app.detection.models import DetectionError, Finding
from services.worker.app.ocr import S3Client

logger = logging.getLogger(__name__)


def default_pii_detector() -> PiiDetector:
    return ComprehendPiiDetector(region_name=AWS_REGION)


def _default_s3() -> S3Client:
    return boto3.client("s3", region_name=AWS_REGION)


def _load_document(document_id: str):
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT mode, safe_mode, ocr_s3_key, deleted_at
                FROM documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).mappings().first()


def _forget_ocr(document_id: str) -> None:
    """Clear OCR pointers so the next attempt reads the PDF again.

    The Textract job id goes too: Textract keeps results for a limited time,
    and a fresh job is cheaper than a failure on an expired one.
    """
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET ocr_s3_key = NULL,
                    textract_job_id = NULL,
                    updated_at = CAST(:updated_at AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id, "updated_at": datetime.utcnow()},
        )


def _load_ocr_payload(document_id: str, key: str, s3_client: S3Client) -> dict[str, Any]:
    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET_ORIGINALS, Key=key)
        payload = json.loads(obj["Body"].read())
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code") or ""
        if code in {"NoSuchKey", "404"}:
            _forget_ocr(document_id)
            raise DetectionError(
                "OCR_MISSING",
                "The extracted text was not found. The document will be read again.",
                retryable=True,
            ) from exc
        raise DetectionError("DETECTION_FAILED", "Could not load the extracted text. You can retry.", retryable=True) from exc
    except BotoCoreError as exc:
        raise DetectionError("DETECTION_FAILED", "Could not load the extracted text. You can retry.", retryable=True) from exc
    except ValueError as exc:
        raise DetectionError("OCR_INVALID", "The extracted text is unreadable. Retry to read the document again.", retryable=False) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("pages"), list):
        raise DetectionError("OCR_INVALID", "The extracted text is unreadable. Retry to read the document again.", retryable=False)
    return payload


def _row_for(document_id: str, finding: Finding, now: datetime, *, store_raw: bool) -> dict[str, Any]:
    stored_text = finding.raw_text if store_raw else finding.masked_text
    return {
        "id": str(uuid4()),
        "document_id": document_id,
        "entity_type": finding.entity_type,
        "detected_text": stored_text,
        "page_number": finding.page_number,
        "block_ref": finding.block_ref,
        "confidence": finding.confidence,
        "bbox": json.dumps(finding.bbox),
        "rects": json.dumps(list(finding.rects)),
        "char_start": finding.char_start,
        "char_end": finding.char_end,
        "masked_text": finding.masked_text,
        "policy_action": finding.policy_action,
        "rule_id": finding.rule_id,
        "source": finding.source,
        "accepted": finding.accepted,
        "created_at": now,
    }


def replace_detections(document_id: str, findings: tuple[Finding, ...]) -> None:
    """Swap the document's machine detections for `findings` atomically.

    Rows are hard-deleted rather than soft-deleted so an old raw value (when
    raw storage was on) does not linger. Manual redactions live in another table.
    """
    now = datetime.utcnow()
    with engine.begin() as conn:
        store_raw = False
        if STORE_RAW_DETECTIONS:
            store_raw = bool(
                conn.execute(
                    text(
                        """
                        SELECT COALESCE(s.store_raw_detections, FALSE)
                        FROM documents d
                        LEFT JOIN user_settings s ON s.user_id = d.user_id
                        WHERE d.id = CAST(:document_id AS UUID)
                        """
                    ),
                    {"document_id": document_id},
                ).scalar()
            )
        rows = [_row_for(document_id, finding, now, store_raw=store_raw) for finding in findings]
        conn.execute(
            text("DELETE FROM detections WHERE document_id = CAST(:document_id AS UUID)"),
            {"document_id": document_id},
        )
        if not rows:
            return
        conn.execute(
            text(
                """
                INSERT INTO detections
                (id, document_id, entity_type, detected_text, page_number, block_ref, confidence,
                 bbox, rects, char_start, char_end, masked_text, policy_action, rule_id,
                 source, accepted, created_at)
                VALUES (
                  CAST(:id AS UUID),
                  CAST(:document_id AS UUID),
                  CAST(:entity_type AS VARCHAR),
                  CAST(:detected_text AS TEXT),
                  CAST(:page_number AS INTEGER),
                  CAST(:block_ref AS VARCHAR),
                  CAST(:confidence AS DOUBLE PRECISION),
                  CAST(:bbox AS JSONB),
                  CAST(:rects AS JSONB),
                  CAST(:char_start AS INTEGER),
                  CAST(:char_end AS INTEGER),
                  CAST(:masked_text AS VARCHAR),
                  CAST(:policy_action AS VARCHAR),
                  CAST(:rule_id AS VARCHAR),
                  CAST(:source AS VARCHAR),
                  CAST(:accepted AS BOOLEAN),
                  CAST(:created_at AS TIMESTAMP)
                )
                """
            ),
            rows,
        )


def run_detection_for_document(
    document_id: str,
    *,
    pii_detector: PiiDetector | None = None,
    s3_client: S3Client | None = None,
) -> dict[str, Any]:
    """Detect, apply the mode policy, and store results. Returns counts for the job row."""
    row = _load_document(document_id)
    if not row or row["deleted_at"] is not None:
        raise DetectionError("MISSING_DOCUMENT", "Document is no longer available.", retryable=False)
    if not row["ocr_s3_key"]:
        raise DetectionError("OCR_MISSING", "The document has not been read yet.", retryable=False)

    payload = _load_ocr_payload(document_id, row["ocr_s3_key"], s3_client or _default_s3())
    try:
        result: DetectionResult = detect_document(
            payload,
            mode=row["mode"],
            safe_mode=bool(row["safe_mode"]),
            pii_detector=pii_detector or default_pii_detector(),
        )
    except UnknownModeError as exc:
        raise DetectionError("UNKNOWN_MODE", "This document mode has no redaction policy.", retryable=False) from exc

    replace_detections(document_id, result.findings)
    summary = result.summary()
    logger.info(
        "detect stored document_id=%s total=%s accepted=%s pages=%s",
        document_id,
        summary["total"],
        summary["accepted"],
        summary["pagesScanned"],
    )
    return summary
