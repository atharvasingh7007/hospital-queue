"""
Hospital Queue AI — Database Session Management
Async SQLAlchemy engine and session factory for SQLite (dev) and PostgreSQL (prod).
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine, AsyncEngine
)
from sqlalchemy.pool import NullPool


def _build_database_url() -> str:
    """Pick the right database URL based on environment."""
    if os.getenv("K_SERVICE"):
        host = os.getenv("ALLOYDB_HOST", "127.0.0.1")
        port = os.getenv("ALLOYDB_PORT", "3306")
        database = os.getenv("ALLOYDB_DATABASE", "hospital_queue")
        user = os.getenv("ALLOYDB_USER", "postgres")
        password = os.getenv("ALLOYDB_PASSWORD", "")
        if not password:
            return f"mysql+aiomysql://{user}@{host}:{port}/{database}"
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{database}"

    db_path = os.getenv("LOCAL_DB_PATH", "hospital_queue.db")
    return f"sqlite+aiosqlite:///{db_path}"


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = _build_database_url()
        if "sqlite" in url:
            _engine = create_async_engine(url, poolclass=NullPool, echo=False)
        else:
            _engine = create_async_engine(
                url,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a database session.
    
    Callers are responsible for committing when they need to.
    The session rolls back on unhandled exceptions and always closes.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Standalone context manager for scripts (seed, migrations, etc.)."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables from models metadata."""
    from models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Shut down the engine cleanly."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
