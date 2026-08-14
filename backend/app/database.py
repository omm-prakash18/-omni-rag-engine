"""
app/database.py — Async database client singletons.

Startup order:
  1. SQLAlchemy (SQLite/Postgres) — always available
  2. Qdrant — local embedded if QDRANT_MODE=local, else server
  3. Neo4j — tries to connect; logs warning + disables graph agent if unreachable
  4. Redis — tries to connect; falls back to in-memory cache if unreachable
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── SQLAlchemy ────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# SQLite performance pragma listener
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if "sqlite" in settings.database_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # FastAPI dependency
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Qdrant ────────────────────────────────────────────────────────────────────
_qdrant_client = None


def get_qdrant():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        if settings.qdrant_mode == "local":
            try:
                _qdrant_client = QdrantClient(path=settings.qdrant_local_path)
                logger.info("Qdrant: local embedded mode at %s", settings.qdrant_local_path)
            except Exception as e:
                logger.warning("Qdrant local path locked (%s), falling back to in-memory Qdrant client", e)
                _qdrant_client = QdrantClient(":memory:")
        else:
            kwargs = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                kwargs["api_key"] = settings.qdrant_api_key
            _qdrant_client = QdrantClient(**kwargs)
            logger.info("Qdrant: server mode at %s", settings.qdrant_url)
    return _qdrant_client


# ── Neo4j ─────────────────────────────────────────────────────────────────────
_neo4j_driver = None
neo4j_available: bool = False


async def init_neo4j():
    global _neo4j_driver, neo4j_available
    try:
        from neo4j import AsyncGraphDatabase

        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await _neo4j_driver.verify_connectivity()
        neo4j_available = True
        logger.info("Neo4j: connected at %s", settings.neo4j_uri)
    except Exception as e:
        logger.warning(
            "Neo4j: not available (%s). Graph agent will be skipped — "
            "install Neo4j Community Edition to enable it.",
            e,
        )
        neo4j_available = False


def get_neo4j():
    return _neo4j_driver


# ── Redis ─────────────────────────────────────────────────────────────────────
_redis_client = None
_memory_cache: dict = {}  # fallback if Redis not running
redis_available: bool = False


async def init_redis():
    global _redis_client, redis_available
    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_client.ping()
        redis_available = True
        logger.info("Redis: connected at %s", settings.redis_url)
    except Exception as e:
        logger.warning(
            "Redis: not available (%s). Falling back to in-memory cache.", e
        )
        redis_available = False


async def cache_get(key: str) -> Optional[str]:
    if redis_available and _redis_client:
        return await _redis_client.get(key)

    val_tuple = _memory_cache.get(key)
    if val_tuple:
        value, expires = val_tuple
        if expires > time.time():
            return value
        else:
            del _memory_cache[key]
    return None


async def cache_set(key: str, value: str, ttl: int = 300):
    if redis_available and _redis_client:
        await _redis_client.set(key, value, ex=ttl)
    else:
        # Evict expired entries if cache is getting large (> 500 entries)
        if len(_memory_cache) > 500:
            now = time.time()
            expired_keys = [k for k, (_, exp) in _memory_cache.items() if exp <= now]
            for k in expired_keys:
                del _memory_cache[k]
            # If still over limit, evict oldest entries by expiry time
            if len(_memory_cache) > 500:
                sorted_keys = sorted(_memory_cache, key=lambda k: _memory_cache[k][1])
                for k in sorted_keys[:len(_memory_cache) - 400]:
                    del _memory_cache[k]
        _memory_cache[key] = (value, time.time() + ttl)


async def cleanup_expired_cache():
    """Purge all expired entries from the in-memory cache. Called periodically."""
    if redis_available:
        return  # Redis manages TTL natively
    now = time.time()
    expired = [k for k, (_, exp) in list(_memory_cache.items()) if exp <= now]
    for k in expired:
        _memory_cache.pop(k, None)
    if expired:
        logger.debug("In-memory cache: purged %d expired entries", len(expired))


# ── Lifecycle ─────────────────────────────────────────────────────────────────
async def startup():
    """Called from FastAPI lifespan — initialises all connections."""
    from app.models.event_log import Base as ModelBase  # noqa: F401 — registers models

    async with engine.begin() as conn:
        await conn.run_sync(ModelBase.metadata.create_all)
    logger.info("SQLAlchemy: tables created / verified")

    await init_neo4j()
    await init_redis()
    # Qdrant is initialised lazily on first use (get_qdrant())


async def shutdown():
    if _neo4j_driver:
        await _neo4j_driver.close()
    if redis_available and _redis_client:
        await _redis_client.close()
    await engine.dispose()
