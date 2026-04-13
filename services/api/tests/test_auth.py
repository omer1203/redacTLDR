import pytest

from services.api.app.auth import get_current_user


@pytest.mark.asyncio
async def test_local_demo_header_support() -> None:
    user = await get_current_user(authorization=None, x_demo_user="demo-user")
    assert user.user_id == "demo-user"
