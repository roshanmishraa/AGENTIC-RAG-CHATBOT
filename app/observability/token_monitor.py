from __future__ import annotations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta

from app.db.models import Message
from app.observability.logger import get_logger

logger = get_logger(__name__)

# Simple in-process daily budget guard — resets are handled by querying
# actual DB totals rather than keeping fragile in-memory counters.
DAILY_COST_ALERT_THRESHOLD_USD = 5.0


async def log_usage(chat_id: str, user_id: str, model_used: str, tokens_used: int, cost_usd: float):
    """Called right after every LLM response — structured log for real-time monitoring,
    on top of the DB row already saved by chat.py."""
    logger.info(
        "llm_call_completed",
        extra={
            "chat_id": chat_id,
            "user_id": user_id,
            "model_used": model_used,
            "tokens_used": tokens_used,
        }
    )
    if cost_usd > 0.05:   # flag unusually expensive single calls
        logger.warning(f"High-cost single call: ${cost_usd:.4f} (model={model_used}, chat={chat_id})")


async def get_daily_cost(db: AsyncSession) -> float:
    since = datetime.utcnow() - timedelta(days=1)
    result = await db.execute(
        select(func.sum(Message.cost_usd)).where(Message.created_at >= since)
    )
    return result.scalar() or 0.0


async def check_daily_budget_alert(db: AsyncSession) -> dict:
    """Called by admin.py — surfaces a warning banner in the admin dashboard
    if spend is approaching the threshold. Doesn't block requests (that would
    need a harder circuit-breaker, which is a reasonable Phase-6+ addition
    if this ever goes to real production traffic)."""
    daily_cost = await get_daily_cost(db)
    return {
        "daily_cost_usd": round(daily_cost, 4),
        "threshold_usd": DAILY_COST_ALERT_THRESHOLD_USD,
        "alert": daily_cost >= DAILY_COST_ALERT_THRESHOLD_USD,
    }