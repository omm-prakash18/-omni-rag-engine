"""
app/services/reliability.py — Source Reliability Scoring Service (A1).

Computes source accuracy & reliability badges from actual tracked outcomes in database.
Does NOT hardcode reputation assumptions — returns "insufficient data" for outlets with < 3 tracked claims.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.features import SourceReliability

logger = logging.getLogger(__name__)

# Default in-memory cache for synchronous fast graph-node decoration
_RELIABILITY_CACHE: Dict[str, Dict[str, Any]] = {}


async def get_source_reliability(source_name: str, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """
    Retrieves reliability metrics for a given source outlet.
    If total_claims_analyzed < 3, returns 'insufficient_data' score.
    """
    s_name = source_name.strip()

    close_session = False
    if db is None:
        db = AsyncSessionLocal()
        close_session = True

    try:
        stmt = select(SourceReliability).where(SourceReliability.source_name == s_name)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record or record.total_claims_analyzed < 3:
            result = {
                "source_name": s_name,
                "total_claims_analyzed": record.total_claims_analyzed if record else 0,
                "score_pct": None,
                "status": "insufficient_data",
                "badge": "Insufficient Data",
            }
        else:
            # Score formula: held_up / (held_up + wrong)
            valid_outcomes = record.confirmed_held_up + record.confirmed_wrong
            score_val = (record.confirmed_held_up / max(valid_outcomes, 1)) * 100.0 if valid_outcomes > 0 else 100.0
            
            # Apply slight penalty for retractions if present
            if record.retractions_count > 0:
                score_val = max(0.0, score_val - (record.retractions_count * 5.0))

            score_val = round(score_val, 1)

            if score_val >= 85.0:
                badge = f"High Reliability ({score_val}%)"
            elif score_val >= 65.0:
                badge = f"Medium Reliability ({score_val}%)"
            else:
                badge = f"Low Reliability ({score_val}%)"

            result = {
                "source_name": s_name,
                "total_claims_analyzed": record.total_claims_analyzed,
                "score_pct": score_val,
                "status": "verified",
                "badge": badge,
            }

        _RELIABILITY_CACHE[s_name] = result
        return result
    finally:
        if close_session:
            await db.close()


def get_cached_reliability_badge(source_name: str) -> Dict[str, Any]:
    """Synchronous lookup from in-memory cache for fast graph node enrichment."""
    return _RELIABILITY_CACHE.get(source_name, {
        "source_name": source_name,
        "total_claims_analyzed": 0,
        "score_pct": None,
        "status": "insufficient_data",
        "badge": "Insufficient Data",
    })


async def record_claim_outcome(
    source_name: str,
    outcome: str,  # "held_up" | "wrong" | "retracted"
    db: Optional[AsyncSession] = None,
) -> None:
    """Record an audited claim outcome for a source outlet."""
    s_name = source_name.strip()
    close_session = False
    if db is None:
        db = AsyncSessionLocal()
        close_session = True

    try:
        stmt = select(SourceReliability).where(SourceReliability.source_name == s_name)
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            record = SourceReliability(source_name=s_name, total_claims_analyzed=0, confirmed_held_up=0, confirmed_wrong=0, retractions_count=0)
            db.add(record)

        record.total_claims_analyzed += 1
        if outcome == "held_up":
            record.confirmed_held_up += 1
        elif outcome == "wrong":
            record.confirmed_wrong += 1
        elif outcome == "retracted":
            record.retractions_count += 1

        # Update computed score if claims >= 3
        valid_outcomes = record.confirmed_held_up + record.confirmed_wrong
        if record.total_claims_analyzed >= 3 and valid_outcomes > 0:
            score = (record.confirmed_held_up / valid_outcomes) * 100.0
            if record.retractions_count > 0:
                score = max(0.0, score - (record.retractions_count * 5.0))
            record.score = round(score, 1)

        await db.commit()
        logger.info("Updated SourceReliability for '%s' (outcome=%s, total=%d)", s_name, outcome, record.total_claims_analyzed)
    finally:
        if close_session:
            await db.close()
