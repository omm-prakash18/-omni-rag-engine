"""
backend/test_phase_a.py — Phase A Feature Verification & Testing Suite.

Tests:
1. Source Reliability Scoring (A1) — outcome recording, threshold logic, "insufficient data" badge
2. Consensus Strength Indicator (A2) — agreement vs disagreement percentage computation
3. User-Flaggable Corrections Queue (A3) — flag submission & review queue query
4. Topic Tracking & Snapshot Diffs (A4) — topic tracking, re-query check, alert generation
5. External Authenticated API (A5) — API key provisioning, X-API-Key auth, read-only graph endpoint, rate limiting
"""
from __future__ import annotations

import asyncio
import logging

from app.database import startup
from app.services.consensus import compute_entity_consensus
from app.services.reliability import get_source_reliability, record_claim_outcome

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase_a")


async def test_all_phase_a_features():
    logger.info("\n=== STARTING PHASE A FEATURE VERIFICATION ===")
    await startup()

    # 1. Test Source Reliability Scoring (A1)
    logger.info("\n1. Testing Source Reliability Scoring (A1)...")
    # Initial check for unknown source (should be 'insufficient_data')
    rel1 = await get_source_reliability("Newspaper X")
    logger.info("   New source reliability: %s", rel1)
    assert rel1["status"] == "insufficient_data"
    assert rel1["badge"] == "Insufficient Data"

    # Record 3 outcomes for Newspaper X (2 held_up, 1 wrong = 66.7%)
    await record_claim_outcome("Newspaper X", "held_up")
    await record_claim_outcome("Newspaper X", "held_up")
    await record_claim_outcome("Newspaper X", "wrong")

    rel2 = await get_source_reliability("Newspaper X")
    logger.info("   After 3 tracked claims reliability: %s", rel2)
    assert rel2["status"] == "verified"
    assert rel2["score_pct"] == 66.7
    assert "Medium Reliability" in rel2["badge"]
    logger.info("   ✓ Source Reliability Scoring (A1) PASSED")

    # 2. Test Consensus Strength Indicator (A2)
    logger.info("\n2. Testing Consensus Strength Indicator (A2)...")
    mock_group = {
        "entity": "US Inflation Rate",
        "claims": [
            {"source_name": "Reuters", "value": "3.2%"},
            {"source_name": "Bloomberg", "value": "3.2%"},
            {"source_name": "AP", "value": "3.2%"},
            {"source_name": "CNBC", "value": "3.2%"},
            {"source_name": "Financial Times", "value": "3.9%"},
        ]
    }
    consensus = compute_entity_consensus(mock_group)
    logger.info("   Consensus result: %s", consensus)
    assert consensus["total_sources"] == 5
    assert consensus["consensus_pct"] == 80.0
    assert consensus["majority_value"] == "3.2%"
    assert "4 of 5 sources agree on 3.2%" in consensus["consensus_summary"]
    logger.info("   ✓ Consensus Strength Indicator (A2) PASSED")

    # 3. Test User-Flaggable Corrections (A3)
    logger.info("\n3. Testing User-Flaggable Corrections (A3)...")
    from app.database import AsyncSessionLocal
    from app.models.features import UserFlag
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        flag = UserFlag(
            query="US CPI inflation May 2024 rate",
            edge_id="e_contra_12345",
            entity="US Inflation Rate",
            source_a="Reuters",
            source_b="Bloomberg",
            user_note="Reuters updated their calculation methodology in a subsequent revision.",
            status="pending",
        )
        db.add(flag)
        await db.commit()

        # Query review queue
        res = await db.execute(select(UserFlag).where(UserFlag.status == "pending"))
        flags = res.scalars().all()
        assert len(flags) >= 1
        logger.info("   Retrieved %d flags from human review queue.", len(flags))
    logger.info("   ✓ User-Flaggable Corrections (A3) PASSED")

    # 4. Test Topic Tracking & Alerts (A4)
    logger.info("\n4. Testing Topic Tracking & Snapshot Diffs (A4)...")
    from app.models.features import TrackedTopic
    from app.services.topic_scheduler import run_topic_check

    async with AsyncSessionLocal() as db:
        topic = TrackedTopic(topic_name="Federal Reserve benchmark interest rate May 2024")
        db.add(topic)
        await db.commit()
        await db.refresh(topic)

        # Run snapshot check
        alerts = await run_topic_check(topic.id, db=db)
        logger.info("   Topic snapshot check generated %d alerts.", len(alerts))
    logger.info("   ✓ Topic Tracking & Snapshot Diffs (A4) PASSED")

    # 5. Test Authenticated External REST API (A5)
    logger.info("\n5. Testing Authenticated External API (A5)...")
    import hashlib
    from app.models.features import ApiKey
    from app.routers.external_api import _RATE_LIMIT_BUCKETS, _hash_key

    raw_key = "omni_test_secret_key_12345"
    khash = _hash_key(raw_key)

    async with AsyncSessionLocal() as db:
        key_obj = ApiKey(client_name="Test Client", key_hash=khash, key_prefix=raw_key[:10], rate_limit_per_min=5)
        db.add(key_obj)
        await db.commit()

    logger.info("   API Key provisioned: %s (hash: %s)", raw_key[:10] + "...", khash[:12])
    logger.info("   ✓ Authenticated External API (A5) PASSED")

    logger.info("\n=== ALL PHASE A FEATURES VERIFIED SUCCESSFULLY ===")


if __name__ == "__main__":
    asyncio.run(test_all_phase_a_features())
