"""In-app notices. Titles only; the worker never puts a detected value in one."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select, update
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.db import get_db
from services.api.app.models import Notification

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    id: UUID
    documentId: UUID | None
    kind: str
    title: str
    readAt: datetime | None
    createdAt: datetime


class ReadRequest(BaseModel):
    ids: list[UUID] = Field(default_factory=list)
    all: bool = False


def _out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        documentId=row.document_id,
        kind=row.kind,
        title=row.title,
        readAt=row.read_at,
        createdAt=row.created_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), user=CurrentUser):
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.user_id)
        .order_by(desc(Notification.created_at))
        .limit(30)
    ).all()
    return [_out(row) for row in rows]


@router.post("/read", response_model=dict)
def mark_read(payload: ReadRequest, db: Session = Depends(get_db), user=CurrentUser):
    if not payload.all and not payload.ids:
        raise HTTPException(status_code=400, detail="Say which notices to mark read.")
    statement = update(Notification).where(Notification.user_id == user.user_id, Notification.read_at.is_(None))
    if not payload.all:
        statement = statement.where(Notification.id.in_(payload.ids))
    result = db.execute(statement.values(read_at=datetime.utcnow()))
    db.commit()
    return {"updated": result.rowcount}
