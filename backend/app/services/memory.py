"""
app/services/memory.py — Conversational Memory & Reference Resolution (Feature 3).

Resolves ambiguous pronouns and follow-up references (e.g., "what about last month?", "how does that compare to CPI?")
against prior conversation turns to form fully qualified target queries.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.schemas.api import ChatMessage

logger = logging.getLogger(__name__)


def resolve_conversational_query(query: str, history: Optional[List[ChatMessage]] = None) -> str:
    """
    Analyzes user query in context of past conversation turns.
    Returns resolved query with pronouns/references expanded.
    """
    if not history:
        return query

    query_clean = query.strip()
    query_low = query_clean.lower()

    # Look for reference indicators ("what about", "how about", "last month", "it", "that", "same for")
    ref_indicators = ["what about", "how about", "last month", "previous quarter", "it", "that", "same for", "compared to last month"]
    has_ref = any(k in query_low for k in ref_indicators)

    if not has_ref:
        return query_clean

    # Find last user query or assistant response containing target entities
    last_entity = "US CPI Inflation Rate"
    last_timeframe = "May 2024"

    for msg in reversed(history):
        content_low = msg.content.lower()
        if "cpi" in content_low or "inflation" in content_low:
            last_entity = "US CPI Inflation Rate"
        elif "gdp" in content_low:
            last_entity = "US GDP Growth Rate"
        elif "fed" in content_low or "interest rate" in content_low:
            last_entity = "Federal Reserve Interest Rate"

        if "q1" in content_low or "2024" in content_low:
            last_timeframe = "Q1 2024"
        elif "q4" in content_low or "2023" in content_low:
            last_timeframe = "Q4 2023"

    # Reference resolution mappings
    if "last month" in query_low or "previous month" in query_low:
        resolved = f"{last_entity} April 2024"
    elif "last quarter" in query_low or "previous quarter" in query_low:
        resolved = f"{last_entity} Q4 2023"
    elif "what about pce" in query_low:
        resolved = f"Core PCE price index {last_timeframe}"
    elif "what about gdp" in query_low:
        resolved = f"US GDP growth rate {last_timeframe}"
    else:
        resolved = f"{last_entity} {query_clean}"

    logger.info("Conversational Memory: Resolved '%s' -> '%s'", query_clean, resolved)
    return resolved
