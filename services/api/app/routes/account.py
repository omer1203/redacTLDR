"""Delete everything stored for the signed-in user."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.celery_client import enqueue_task
from services.api.app.db import get_db
from services.api.app.services.audit import log_event

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.post("/delete", status_code=202)
def delete_account(db: Session = Depends(get_db), user=CurrentUser):
    """Queue a hard delete of this user's documents, files, notices, and settings."""
    log_event(
        db,
        user_id=user.user_id,
        event_type="account.delete.queued",
        payload={},
    )
    db.commit()
    try:
        enqueue_task("purge_user_data", user.user_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Could not queue the deletion. Try again.") from exc
    return {"status": "QUEUED"}
