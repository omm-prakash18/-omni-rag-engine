"""
app/services/topic_scheduler.py — Topic Tracking & Snapshot Diff Service (A4).

Re-queries saved user topics on an interval and diffs the claim graph snapshot against the previous state.
Generates alerts ONLY on meaningful changes:
- New contradiction appeared
- Existing contradiction resolved
- Consensus score shifted significantly (>= 15%)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.features import TopicAlert, TrackedTopic

logger = logging.getLogger(__name__)


def _diff_graph_snapshots(
    old_snapshot: Optional[Dict[str, Any]],
    new_response: Any
) -> List[Dict[str, Any]]:
    """
    Diffs current QueryResponse against previous saved graph snapshot.
    Returns list of material alert dicts (empty if no material change).
    """
    if not old_snapshot:
        return []  # Initial baseline snapshot saved — no alert on first run

    old_contradiction_ids = set(c.get("id") for c in old_snapshot.get("contradictions", []) if c.get("id"))
    new_contradiction_ids = set(c.id for c in new_response.contradictions)

    alerts = []

    # 1. Check for New Contradictions
    added_ids = new_contradiction_ids - old_contradiction_ids
    if added_ids:
        new_c_objs = [c for c in new_response.contradictions if c.id in added_ids]
        for c in new_c_objs:
            alerts.append({
                "alert_type": "new_contradiction",
                "summary": f"New contradiction detected on '{c.entity}': {c.source_a.source_name} vs {c.source_b.source_name} ({c.metric})",
                "details": json.dumps({"entity": c.entity, "type": c.contradiction_type.value, "reason": c.reason}),
            })

    # 2. Check for Resolved Contradictions
    removed_ids = old_contradiction_ids - new_contradiction_ids
    if removed_ids:
        old_c_objs = [c for c in old_snapshot.get("contradictions", []) if c.get("id") in removed_ids]
        for c in old_c_objs:
            alerts.append({
                "alert_type": "resolved_contradiction",
                "summary": f"Contradiction resolved on '{c.get('entity', 'Indicator')}': Sources now align or report consistent figures.",
                "details": json.dumps({"entity": c.get("entity"), "previous_metric": c.get("metric")}),
            })

    # 3. Check for Consensus Score Shift (>= 15% shift)
    old_consensus_pct = old_snapshot.get("consensus_pct", 100.0)
    new_consensus_summary = getattr(new_response, "consensus_summary", None) or {}
    new_consensus_pct = new_consensus_summary.get("consensus_pct", 100.0)

    shift = abs(new_consensus_pct - old_consensus_pct)
    if shift >= 15.0:
        alerts.append({
            "alert_type": "consensus_shift",
            "summary": f"Consensus score shifted by {round(shift, 1)}%: from {old_consensus_pct}% to {new_consensus_pct}%.",
            "details": json.dumps({"old_pct": old_consensus_pct, "new_pct": new_consensus_pct, "summary": new_consensus_summary.get("summary")}),
        })

    return alerts


async def run_topic_check(topic_id: str, db: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
    """
    Executes a re-query check for a tracked topic, diffs graph snapshot, and persists material alerts.
    """
    from app.agents.pipeline import run_omni_pipeline

    close_session = False
    if db is None:
        db = AsyncSessionLocal()
        close_session = True

    try:
        stmt = select(TrackedTopic).where(TrackedTopic.id == topic_id)
        res = await db.execute(stmt)
        topic = res.scalar_one_or_none()

        if not topic or not topic.active:
            return []

        # Run pipeline query for the topic
        query_text = topic.topic_name
        current_res = await run_omni_pipeline(query_text)

        old_snapshot = json.loads(topic.last_graph_snapshot) if topic.last_graph_snapshot else None

        # Calculate diff alerts
        alerts_data = _diff_graph_snapshots(old_snapshot, current_res)

        # Build new snapshot payload
        new_snapshot_payload = {
            "query": query_text,
            "contradictions": [c.model_dump(mode="json") for c in current_res.contradictions],
            "consensus_pct": getattr(current_res, "consensus_summary", {}).get("consensus_pct", 100.0) if hasattr(current_res, "consensus_summary") else 100.0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        # Update topic state
        topic.last_graph_snapshot = json.dumps(new_snapshot_payload)
        topic.last_run_at = datetime.now(timezone.utc)

        # Save material alerts
        created_alerts = []
        for a in alerts_data:
            alert_obj = TopicAlert(
                topic_id=topic.id,
                alert_type=a["alert_type"],
                summary=a["summary"],
                details=a.get("details"),
            )
            db.add(alert_obj)
            created_alerts.append(a)

        await db.commit()
        logger.info("Topic check completed for '%s' (topic_id=%s): %d alerts generated.", topic.topic_name, topic.id, len(created_alerts))
        return created_alerts

    finally:
        if close_session:
            await db.close()
