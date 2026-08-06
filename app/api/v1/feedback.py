# app/api/v1/feedback.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models import Feedback, Message, User
from app.security.rbac import get_current_user

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., ge=-1, le=1)   # -1 = thumbs down, 1 = thumbs up
    comment: str | None = None


@router.post("")
async def submit_feedback(
    payload: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 1. Verify the message exists AND belongs to this user's chat.
    #    Without this, any user can submit feedback on any message —
    #    including messages from other users' private conversations.
    result = await db.execute(
        select(Message)
        .join(Message.chat)                  # JOIN chats
        .where(
            Message.id == payload.message_id,
            Message.chat.has(user_id=user.id),  # ownership check
        )
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(
            status_code=404,
            detail="Message not found or does not belong to you",
        )

    # 2. One feedback per user per message — prevent duplicate votes.
    #    Without this, a user can thumbs-up the same message 1000 times.
    existing = await db.execute(
        select(Feedback).where(
            Feedback.message_id == payload.message_id,
            Feedback.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="You have already submitted feedback for this message",
        )

    fb = Feedback(
        message_id=payload.message_id,
        user_id=user.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(fb)
    await db.commit()
    return {"status": "recorded", "rating": payload.rating}