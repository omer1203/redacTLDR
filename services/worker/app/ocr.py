"""OCR stage for R2.

Textract reads the original PDF in S3. This module turns those blocks into a
pages → lines → words model with normalized boxes, then stores that JSON in S3.
Postgres only keeps page sizes, word counts, and the S3 key.

Do not log line text, word text, or the OCR JSON. Those strings are document content.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import text

from services.worker.app.config import AWS_REGION, S3_BUCKET_ORIGINALS
from services.worker.app.db import engine

logger = logging.getLogger(__name__)

# Poll StartDocumentTextDetection until this budget is spent. Textract jobs
# usually finish well inside it; the cap keeps a stuck job from living forever.
POLL_DEADLINE_SECONDS = 600.0
POLL_START_SECONDS = 2.0
POLL_MAX_SECONDS = 10.0
MAX_PDF_BYTES = 20 * 1024 * 1024
# Cost cap shared with summaries. A longer PDF is rejected before Textract is called.
MAX_DOCUMENT_PAGES = 30

_RETRYABLE_CLIENT_CODES = {
    "ThrottlingException",
    "ProvisionedThroughputExceededException",
    "LimitExceededException",
    "InternalServerError",
    "ServiceUnavailableException",
}
_PERMANENT_CLIENT_CODES = {
    "UnsupportedDocumentException",
    "BadDocumentException",
    "InvalidS3ObjectException",
    "DocumentTooLargeException",
}


class OcrError(Exception):
    """A failure the pipeline can show to the user without echoing document text."""

    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class TextractClient(Protocol):
    def start_document_text_detection(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_document_text_detection(self, **kwargs: Any) -> dict[str, Any]: ...


class S3Client(Protocol):
    def get_object(self, **kwargs: Any) -> dict[str, Any]: ...

    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PageInspection:
    """Physical page facts from the PDF, independent of Textract text."""

    page_number: int
    width: float
    height: float
    has_text_layer: bool


def bbox_from_textract(geometry: dict[str, Any] | None) -> dict[str, float]:
    """Textract BoundingBox is already 0–1: Left/Top/Width/Height."""
    box = (geometry or {}).get("BoundingBox") or {}
    return {
        "x": float(box.get("Left") or 0.0),
        "y": float(box.get("Top") or 0.0),
        "width": float(box.get("Width") or 0.0),
        "height": float(box.get("Height") or 0.0),
    }


def _child_ids(block: dict[str, Any], relationship_type: str) -> list[str]:
    ids: list[str] = []
    for relationship in block.get("Relationships") or []:
        if relationship.get("Type") == relationship_type:
            ids.extend(relationship.get("Ids") or [])
    return ids


def normalize_textract_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group Textract PAGE/LINE/WORD blocks into one record per page.

    A LINE's words come from its CHILD relationship, so a phrase that wraps
    stays on the line Textract assigned. Pages with no lines are still returned
    so a scanned blank page keeps its page number.
    """
    by_id = {block["Id"]: block for block in blocks if block.get("Id")}
    pages: dict[int, dict[str, Any]] = {}

    def bucket(page_number: int) -> dict[str, Any]:
        return pages.setdefault(page_number, {"pageNumber": page_number, "lines": []})

    page_blocks = [block for block in blocks if block.get("BlockType") == "PAGE"]
    if not page_blocks:
        for block in blocks:
            if block.get("Page"):
                bucket(int(block["Page"]))

    for page in page_blocks:
        page_number = int(page.get("Page") or 1)
        record = bucket(page_number)
        for line_id in _child_ids(page, "CHILD"):
            line = by_id.get(line_id)
            if not line or line.get("BlockType") != "LINE":
                continue
            words = []
            for word_id in _child_ids(line, "CHILD"):
                word = by_id.get(word_id)
                if not word or word.get("BlockType") != "WORD":
                    continue
                words.append(
                    {
                        "text": word.get("Text") or "",
                        "bbox": bbox_from_textract(word.get("Geometry")),
                    }
                )
            record["lines"].append(
                {
                    "text": line.get("Text") or "",
                    "bbox": bbox_from_textract(line.get("Geometry")),
                    "words": words,
                }
            )

    return [pages[number] for number in sorted(pages)]


def start_or_resume_textract(
    client: TextractClient,
    existing_job_id: str | None,
    bucket: str,
    key: str,
) -> tuple[str, bool]:
    """Return `(job_id, started_new)`.

    A saved job id means a previous attempt already paid for Textract. Poll that
    job instead of starting another one.
    """
    if existing_job_id:
        return existing_job_id, False
    response = client.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
    )
    job_id = str(response["JobId"])
    return job_id, True


