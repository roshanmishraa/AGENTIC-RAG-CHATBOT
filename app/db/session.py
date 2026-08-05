from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncSession
)
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.settings import settings
from app.db.models import Base

# ------------------------------------------------------------
# Async engine + session factory
# ------------------------------------------------------------
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,               # set True for SQL debug logs
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,       # avoids "stale connection" errors after idle time
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — inject with `db: AsyncSession = Depends(get_db)`"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Called once on startup. Creates the pgvector extension (if missing)
    and all tables. In production, prefer Alembic migrations instead
    of create_all — but this is a safe first-run bootstrap.
    """
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)