from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import User
from app.security.rbac import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None


@router.get("/me")
async def get_my_profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "phone_number": user.phone_number, "role": user.role.value,
        "auth_provider": user.auth_provider, "created_at": user.created_at,
    }


@router.patch("/me")
async def update_my_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number
    await db.commit()
    return {"status": "updated"}