def collect_textract_blocks(
    client: TextractClient,
    job_id: str,
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    deadline_s: float = POLL_DEADLINE_SECONDS,
) -> list[dict[str, Any]]:
    """Poll until Textract finishes, then follow NextToken until every block is loaded."""
    delay = POLL_START_SECONDS
    started = clock()
    blocks: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        if clock() - started > deadline_s:
            raise OcrError(
                "TEXTRACT_TIMEOUT",
                "Reading the document timed out. You can retry.",
                retryable=True,
            )
        kwargs: dict[str, Any] = {"JobId": job_id}
        if token:
            kwargs["NextToken"] = token
        response = client.get_document_text_detection(**kwargs)
        status = response.get("JobStatus")
        if status == "IN_PROGRESS":
            sleep(delay)
            delay = min(POLL_MAX_SECONDS, max(POLL_START_SECONDS, delay * 1.5))
            token = None
            continue
        if status == "SUCCEEDED":
            blocks.extend(response.get("Blocks") or [])
            token = response.get("NextToken")
            if not token:
                return blocks
            continue
        if status in {"FAILED", "PARTIAL_SUCCESS"}:
            raise OcrError(
                "TEXTRACT_FAILED",
                "Textract could not read this PDF.",
                retryable=False,
            )
        raise OcrError(
            "TEXTRACT_FAILED",
            "Textract returned an unexpected status.",
            retryable=True,
        )


def inspect_pdf(pdf_bytes: bytes) -> list[PageInspection]:
    """Read page size and whether each page already has a text layer.

    The text layer is only used as a boolean. The characters themselves are discarded.
    """
    if not pdf_bytes:
        raise OcrError("UNSUPPORTED_PDF", "The file is empty.", retryable=False)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise OcrError("UNSUPPORTED_PDF", "The file is larger than the 20 MB limit.", retryable=False)

    import pymupdf

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 — PyMuPDF raises several types for bad files
        raise OcrError("UNSUPPORTED_PDF", "The file is not a readable PDF.", retryable=False) from exc

    pages: list[PageInspection] = []
    try:
        if document.page_count < 1:
            raise OcrError("UNSUPPORTED_PDF", "The PDF has no pages.", retryable=False)
        if document.page_count > MAX_DOCUMENT_PAGES:
            raise OcrError(
                "TOO_MANY_PAGES",
                f"This PDF has {document.page_count} pages. The limit is {MAX_DOCUMENT_PAGES}.",
                retryable=False,
            )
        for index, page in enumerate(document):
            rect = page.rect
            # `get_text` is not logged and not returned. Only emptiness matters.
            has_text = bool((page.get_text("text") or "").strip())
            pages.append(
                PageInspection(
                    page_number=index + 1,
                    width=float(rect.width),
                    height=float(rect.height),
                    has_text_layer=has_text,
                )
            )
    finally:
        document.close()
    return pages


def merge_ocr_payload(
    inspections: list[PageInspection],
    textract_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Combine PDF page sizes with Textract lines. Page count is the larger of the two."""
    by_number = {page["pageNumber"]: page for page in textract_pages}
    inspection_by_number = {page.page_number: page for page in inspections}
    numbers = sorted(set(by_number) | set(inspection_by_number))
    pages: list[dict[str, Any]] = []
    for number in numbers:
        inspection = inspection_by_number.get(number)
        extracted = by_number.get(number) or {"pageNumber": number, "lines": []}
        lines = extracted.get("lines") or []
        word_count = sum(len(line.get("words") or []) for line in lines)
        pages.append(
            {
                "pageNumber": number,
                "width": inspection.width if inspection else 0.0,
                "height": inspection.height if inspection else 0.0,
                "hasTextLayer": inspection.has_text_layer if inspection else False,
                "wordCount": word_count,
                "lines": lines,
            }
        )
    return {"version": 1, "pageCount": len(pages), "pages": pages}


def ocr_object_key(user_id: str, document_id: str) -> str:
    return f"ocr/{user_id}/{document_id}.json"


def _default_textract() -> TextractClient:
    return boto3.client("textract", region_name=AWS_REGION)


def _default_s3() -> S3Client:
    return boto3.client("s3", region_name=AWS_REGION)


def _load_document(document_id: str):
    with engine.begin() as conn:
        return conn.execute(
            text(
                """
                SELECT user_id, s3_key, ocr_s3_key, textract_job_id, page_count, deleted_at
                FROM documents
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"document_id": document_id},
        ).mappings().first()


