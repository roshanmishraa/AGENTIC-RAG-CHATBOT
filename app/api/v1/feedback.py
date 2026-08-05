from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models import Feedback, User
from app.security.rbac import get_current_user

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1)   # -1 = down, 1 = up
    comment: str | None = None


@router.post("")
async def submit_feedback(
    payload: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    fb = Feedback(
        message_id=payload.message_id, user_id=user.id,
        rating=payload.rating, comment=payload.comment,
    )
    db.add(fb)
    await db.commit()
    return {"status": "recorded"}