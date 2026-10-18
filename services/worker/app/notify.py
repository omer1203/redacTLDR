"""Insert one in-app notice. Failures are logged and swallowed so a notice never fails the job."""

from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import text

from services.worker.app.db import engine

logger = logging.getLogger(__name__)


def notify(user_id: str | None, document_id: str | None, kind: str, title: str) -> None:
    if not user_id or not title:
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO notifications (id, user_id, document_id, kind, title, created_at)
                    VALUES (CAST(:id AS UUID), CAST(:user_id AS VARCHAR), CAST(:document_id AS UUID),
                            CAST(:kind AS VARCHAR), CAST(:title AS VARCHAR), NOW())
                    """
                ),
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "document_id": document_id,
                    "kind": kind,
                    "title": title[:500],
                },
            )
    except Exception:  # noqa: BLE001 — a missing table or a locked row must not fail the document
        logger.warning("notification insert failed kind=%s document_id=%s", kind, document_id)
