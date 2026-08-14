"""
app/models/event_log.py — SQLAlchemy ORM models.

Postgres-compatible schema; runs on SQLite via aiosqlite in development.
Postgres JSON → SQLite TEXT for claimed_scope (serialised as JSON string).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Source ────────────────────────────────────────────────────────────────────
class Source(Base):
    """A news/data source (Reuters, Bloomberg, NewsAPI, etc.)."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    api_type: Mapped[str] = mapped_column(String(50), default="newsapi")
    base_url: Mapped[Optional[str]] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["EventLog"]] = relationship(back_populates="source")
    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")


# ── Event Log (chunks) ────────────────────────────────────────────────────────
class EventLog(Base):
    """
    Single source-of-truth for every ingested chunk.
    Both Qdrant points and Neo4j nodes reference this row's id.
    """

    __tablename__ = "event_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id"), nullable=True
    )

    # Content
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(200))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Enrichment
    sentiment: Mapped[Optional[float]] = mapped_column(Float)  # [-1, 1]
    # claimed_scope stored as JSON string for SQLite compatibility
    claimed_scope: Mapped[Optional[str]] = mapped_column(Text)  # JSON: {date_range, geography, methodology}

    # Status
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|retracted|superseded

    # Sync flags (write-path tracking)
    qdrant_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    neo4j_synced: Mapped[bool] = mapped_column(Boolean, default=False)
    embedding_model: Mapped[Optional[str]] = mapped_column(String(100))

    source: Mapped[Optional["Source"]] = relationship(back_populates="chunks")


# ── Ingestion Jobs ────────────────────────────────────────────────────────────
class IngestionJob(Base):
    """Tracks each polling run — for /ingest/status endpoint."""

    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("sources.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    articles_fetched: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|done|error
    error: Mapped[Optional[str]] = mapped_column(Text)

    source: Mapped[Optional["Source"]] = relationship(back_populates="jobs")
