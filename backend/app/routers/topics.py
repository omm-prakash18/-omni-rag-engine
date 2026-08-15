"""
app/routers/topics.py — Topic Tracking & Change Alerts API (A4).

Allows users to save topics (entities or queries) for scheduled change monitoring.
Notifies ONLY on material graph changes (new contradiction, resolved contradiction, consensus shift).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.features import TopicAlert, TrackedTopic
from app.services.topic_scheduler import run_topic_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/topics", tags=["topics"])


class TrackedTopicCreate(BaseModel):
    topic_name: str = Field(min_length=2, max_length=200)  # Entity or query string
    interval_minutes: int = Field(default=60, ge=5, le=10080)


class TrackedTopicResponse(BaseModel):
    id: str
    user_id: str
    topic_name: str
    interval_minutes: int
    last_run_at: Optional[str]
    active: bool
    created_at: str


class TopicAlertResponse(BaseModel):
    id: str
    topic_id: str
    topic_name: str
    alert_type: str
    summary: str
    details: Optional[str]
    created_at: str


@router.post("", response_model=TrackedTopicResponse, status_code=status.HTTP_201_CREATED)
async def create_tracked_topic(payload: TrackedTopicCreate, db: AsyncSession = Depends(get_db)):
    """Save a new topic for background change tracking."""
    topic = TrackedTopic(
        topic_name=payload.topic_name,
        interval_minutes=payload.interval_minutes,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    # Trigger initial snapshot run
    await run_topic_check(topic.id, db=db)
    await db.refresh(topic)

    return TrackedTopicResponse(
        id=topic.id,
        user_id=topic.user_id,
        topic_name=topic.topic_name,
        interval_minutes=topic.interval_minutes,
        last_run_at=topic.last_run_at.isoformat() if topic.last_run_at else None,
        active=topic.active,
        created_at=topic.created_at.isoformat(),
    )


@router.get("", response_model=List[TrackedTopicResponse])
async def list_tracked_topics(db: AsyncSession = Depends(get_db)):
    """List all tracked topics."""
    stmt = select(TrackedTopic).order_by(TrackedTopic.created_at.desc())
    res = await db.execute(stmt)
    topics = res.scalars().all()

    return [
        TrackedTopicResponse(
            id=t.id,
            user_id=t.user_id,
            topic_name=t.topic_name,
            interval_minutes=t.interval_minutes,
            last_run_at=t.last_run_at.isoformat() if t.last_run_at else None,
            active=t.active,
            created_at=t.created_at.isoformat(),
        )
        for t in topics
    ]


@router.get("/alerts", response_model=List[TopicAlertResponse])
async def list_topic_alerts(db: AsyncSession = Depends(get_db)):
    """Retrieve material change alerts generated across all tracked topics."""
    stmt = (
        select(TopicAlert, TrackedTopic.topic_name)
        .join(TrackedTopic, TopicAlert.topic_id == TrackedTopic.id)
        .order_by(TopicAlert.created_at.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    return [
        TopicAlertResponse(
            id=alert.id,
            topic_id=alert.topic_id,
            topic_name=topic_name,
            alert_type=alert.alert_type,
            summary=alert.summary,
            details=alert.details,
            created_at=alert.created_at.isoformat(),
        )
        for alert, topic_name in rows
    ]


@router.post("/{topic_id}/check")
async def trigger_topic_check(topic_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger snapshot re-query check and diff for a topic."""
    alerts = await run_topic_check(topic_id, db=db)
    return {
        "status": "success",
        "topic_id": topic_id,
        "alerts_generated": len(alerts),
        "alerts": alerts,
    }
