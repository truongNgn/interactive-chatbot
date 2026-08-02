"""Async SQLAlchemy database setup for structured production data."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> bool:
    """Create tables for local/dev deployments.

    Production should replace this with Alembic migrations, but auto-create
    keeps Docker/local setup usable while the schema is still small.
    """
    try:
        from app import db_models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return True
    except Exception as exc:
        logger.warning("Database initialization failed: %s", exc)
        return False


async def db_ready() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.run_sync(lambda sync_conn: None)
        return True
    except Exception:
        return False


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
