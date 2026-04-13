from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException
from jose import jwt

from services.api.app.config import get_settings
from services.api.app.schemas import UserPrincipal

_JWKS_CACHE: dict[str, Any] = {"keys": [], "expires_at": datetime.now(timezone.utc)}


async def _fetch_jwks() -> dict[str, Any]:
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise HTTPException(status_code=500, detail="clerk jwks not configured")

    now = datetime.now(timezone.utc)
    if _JWKS_CACHE["keys"] and now < _JWKS_CACHE["expires_at"]:
        return {"keys": _JWKS_CACHE["keys"]}

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(settings.clerk_jwks_url)
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="unable to fetch jwks")

    jwks = response.json()
    _JWKS_CACHE["keys"] = jwks.get("keys", [])
    _JWKS_CACHE["expires_at"] = now + timedelta(minutes=10)
    return jwks


async def get_current_user(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> UserPrincipal:
    """
    Resolve user identity from Clerk JWT.

    For local prototyping, x-demo-user can be used when Clerk is not configured.
    """
    settings = get_settings()

    if x_demo_user and settings.environment == "local":
        return UserPrincipal(user_id=x_demo_user, email=None, session_id=None)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    token = authorization.replace("Bearer ", "", 1)
    jwks = await _fetch_jwks()
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.clerk_audience,
            issuer=settings.clerk_issuer_url or None,
            options={"verify_at_hash": False},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token subject")

    return UserPrincipal(
        user_id=sub,
        email=payload.get("email"),
        session_id=payload.get("sid"),
    )


CurrentUser = Depends(get_current_user)
