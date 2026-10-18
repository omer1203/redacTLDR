"""Remove stored data when the user asks, and when a document is past its retention.

S3 objects go first. Database rows go only after the files are gone, so a retry
can find the keys again. Notices and settings go last.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import bindparam, text

from services.worker.app.config import S3_BUCKET_DOWNLOADS, S3_BUCKET_ORIGINALS
from services.worker.app.db import engine
from services.worker.app.export import _default_s3

logger = logging.getLogger(__name__)

_CHILD_TABLES = (
    "detections",
    "manual_redactions",
    "exports",
    "summaries",
    "jobs",
    "document_pages",
)


def _delete_keys(s3, pairs: list[tuple[str, str]]) -> None:
    for bucket, key in pairs:
        if not key:
            continue
        try:
            s3.delete_object(Bucket=bucket, Key=key)
        except Exception:  # noqa: BLE001
            logger.warning("retention could not delete an object bucket=%s", bucket)


def purge_user(user_id: str) -> dict:
    s3 = _default_s3()
    with engine.begin() as conn:
        docs = conn.execute(
            text(
                """
                SELECT id, s3_key_original, s3_key, ocr_s3_key
                FROM documents WHERE user_id = CAST(:user_id AS VARCHAR)
                """
            ),
            {"user_id": user_id},
        ).mappings().all()
        export_keys = []
        if docs:
            export_keys = conn.execute(
                text("SELECT s3_key FROM exports WHERE document_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                {"ids": [row["id"] for row in docs]},
            ).scalars().all()
    pairs = []
    for row in docs:
        for key in (row["s3_key_original"], row["s3_key"], row["ocr_s3_key"]):
            pairs.append((S3_BUCKET_ORIGINALS, key))
    pairs.extend((S3_BUCKET_DOWNLOADS, key) for key in export_keys)
    _delete_keys(s3, pairs)

    with engine.begin() as conn:
        ids = [row["id"] for row in docs]
        if ids:
            for table in _CHILD_TABLES:
                conn.execute(
                    text(f"DELETE FROM {table} WHERE document_id IN :ids").bindparams(bindparam("ids", expanding=True)),
                    {"ids": ids},
                )
            conn.execute(
                text("DELETE FROM documents WHERE user_id = CAST(:user_id AS VARCHAR)"),
                {"user_id": user_id},
            )
        conn.execute(text("DELETE FROM notifications WHERE user_id = CAST(:user_id AS VARCHAR)"), {"user_id": user_id})
        conn.execute(text("DELETE FROM user_settings WHERE user_id = CAST(:user_id AS VARCHAR)"), {"user_id": user_id})
        conn.execute(text("DELETE FROM audit_logs WHERE user_id = CAST(:user_id AS VARCHAR)"), {"user_id": user_id})
    logger.info("purge_user documents=%s", len(docs))
    return {"ok": True, "documents": len(docs)}


def apply_retention() -> dict:
    """Soft-delete documents older than the owner's retention and remove their files."""
    removed = 0
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT d.id, d.user_id, d.s3_key_original, d.s3_key, d.ocr_s3_key,
                       COALESCE(s.retention_days, 30) AS retention_days
                FROM documents d
                LEFT JOIN user_settings s ON s.user_id = d.user_id
                WHERE d.deleted_at IS NULL
                  AND d.created_at < NOW() - (COALESCE(s.retention_days, 30) || ' days')::interval
                """
            )
        ).mappings().all()
    if not rows:
        return {"ok": True, "removed": 0}
    s3 = _default_s3()
    _delete_keys(
        s3,
        [(S3_BUCKET_ORIGINALS, key) for row in rows for key in (row["s3_key_original"], row["s3_key"], row["ocr_s3_key"])],
    )
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE documents
                SET deleted_at = CAST(:now AS TIMESTAMP), updated_at = CAST(:now AS TIMESTAMP)
                WHERE id IN :ids
                """
            ).bindparams(bindparam("ids", expanding=True)),
            {"now": now, "ids": [row["id"] for row in rows]},
        )
    removed = len(rows)
    logger.info("apply_retention removed=%s", removed)
    return {"ok": True, "removed": removed}
