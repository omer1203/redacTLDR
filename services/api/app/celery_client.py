import logging

from celery import Celery

from services.api.app.config import get_settings
from services.shared.trace_context import inject_trace_headers

settings = get_settings()
logger = logging.getLogger(__name__)
celery_client = Celery(
    "redactldr-api",
    broker=settings.celery_broker_url,
    backend=settings.celery_backend_url,
)
# Must match worker `-Q default` (Celery's built-in default queue name is `celery`).
celery_client.conf.task_default_queue = "default"


def enqueue_task(task_name: str, *args: object) -> str:
    """Queue a Celery task and return broker task id."""
    result = celery_client.send_task(task_name, args=list(args), headers=inject_trace_headers())
    logger.info("Queued task %s id=%s", task_name, result.id)
    return str(result.id)
