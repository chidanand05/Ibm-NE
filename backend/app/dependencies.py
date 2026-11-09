"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings

# ── Database engine (module-level singleton) ──────────────────────────────────

def _make_engine(settings: Settings):
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        echo=(settings.app_env == "development"),
    )


def _make_session_factory(settings: Settings):
    engine = _make_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)


# Lazy singletons — created on first request
_session_factory: async_sessionmaker | None = None
_redis_pool: aioredis.Redis | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session. Auto-commits or rolls back on exit."""
    global _session_factory
    if _session_factory is None:
        settings = get_settings()
        _session_factory = _make_session_factory(settings)
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a Redis client from the connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    yield _redis_pool


# ── Annotated dependency aliases (for cleaner route signatures) ───────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]
AppSettings = Annotated[Settings, Depends(get_settings)]
