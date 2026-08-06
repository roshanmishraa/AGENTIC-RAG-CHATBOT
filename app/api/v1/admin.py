# app/api/v1/admin.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import User, Chat, Message, Document, AuditLog
from app.security.rbac import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    # Paginated — loading ALL users into memory is a memory bomb at scale.
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    users = result.scalars().all()

    # Total count for frontend pagination controls
    total = (await db.execute(select(func.count(User.id)))).scalar() or 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "username": u.username,      # ← ADDED
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    user = await db.get(User, user_id)

    # Old code silently returned {"status": "deactivated"} even when
    # the user didn't exist — a lie that hides bugs and misuse.
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        return {"status": "already_deactivated"}

    user.is_active = False
    await db.commit()
    return {"status": "deactivated", "user_id": user_id}


@router.get("/usage")
async def usage_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """Token and cost monitoring — aggregated across all users."""
    total_tokens  = (await db.execute(select(func.sum(Message.tokens_used)))).scalar() or 0
    total_cost    = (await db.execute(select(func.sum(Message.cost_usd)))).scalar() or 0.0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_chats   = (await db.execute(select(func.count(Chat.id)))).scalar() or 0
    total_docs    = (await db.execute(select(func.count(Document.id)))).scalar() or 0

    return {
        "total_tokens_used": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "total_messages": total_messages,
        "total_chats": total_chats,
        "total_documents": total_docs,
    }


@router.get("/audit-logs")
async def audit_logs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    # Paginated — old code had limit(100) with no offset so page 2 was unreachable.
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()

    total = (await db.execute(select(func.count(AuditLog.id)))).scalar() or 0

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "detail": log.detail,
                "created_at": log.created_at,
            }
            for log in logs
        ],
    }