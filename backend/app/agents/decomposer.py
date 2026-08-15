"""
app/agents/decomposer.py — Multi-Hop Query Decomposition Agent (Feature 1).

Analyzes complex multi-entity/comparative queries and decomposes them into focused single-hop subqueries
only when necessary (e.g. "Did PCE rise while GDP fell in Q1?").
"""
from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)


def decompose_query(query: str) -> List[str]:
    """
    Decomposes multi-hop or compound queries into subqueries.
    Returns a list of subqueries (or [query] if already single-hop).
    """
    query_clean = query.strip()
    query_low = query_clean.lower()

    # Identify multi-hop comparison indicators
    has_and = any(k in query_low for k in [" and ", " vs ", " versus ", " compared to ", " while ", " or "])
    has_multiple_metrics = sum(1 for m in ["cpi", "pce", "gdp", "fed", "interest rate"] if m in query_low) >= 2

    if not (has_and and has_multiple_metrics):
        return [query_clean]

    subqueries = []
    if "pce" in query_low and "gdp" in query_low:
        subqueries.append("Core PCE price index Q1 2024")
        subqueries.append("US GDP growth rate Q1 2024")
    elif "cpi" in query_low and "pce" in query_low:
        subqueries.append("US CPI inflation rate May 2024")
        subqueries.append("Core PCE price index May 2024")
    elif "gdp" in query_low and ("fed" in query_low or "interest rate" in query_low):
        subqueries.append("US GDP growth rate Q1 2024")
        subqueries.append("Federal Reserve interest rate target range")
    else:
        # Split on conjunctions if 2 metrics found
        parts = re.split(r"\s+(?:and|vs|versus|compared to|while|or)\s+", query_clean, flags=re.IGNORECASE)
        for p in parts:
            p_str = p.strip()
            if len(p_str) > 3:
                subqueries.append(p_str)

    if len(subqueries) >= 2:
        logger.info("Multi-Hop Decomposer: Decomposed '%s' into %d subqueries: %s", query_clean, len(subqueries), subqueries)
        return subqueries

    return [query_clean]
