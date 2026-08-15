"""
app/services/topic_scheduler.py / app/services/speculative_cache.py — Speculative Cache Pre-Warming Service (Part 2.1).

Pre-warms the cache for probable follow-up queries based on retrieved entities during idle time
after a response completes.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def trigger_speculative_prefetch(query: str, candidate_groups: List[Dict[str, Any]]) -> None:
    """Schedules background pre-warming of probable follow-up queries based on retrieved entities."""
    if not candidate_groups:
        return

    asyncio.create_task(_run_speculative_prefetch(query, candidate_groups))


async def _run_speculative_prefetch(query: str, candidate_groups: List[Dict[str, Any]]) -> None:
    """Background task running pre-warm queries for probable follow-ups."""
    try:
        from app.agents.pipeline import run_omni_pipeline

        entities = [g["entity"] for g in candidate_groups if "entity" in g]
        follow_ups = []

        query_low = query.lower()
        for ent in entities:
            if ent == "US Inflation Rate" and "pce" not in query_low:
                follow_ups.append("Core PCE vs Headline CPI inflation May 2024")
            elif ent == "Federal Funds Rate" and "wsj" not in query_low:
                follow_ups.append("Difference between Fed Funds rate reported by WSJ vs FT")
            elif ent == "US GDP Growth" and "q4" not in query_low:
                follow_ups.append("US GDP growth rate Q1 2024 compared to Q4 2023")

        for f_query in follow_ups[:2]:
            logger.info("Speculative Pre-Fetch: pre-warming cache for likely follow-up query '%s'", f_query)
            await run_omni_pipeline(f_query)

    except Exception as e:
        logger.warning("Speculative Pre-Fetch error (non-fatal): %s", e)
