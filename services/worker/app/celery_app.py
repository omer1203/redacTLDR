from celery import Celery

from services.worker.app.config import CELERY_BACKEND_URL, CELERY_BROKER_URL
from services.worker.app.telemetry import setup_worker_telemetry

celery = Celery("redactldr-worker", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)
celery.conf.task_routes = {
    "detect_job": {"queue": "default"},
    "export_job": {"queue": "default"},
    "summary_job": {"queue": "default"},
}
setup_worker_telemetry()

# Ensure task decorators are registered.
from app import tasks  # noqa: E402,F401
