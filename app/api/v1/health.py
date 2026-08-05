from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis

from app.db.session import get_db
from app.settings import settings

router = APIRouter(prefix="/health", tags=["health"])
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.get("/live")
async def liveness():
    """Is the process even running? Used by Docker/orchestrator restart policies."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """Are dependencies (Postgres, Redis) actually reachable? Used by load
    balancers to decide whether to route traffic to this instance."""
    checks = {"postgres": False, "redis": False}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass

    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_healthy = all(checks.values())
    return {"status": "ready" if all_healthy else "degraded", "checks": checks}