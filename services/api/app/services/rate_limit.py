"""Per-user request caps.

Redis is the shared counter, so a second API process enforces the same limit.
If Redis is down, the process keeps its own counter rather than allowing every
request through.
"""

from __future__ import annotations

import logging
import threading
import time

from fastapi import Depends, HTTPException

from services.api.app.auth import CurrentUser
from services.api.app.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_memory: dict[str, tuple[int, float]] = {}
_redis = None
_redis_failed = False


def _client():
    global _redis, _redis_failed
    if _redis_failed:
        return None
    if _redis is None:
        try:
            import redis

            _redis = redis.Redis.from_url(get_settings().celery_broker_url, socket_timeout=0.2)
            _redis.ping()
        except Exception:  # noqa: BLE001
            logger.warning("rate limit using in-process counters; redis unavailable")
            _redis_failed = True
            return None
    return _redis


def allow(user_id: str, action: str, limit: int, window_seconds: int) -> bool:
    key = f"rl:{action}:{user_id}"
    client = _client()
    if client is not None:
        try:
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, window_seconds)
            return count <= limit
        except Exception:  # noqa: BLE001
            logger.warning("rate limit redis error action=%s", action)
    now = time.monotonic()
    with _lock:
        count, started = _memory.get(key, (0, now))
        if now - started >= window_seconds:
            count, started = 0, now
        count += 1
        _memory[key] = (count, started)
        return count <= limit


def rate_limit(action: str, limit: int, window_seconds: int = 3600):
    def dependency(user=CurrentUser) -> None:
        if not allow(user.user_id, action, limit, window_seconds):
            raise HTTPException(status_code=429, detail="Too many requests. Wait a bit and try again.")

    return Depends(dependency)
