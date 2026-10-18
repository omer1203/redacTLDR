import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from services.api.app import auth
from services.api.app.auth import get_current_user

ISSUER = "https://clerk.example.test"
AUDIENCE = "redactldr-api"
KID = "test-key"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_private_key.public_key(), as_dict=True) | {"kid": KID, "use": "sig"}


def _token(**overrides) -> str:
    now = int(time.time())
    claims = {"sub": "user_123", "aud": AUDIENCE, "iss": ISSUER, "iat": now, "exp": now + 60, "sid": "sess_1"}
    claims.update(overrides)
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def clerk(monkeypatch):
    settings = auth.get_settings()
    monkeypatch.setattr(settings, "environment", "prod")
    monkeypatch.setattr(settings, "clerk_issuer_url", ISSUER)
    monkeypatch.setattr(settings, "clerk_audience", AUDIENCE)

    async def _jwks():
        return {"keys": [_public_jwk]}

    monkeypatch.setattr(auth, "_fetch_jwks", _jwks)


@pytest.mark.asyncio
async def test_local_demo_header_support() -> None:
    user = await get_current_user(authorization=None, x_demo_user="demo-user")
    assert user.user_id == "demo-user"


@pytest.mark.asyncio
async def test_valid_clerk_token_resolves_user(clerk) -> None:
    user = await get_current_user(authorization=f"Bearer {_token()}", x_demo_user=None)
    assert (user.user_id, user.session_id) == ("user_123", "sess_1")


@pytest.mark.asyncio
async def test_demo_header_is_ignored_outside_local(clerk) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=None, x_demo_user="demo-user")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: _token(aud="another-app"), id="wrong-audience"),
        pytest.param(lambda: _token(iss="https://evil.example"), id="wrong-issuer"),
        pytest.param(lambda: _token(exp=int(time.time()) - 10), id="expired"),
        pytest.param(lambda: _token(sub=""), id="missing-subject"),
        pytest.param(
            lambda: jwt.encode({"sub": "x", "aud": AUDIENCE, "iss": ISSUER}, _private_key, algorithm="RS256", headers={"kid": "other"}),
            id="unknown-kid",
        ),
        pytest.param(
            lambda: jwt.encode({"sub": "x", "aud": AUDIENCE, "iss": ISSUER}, "x" * 32, algorithm="HS256", headers={"kid": KID}),
            id="hs256-forgery",
        ),
    ],
)
async def test_rejected_tokens(clerk, token) -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization=f"Bearer {token()}", x_demo_user=None)
    assert exc.value.status_code == 401
