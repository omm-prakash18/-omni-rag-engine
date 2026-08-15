"""
app/services/cache.py — Shared In-Memory Query & Entity Cache.

Caches pipeline results keyed on query normalization & hashing to eliminate redundant
retrieval and LLM calls for near-duplicate queries within a session.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_QUERY_CACHE: Dict[str, Any] = {}
_MAX_CACHE_SIZE = 256


def _normalize_query_key(query: str) -> str:
    """Compute normalized hash key for a query string."""
    clean = re.sub(r"\s+", " ", query.strip().lower())
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


def get_cached_response(query: str) -> Optional[Any]:
    """Retrieve cached QueryResponse if available."""
    key = _normalize_query_key(query)
    cached = _QUERY_CACHE.get(key)
    if cached:
        logger.info("Pipeline Cache HIT for query '%s'", query)
        return cached
    return None


def set_cached_response(query: str, response: Any) -> None:
    """Store QueryResponse in cache."""
    key = _normalize_query_key(query)
    if len(_QUERY_CACHE) >= _MAX_CACHE_SIZE:
        # Evict oldest entry
        oldest_key = next(iter(_QUERY_CACHE))
        _QUERY_CACHE.pop(oldest_key, None)
    _QUERY_CACHE[key] = response
    logger.info("Pipeline Cache SET for query '%s'", query)


def clear_cache() -> None:
    """Clear all entries in the pipeline cache."""
    _QUERY_CACHE.clear()
    logger.info("Pipeline Cache cleared.")
