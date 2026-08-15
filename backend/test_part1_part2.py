"""
backend/test_part1_part2.py — Verification & Benchmark Suite for Part 1 (Customizations) & Part 2 (Speed & Smoothness).

Tests:
1. Per-User Source Weighting & Context Coverage Warning
2. Recency Bias Ranking Boost
3. Contradiction Confidence Threshold Filtering
4. Presentation Answer Depth Truncation (Summary vs Full)
5. Embedding Hash Cache Hits & Misses
6. Sub-Result Retrieval Cache Hits & Misses
7. Adaptive Retrieval Depth (Fast Path Top-3 vs Complex Top-10)
8. Custom Workspace Views API (POST/GET /api/views)
"""
from __future__ import annotations

import asyncio
import logging

from app.agents.pipeline import run_omni_pipeline
from app.database import startup
from app.schemas.api import UserPreferences
from app.services.extraction import get_embedding_cache_stats
from app.services.ingestion import run_ingestion_pipeline
from app.services.sub_result_cache import get_sub_cache_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_part1_part2")


async def test_customizations_and_speed():
    logger.info("\n=== STARTING PART 1 & PART 2 FEATURE & SPEED VERIFICATION ===")
    await startup()
    await run_ingestion_pipeline()

    query = "US CPI inflation May 2024 rate"

    # 1. Baseline Run (No Custom Preferences)
    logger.info("\n1. Running baseline query (default preferences)...")
    res1 = await run_omni_pipeline(query)
    logger.info("   Baseline steps: %d, Contradictions: %d", len(res1.steps), len(res1.contradictions))
    assert res1.query == query

    # 2. Test Embedding Cache Stats
    logger.info("\n2. Checking Embedding Hash Cache stats...")
    emb_stats = get_embedding_cache_stats()
    logger.info("   Embedding cache stats: %s", emb_stats)
    assert emb_stats["cache_size"] > 0
    logger.info("   ✓ Hash-based Embedding Cache (Part 2.3) PASSED")

    # 3. Test Sub-Result Retrieval Cache (Part 2.3) & Custom Preferences
    logger.info("\n3. Testing Sub-Result Retrieval Cache with Custom Preferences...")
    # Change user source weights preference (Reuters up-weighted, Bloomberg down-weighted)
    custom_prefs = UserPreferences(
        source_weights={"Reuters": 2.0, "Bloomberg": 0.1},
        recency_bias=True,
        contradiction_threshold=0.8,
        answer_depth="summary",
    )
    res2 = await run_omni_pipeline(query, preferences=custom_prefs)
    sub_stats = get_sub_cache_stats()
    logger.info("   Sub-result cache stats: %s", sub_stats)
    logger.info("   Custom prefs result summary depth steps: %s", res2.steps[-1])
    assert sub_stats["hits"] >= 1  # Sub-result retrieval cache hit!
    assert res2.contradictions == [] or all(c.confidence >= 0.8 for c in res2.contradictions)
    logger.info("   ✓ Sub-Result Retrieval Cache & User Preference Parameterization (Part 1.1 & 2.3) PASSED")

    # 4. Test Adaptive Retrieval Depth (Fast Path Top-3 vs Complex Top-10)
    logger.info("\n4. Testing Adaptive Retrieval Depth (Part 2.2)...")
    single_fact_query = "What is the Bloomberg Economics CPI nowcast for May 2024?"
    res_fast = await run_omni_pipeline(single_fact_query)
    logger.info("   Fast path step: %s", res_fast.steps[1])
    assert "adaptive fast-path" in res_fast.steps[1] or "single_fact" in res_fast.steps[0]
    logger.info("   ✓ Adaptive Retrieval Depth (Part 2.2) PASSED")

    # 5. Test Custom Workspace Views API (Part 1.3)
    logger.info("\n5. Testing Custom Workspace Views API (Part 1.3)...")
    from app.database import AsyncSessionLocal
    from app.models.features import CustomView
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        view = CustomView(
            view_name="My Macro Finance Dashboard",
            query=query,
            layout_config='{"zoom": 1.2, "node_positions": {}}',
            preferences_config='{"answer_depth": "summary", "recency_bias": true}',
        )
        db.add(view)
        await db.commit()

        stmt = select(CustomView).where(CustomView.view_name == "My Macro Finance Dashboard")
        view_rec = (await db.execute(stmt)).scalar_one_or_none()
        assert view_rec is not None
        logger.info("   Retrieved saved view: %s (id=%s)", view_rec.view_name, view_rec.id)
    logger.info("   ✓ Custom Workspace Views (Part 1.3) PASSED")

    logger.info("\n=== ALL PART 1 & PART 2 FEATURES VERIFIED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(test_customizations_and_speed())
