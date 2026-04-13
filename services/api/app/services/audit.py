from sqlalchemy.orm import Session

from services.api.app.models import AuditLog


def log_event(db: Session, user_id: str, event_type: str, payload: dict, document_id=None) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            event_type=event_type,
            payload=payload,
            document_id=document_id,
        )
    )
