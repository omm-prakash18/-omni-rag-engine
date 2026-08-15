"""
app/services/consensus.py — Consensus Strength Indicator Service (A2).

Computes consensus metrics per entity claim group:
- Total independent sources reporting on the entity
- Count of sources agreeing on the majority value vs outlier sources
- Formats consensus summary string (e.g. "4 of 5 sources agree (80% Consensus); 1 outlier (Financial Times)")
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def compute_entity_consensus(candidate_group: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes consensus strength metrics for a single candidate claim group.
    """
    entity = candidate_group.get("entity", "Economic Indicator")
    claims = candidate_group.get("claims", [])

    if not claims:
        return {
            "entity": entity,
            "total_sources": 0,
            "consensus_pct": 100.0,
            "majority_value": "N/A",
            "agreeing_sources": [],
            "outlier_sources": [],
            "consensus_summary": "0 sources reporting",
        }

    # Group claims by claim value
    value_map: Dict[str, List[str]] = {}
    for c in claims:
        val = c.get("value", "N/A")
        src = c.get("source_name", "Unknown")
        if val not in value_map:
            value_map[val] = []
        if src not in value_map[val]:
            value_map[val].append(src)

    all_sources = set(c.get("source_name", "Unknown") for c in claims)
    total_sources_count = len(all_sources)

    # Find value with highest source agreement
    majority_val = max(value_map.keys(), key=lambda v: len(value_map[v]))
    agreeing_srcs = value_map[majority_val]
    agreeing_count = len(agreeing_srcs)

    outlier_srcs = [src for src in all_sources if src not in agreeing_srcs]
    outlier_count = len(outlier_srcs)

    consensus_pct = round((agreeing_count / max(total_sources_count, 1)) * 100.0, 1)

    if outlier_count == 0:
        summary = f"Full Consensus: {agreeing_count} of {total_sources_count} sources agree on {majority_val} (100% Consensus)"
    else:
        outlier_names = ", ".join(outlier_srcs[:2])
        if outlier_count > 2:
            outlier_names += f" (+{outlier_count - 2} more)"
        summary = (
            f"{agreeing_count} of {total_sources_count} sources agree on {majority_val} "
            f"({consensus_pct}% Consensus); {outlier_count} outlier source{'s' if outlier_count > 1 else ''} ({outlier_names})"
        )

    return {
        "entity": entity,
        "total_sources": total_sources_count,
        "consensus_pct": consensus_pct,
        "majority_value": majority_val,
        "agreeing_sources": agreeing_srcs,
        "outlier_sources": outlier_srcs,
        "consensus_summary": summary,
    }


def compute_all_consensus(candidate_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute consensus strength indicators across all candidate claim groups."""
    return [compute_entity_consensus(group) for group in candidate_groups]
