"""
app/services/personalized_ranking.py — Personalized Interaction Ranking Service (Feature 4).

Tracks user interaction signal (clicks, helpful flags) and computes bounded ranking boosts (max 1.2x multiplier)
to personalize search results without overfitting or introducing quiet bias.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.features import UserInteraction

logger = logging.getLogger(__name__)


async def record_user_interaction(user_id: str, chunk_id: str, query: str, action_type: str = "click") -> None:
    """Records user interaction signal for personalized ranking."""
    if not user_id or not chunk_id:
        return

    try:
        async with AsyncSessionLocal() as db:
            interaction = UserInteraction(
                user_id=user_id,
                chunk_id=chunk_id,
                query=query,
                action_type=action_type,
                score_delta=0.15 if action_type == "helpful" else 0.05,
            )
            db.add(interaction)
            await db.commit()
            logger.info("Recorded UserInteraction user=%s chunk=%s action=%s", user_id, chunk_id, action_type)
    except Exception as e:
        logger.warning("UserInteraction recording failed (non-fatal): %s", e)


async def get_user_interaction_boosts(user_id: Optional[str], chunk_ids: List[str]) -> Dict[str, float]:
    """
    Computes bounded score boost multipliers per chunk for a user (range: 1.0x to 1.2x max).
    Bounded to prevent low-volume overfitting.
    """
    if not user_id or not chunk_ids:
        return {cid: 1.0 for cid in chunk_ids}

    boosts: Dict[str, float] = {cid: 1.0 for cid in chunk_ids}
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(UserInteraction).where(
                UserInteraction.user_id == user_id,
                UserInteraction.chunk_id.in_(chunk_ids),
            )
            res = await db.execute(stmt)
            interactions = res.scalars().all()

            for item in interactions:
                current = boosts.get(item.chunk_id, 1.0)
                # Cap maximum multiplier at 1.2x to prevent quiet bias/overfitting
                boosts[item.chunk_id] = min(1.20, round(current + item.score_delta, 2))
    except Exception as e:
        logger.warning("Error fetching interaction boosts: %s", e)

    return boosts
