from __future__ import annotations
import json
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.settings import settings
from app.db.models import Message, Chat

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

SHORT_TERM_TTL = 3600   # 1 hour — short-term memory expires if chat goes idle
SHORT_TERM_MAX_TURNS = 10


# ============================================================
# Short-term memory (current conversation) — Redis for speed
# ============================================================
async def get_short_term_memory(chat_id: str) -> list[dict]:
    raw = await redis_client.get(f"chat_memory:{chat_id}")
    return json.loads(raw) if raw else []


async def append_short_term_memory(chat_id: str, role: str, content: str):
    history = await get_short_term_memory(chat_id)
    history.append({"role": role, "content": content})
    history = history[-SHORT_TERM_MAX_TURNS:]   # keep only recent turns — bounded context
    await redis_client.set(f"chat_memory:{chat_id}", json.dumps(history), ex=SHORT_TERM_TTL)


async def load_history_from_db(db: AsyncSession, chat_id: str, limit: int = 10) -> list[dict]:
    """Fallback/cold-start: if Redis cache expired, rebuild short-term memory from Postgres."""
    result = await db.execute(
        select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.desc()).limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in messages]


# ============================================================
# Long-term memory (cross-session facts about the user) — Postgres for durability
# ============================================================
async def get_user_long_term_notes(db: AsyncSession, user_id: str) -> str:
    """
    Simple approach: pull a summary of the user's past chat topics.
    (Could be upgraded later to an LLM-generated running summary stored per-user.)
    """
    result = await db.execute(
        select(Chat.title).where(Chat.user_id == user_id).order_by(Chat.created_at.desc()).limit(5)
    )
    titles = result.scalars().all()
    if not titles:
        return ""
    return "User's recent topics: " + ", ".join(titles)