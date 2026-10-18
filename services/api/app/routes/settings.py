"""Account defaults. The row is created the first time it is read."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from services.api.app.auth import CurrentUser
from services.api.app.db import get_db
from services.api.app.enums import DocumentMode
from services.api.app.models import UserSetting

router = APIRouter(prefix="/v1/settings", tags=["settings"])

RETENTION_CHOICES = {7, 30, 90}


class SettingsOut(BaseModel):
    defaultMode: DocumentMode
    safeMode: bool
    retentionDays: int
    storeRawDetections: bool


class SettingsUpdate(BaseModel):
    defaultMode: DocumentMode
    safeMode: bool = True
    retentionDays: int = Field(default=30)
    storeRawDetections: bool = False


def _get_or_create(db: Session, user_id: str) -> UserSetting:
    row = db.get(UserSetting, user_id)
    if row:
        return row
    row = UserSetting(
        user_id=user_id,
        default_mode=DocumentMode.RESUME_ANONYMIZATION.value,
        safe_mode=True,
        retention_days=30,
        store_raw_detections=False,
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _out(row: UserSetting) -> SettingsOut:
    return SettingsOut(
        defaultMode=DocumentMode(row.default_mode),
        safeMode=row.safe_mode,
        retentionDays=row.retention_days,
        storeRawDetections=row.store_raw_detections,
    )


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), user=CurrentUser):
    return _out(_get_or_create(db, user.user_id))


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db), user=CurrentUser):
    if payload.retentionDays not in RETENTION_CHOICES:
        payload = payload.model_copy(update={"retentionDays": 30})
    row = _get_or_create(db, user.user_id)
    row.default_mode = payload.defaultMode.value
    row.safe_mode = payload.safeMode
    row.retention_days = payload.retentionDays
    row.store_raw_detections = payload.storeRawDetections
    row.updated_at = datetime.utcnow()
    db.commit()
    return _out(row)
