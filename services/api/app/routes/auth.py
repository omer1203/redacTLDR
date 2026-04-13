from fastapi import APIRouter

from services.api.app.auth import CurrentUser

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/me")
async def me(user=CurrentUser):
    return {
        "id": user.user_id,
        "email": user.email,
        "sessionId": user.session_id,
    }
