"""
app/services/freshness.py — Automatic Re-Ingestion & Retraction Freshness Monitor (Feature 6).

Monitors ingested sources for updates, revisions, and retractions.
Protects against false contradictions caused by un-checked stale data.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.features import SourceRetraction

logger = logging.getLogger(__name__)


async def check_source_retractions_and_updates() -> List[Dict[str, Any]]:
    """
    Checks source database for retractions or official revisions.
    Returns list of active retraction notifications.
    """
    retractions_list = []
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(SourceRetraction).where(SourceRetraction.retraction_status != "resolved")
            res = await db.execute(stmt)
            retractions = res.scalars().all()

            for r in retractions:
                retractions_list.append({
                    "id": r.id,
                    "source_id": r.source_id,
                    "chunk_id": r.chunk_id,
                    "status": r.retraction_status,
                    "reason": r.reason,
                    "updated_at": r.updated_at.isoformat(),
                })
    except Exception as e:
        logger.warning("Error checking source retractions: %s", e)

    return retractions_list


async def mark_source_retraction(source_id: str, chunk_id: str, reason: str, status: str = "retracted") -> None:
    """Marks a source or chunk as retracted/revised to prevent stale contradiction false positives."""
    try:
        async with AsyncSessionLocal() as db:
            retraction = SourceRetraction(
                source_id=source_id,
                chunk_id=chunk_id,
                retraction_status=status,
                reason=reason,
            )
            db.add(retraction)
            await db.commit()
            logger.info("Marked SourceRetraction source=%s chunk=%s status=%s", source_id, chunk_id, status)
    except Exception as e:
        logger.warning("Failed to mark source retraction: %s", e)
