"""
app/models/features.py — SQLAlchemy ORM models for Phase A features.

Models:
- SourceReliability: Per-outlet historical accuracy tracking from real outcomes
- UserFlag: User-flaggable corrections queue for human audit
- TrackedTopic: User saved topics for change monitoring
- TopicAlert: Material change notifications generated from snapshot diffing
- ApiKey: API key credentials and rate limit tracking
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
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# ── 1. Source Reliability Table ──────────────────────────────────────────────
class SourceReliability(Base):
    """Tracks historical accuracy & retractions per outlet based on tracked outcomes."""

    __tablename__ = "source_reliability"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    
    total_claims_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_held_up: Mapped[int] = mapped_column(Integer, default=0)
    confirmed_wrong: Mapped[int] = mapped_column(Integer, default=0)
    retractions_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Reliability score (0.0 to 100.0) or None if total_claims_analyzed < 3
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ── 2. User Flaggable Corrections Queue ──────────────────────────────────────
class UserFlag(Base):
    """Human review queue for user-reported contradiction & scope flags."""

    __tablename__ = "user_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    edge_id: Mapped[Optional[str]] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(200), nullable=False)
    source_a: Mapped[str] = mapped_column(String(100), nullable=False)
    source_b: Mapped[str] = mapped_column(String(100), nullable=False)
    user_note: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|reviewed|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ── 3. Topic Tracking & Snapshot Diffs ───────────────────────────────────────
class TrackedTopic(Base):
    """Saved topics re-queried periodically to detect material claim graph shifts."""

    __tablename__ = "tracked_topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(100), default="default_user")
    topic_name: Mapped[str] = mapped_column(String(200), nullable=False)  # Entity or query string
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_graph_snapshot: Mapped[Optional[str]] = mapped_column(Text)  # JSON representation of GraphData
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    alerts: Mapped[list["TopicAlert"]] = relationship(back_populates="topic")


class TopicAlert(Base):
    """Notification generated ONLY when material changes occur on a tracked topic."""

    __tablename__ = "topic_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("tracked_topics.id"), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # new_contradiction|resolved_contradiction|consensus_shift
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)  # JSON payload of diff
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    topic: Mapped["TrackedTopic"] = relationship(back_populates="alerts")


# ── 4. API Keys & External Rate Limiting ─────────────────────────────────────
class ApiKey(Base):
    """API key credentials for external read-only REST access."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)  # First few chars for display
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, default=60)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
