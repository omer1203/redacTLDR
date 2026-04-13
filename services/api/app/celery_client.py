from celery import Celery

from services.api.app.config import get_settings

settings = get_settings()
celery_client = Celery(
    "redactldr-api",
    broker=settings.celery_broker_url,
    backend=settings.celery_backend_url,
)
