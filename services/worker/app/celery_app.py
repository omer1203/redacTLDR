"""
Celery worker runtime entrypoint.

This module creates the shared Celery application instance used by worker
processes and configures queue routing for task names emitted by the API.
"""

from celery import Celery

from services.worker.app.config import CELERY_BACKEND_URL, CELERY_BROKER_URL
from services.worker.app.telemetry import setup_worker_telemetry

# Name is visible in Celery inspect output and monitoring tools.
celery = Celery("redactldr-worker", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)

# Route all currently supported jobs to the default queue.
# This allows future queue specialization without changing producer call sites.
celery.conf.task_routes = {
    "detect_job": {"queue": "default"},
    "export_job": {"queue": "default"},
    "summary_job": {"queue": "default"},
    "cleanup_stale_uploads": {"queue": "default"},
}
celery.conf.beat_schedule = {
    "cleanup-stale-uploads-hourly": {
        "task": "cleanup_stale_uploads",
        "schedule": 3600.0,
    },
}
celery.conf.timezone = "UTC"

# Initialize worker tracing/metrics exporters.
setup_worker_telemetry()

# Ensure task decorators are registered.
from services.worker.app import tasks  # noqa: E402,F401
