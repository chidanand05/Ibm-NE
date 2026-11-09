"""
Database seed script — Milestone 2.1.

Seeds:
  1. System seed user (for FK references)
  2. Chinnaswamy Stadium venue
  3. RCB vs MI demo event
  4. Model configs for all 7 agents
  5. ChromaDB historical event records (3 synthetic)

All operations are idempotent: INSERT ... ON CONFLICT DO NOTHING.
Re-running the seed will not create duplicates.

Usage
-----
    python -m app.seed.run_seed

Or call seed_all() directly in tests.
"""

from __future__ import annotations

import asyncio
import logging

import structlog

log = structlog.get_logger(__name__)


async def seed_all(database_url: str | None = None, skip_chroma: bool = False) -> None:
    """
    Run all seed operations.

    Parameters
    ----------
    database_url   Override DATABASE_URL (useful in tests).
    skip_chroma    Skip ChromaDB seeding (set True when ChromaDB is unavailable).
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    from app.config import get_settings
    from app.seed.venues import seed_venue
    from app.seed.events import seed_event
    from app.seed.model_configs import seed_model_configs

    settings = get_settings()
    url = database_url or settings.database_url

    engine = create_async_engine(url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        try:
            await seed_venue(db)
            await seed_event(db)
            await seed_model_configs(db)
            await db.commit()
            log.info("seed.db_complete")
        except Exception as exc:
            await db.rollback()
            log.error("seed.db_failed", error=str(exc))
            raise

    await engine.dispose()

    if not skip_chroma:
        try:
            from app.seed.chroma_seed import seed_chroma_history
            await seed_chroma_history()
            log.info("seed.chroma_complete")
        except Exception as exc:
            log.warning("seed.chroma_failed", error=str(exc))
            # ChromaDB unavailable is non-fatal at seed time
    else:
        log.info("seed.chroma_skipped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_all())
