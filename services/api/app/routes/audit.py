from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.db import get_db
from services.api.app.models import AuditLog

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("")
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None, alias="eventType"),
    db: Session = Depends(get_db),
    user=CurrentUser,
):
    statement = select(AuditLog).where(AuditLog.user_id == user.user_id)
    if event_type:
        statement = statement.where(AuditLog.event_type == event_type)
    statement = statement.order_by(desc(AuditLog.created_at)).offset(offset).limit(limit)
    rows = list(db.scalars(statement).all())
    return [
        {
            "id": str(row.id),
            "eventType": row.event_type,
            "payload": row.payload,
            "documentId": str(row.document_id) if row.document_id else None,
            "createdAt": row.created_at,
        }
        for row in rows
    ]