def _save_textract_job_id(document_id: str, job_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET textract_job_id = CAST(:job_id AS VARCHAR),
                    updated_at = CAST(:updated_at AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {"job_id": job_id, "updated_at": _utcnow(), "document_id": document_id},
        )


def _utcnow():
    from datetime import datetime

    return datetime.utcnow()


def _store_ocr(
    document_id: str,
    user_id: str,
    payload: dict[str, Any],
    s3_client: S3Client,
) -> str:
    key = ocr_object_key(user_id, document_id)
    body = json.dumps(payload).encode("utf-8")
    s3_client.put_object(
        Bucket=S3_BUCKET_ORIGINALS,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    from uuid import uuid4

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM document_pages WHERE document_id = CAST(:document_id AS UUID)"),
            {"document_id": document_id},
        )
        for page in payload["pages"]:
            conn.execute(
                text(
                    """
                    INSERT INTO document_pages
                    (id, document_id, page_number, width, height, word_count, has_text_layer)
                    VALUES (
                      CAST(:id AS UUID),
                      CAST(:document_id AS UUID),
                      CAST(:page_number AS INTEGER),
                      CAST(:width AS DOUBLE PRECISION),
                      CAST(:height AS DOUBLE PRECISION),
                      CAST(:word_count AS INTEGER),
                      CAST(:has_text_layer AS BOOLEAN)
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "page_number": page["pageNumber"],
                    "width": page["width"],
                    "height": page["height"],
                    "word_count": page["wordCount"],
                    "has_text_layer": page["hasTextLayer"],
                },
            )
        conn.execute(
            text(
                """
                UPDATE documents
                SET page_count = CAST(:page_count AS INTEGER),
                    ocr_s3_key = CAST(:ocr_s3_key AS VARCHAR),
                    updated_at = CAST(:updated_at AS TIMESTAMP)
                WHERE id = CAST(:document_id AS UUID)
                """
            ),
            {
                "page_count": payload["pageCount"],
                "ocr_s3_key": key,
                "updated_at": _utcnow(),
                "document_id": document_id,
            },
        )
    return key


def _map_client_error(exc: ClientError) -> OcrError:
    code = exc.response.get("Error", {}).get("Code") or ""
    if code in _PERMANENT_CLIENT_CODES:
        return OcrError("UNSUPPORTED_PDF", "Textract could not read this PDF.", retryable=False)
    return OcrError(
        "TEXTRACT_FAILED",
        "Text detection failed. You can retry.",
        retryable=code in _RETRYABLE_CLIENT_CODES or not code,
    )


def run_ocr_for_document(
    document_id: str,
    *,
    textract_client: TextractClient | None = None,
    s3_client: S3Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run OCR unless this document already has an OCR object.

    Returns `{ok, skipped, pageCount}`. `skipped` is true when `ocr_s3_key` is
    already set, which is how a retried pipeline avoids a second Textract start.
    """
    row = _load_document(document_id)
    if not row or row["deleted_at"] is not None:
        raise OcrError("MISSING_DOCUMENT", "Document is no longer available.", retryable=False)
    if row["ocr_s3_key"]:
        logger.info("ocr skipped document_id=%s", document_id)
        return {"ok": True, "skipped": True, "pageCount": row["page_count"]}

    s3 = s3_client or _default_s3()
    try:
        obj = s3.get_object(Bucket=S3_BUCKET_ORIGINALS, Key=row["s3_key"])
        pdf_bytes = obj["Body"].read()
    except ClientError as exc:
        raise _map_client_error(exc) from exc

    inspections = inspect_pdf(pdf_bytes)
    textract = textract_client or _default_textract()
    try:
        job_id, started = start_or_resume_textract(
            textract,
            row["textract_job_id"],
            S3_BUCKET_ORIGINALS,
            row["s3_key"],
        )
        if started:
            _save_textract_job_id(document_id, job_id)
            logger.info("ocr textract started document_id=%s job_id=%s", document_id, job_id)
        else:
            logger.info("ocr textract resume document_id=%s job_id=%s", document_id, job_id)
        blocks = collect_textract_blocks(textract, job_id, sleep=sleep, clock=clock)
    except OcrError:
        raise
    except ClientError as exc:
        raise _map_client_error(exc) from exc

    payload = merge_ocr_payload(inspections, normalize_textract_blocks(blocks))
    key = _store_ocr(document_id, row["user_id"], payload, s3)
    logger.info("ocr stored document_id=%s pages=%s", document_id, payload["pageCount"])
    return {"ok": True, "skipped": False, "pageCount": payload["pageCount"], "ocrKey": key}
