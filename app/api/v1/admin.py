from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.models import User, Chat, Message, Document, AuditLog
from app.security.rbac import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        {"id": u.id, "email": u.email, "role": u.role.value,
         "is_active": u.is_active, "created_at": u.created_at}
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    user = await db.get(User, user_id)
    if user:
        user.is_active = False
        await db.commit()
    return {"status": "deactivated"}


@router.get("/usage")
async def usage_stats(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    """Token/cost monitoring dashboard data."""
    total_tokens = (await db.execute(select(func.sum(Message.tokens_used)))).scalar() or 0
    total_cost = (await db.execute(select(func.sum(Message.cost_usd)))).scalar() or 0.0
    total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_chats = (await db.execute(select(func.count(Chat.id)))).scalar() or 0
    total_documents = (await db.execute(select(func.count(Document.id)))).scalar() or 0

    return {
        "total_tokens_used": total_tokens,
        "total_cost_usd": round(total_cost, 4),
        "total_messages": total_messages,
        "total_chats": total_chats,
        "total_documents": total_documents,
    }


@router.get("/audit-logs")
async def audit_logs(db: AsyncSession = Depends(get_db), _=Depends(require_admin)):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)
    )
    logs = result.scalars().all()
    return [
        {"id": l.id, "user_id": l.user_id, "action": l.action,
         "detail": l.detail, "created_at": l.created_at}
        for l in logs
    ]