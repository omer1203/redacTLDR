"""Publish the Celery queue length so ECS can scale the worker on it.

Local beat runs this every minute and returns immediately. ECS sets
CLOUDWATCH_METRICS_NAMESPACE (RedacTLDR) and the worker role can PutMetricData.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager

from services.worker.app.config import AWS_REGION, CELERY_BROKER_URL

logger = logging.getLogger(__name__)


def publish_queue_depth() -> dict:
    namespace = os.environ.get("CLOUDWATCH_METRICS_NAMESPACE", "").strip()
    if not namespace:
        return {"ok": True, "skipped": True}
    import boto3
    import redis

    depth = int(redis.Redis.from_url(CELERY_BROKER_URL).llen("default"))
    boto3.client("cloudwatch", region_name=AWS_REGION).put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": "QueueDepth",
                "Dimensions": [{"Name": "QueueName", "Value": "default"}],
                "Value": depth,
                "Unit": "Count",
            }
        ],
    )
    return {"ok": True, "depth": depth}


def record_stage_seconds(stage: str, seconds: float) -> None:
    """How long OCR, detection, export, or summary took. No-op without a namespace."""
    namespace = os.environ.get("CLOUDWATCH_METRICS_NAMESPACE", "").strip()
    if not namespace:
        return
    try:
        import boto3

        boto3.client("cloudwatch", region_name=AWS_REGION).put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": "StageSeconds",
                    "Dimensions": [{"Name": "Stage", "Value": stage}],
                    "Value": seconds,
                    "Unit": "Seconds",
                }
            ],
        )
    except Exception:  # noqa: BLE001
        logger.warning("stage metric failed stage=%s", stage)


@contextmanager
def stage_timer(stage: str):
    started = time.perf_counter()
    try:
        yield
    finally:
        record_stage_seconds(stage, time.perf_counter() - started)
