"""
Authentication dependency helpers.

Main responsibility: validate Clerk-issued bearer JWTs and expose a normalized
`UserPrincipal` object to route handlers.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException
from jose import jwt

from services.api.app.config import get_settings
from services.api.app.schemas import UserPrincipal

# In-process JWKS cache to avoid network round-trips on every request.
# NOTE: cache is per API process/worker (not shared across instances).
_JWKS_CACHE: dict[str, Any] = {"keys": [], "expires_at": datetime.now(timezone.utc)}
_JWKS_TTL = timedelta(minutes=10)
logger = logging.getLogger(__name__)


async def _fetch_jwks() -> dict[str, Any]:
    """
    Fetch Clerk public keys used to verify JWT signatures.

    Uses a 10-minute in-memory TTL cache for performance.
    """
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise HTTPException(status_code=500, detail="clerk jwks not configured")

    now = datetime.now(timezone.utc)
    if _JWKS_CACHE["keys"] and now < _JWKS_CACHE["expires_at"]:
        # `jwt.decode` accepts a JWKS-like structure: {"keys": [...]}.
        return {"keys": _JWKS_CACHE["keys"]}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.clerk_jwks_url)
        response.raise_for_status()
        jwks = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        if _JWKS_CACHE["keys"]:
            logger.warning("JWKS refresh failed, using stale cache: %s", exc)
            return {"keys": _JWKS_CACHE["keys"]}
        raise HTTPException(status_code=401, detail="unable to fetch jwks") from exc

    _JWKS_CACHE["keys"] = jwks.get("keys", [])
    _JWKS_CACHE["expires_at"] = now + _JWKS_TTL
    return {"keys": _JWKS_CACHE["keys"]}


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> UserPrincipal:
    """
    Resolve user identity from Clerk JWT.

    For local prototyping, x-demo-user can be used when Clerk is not configured.
    """
    settings = get_settings()

    # Local-only bypass for fast iteration without full auth wiring.
    if x_demo_user and settings.environment == "local":
        return UserPrincipal(user_id=x_demo_user, email=None, session_id=None)

    # Require standard bearer token format.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.replace("Bearer ", "", 1)
    jwks = await _fetch_jwks()
    try:
        # Validate signature + standard claims against Clerk configuration.
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.clerk_audience,
            issuer=settings.clerk_issuer_url or None,
            options={"verify_at_hash": False},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("JWT verification failed for request: %s", exc.__class__.__name__)
        raise HTTPException(status_code=401, detail="invalid token") from exc

    # `sub` is the canonical subject/user identifier in JWT.
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token subject")

    # Normalize token claims into internal principal shape used by routes/services.
    return UserPrincipal(
        user_id=sub,
        email=payload.get("email"),
        session_id=payload.get("sid"),
    )


# Reusable FastAPI dependency alias for concise endpoint signatures.
CurrentUser = Depends(get_current_user)
