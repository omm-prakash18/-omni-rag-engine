"""
app/services/sub_result_cache.py — Sub-Result Retrieval Caching Service (Part 2.3).

Caches raw Vector Agent and Graph Agent retrieval results independently,
keyed on (query_text, domain_scope, top_k).

Benefit: When a user modifies preference parameters (source_weights, recency_bias, answer_depth),
the pipeline reuses the cached raw retrieval sub-results without hitting Qdrant or Neo4j again!
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_VECTOR_SUB_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_GRAPH_SUB_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_SUB_CACHE_HITS: int = 0
_SUB_CACHE_MISSES: int = 0


def _build_sub_key(query: str, domain_scope: Optional[List[str]], top_k: int) -> str:
    scope_str = ",".join(sorted(domain_scope)) if domain_scope else "global"
    raw_key = f"{query.strip().lower()}:{scope_str}:{top_k}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def get_cached_vector_sub_results(query: str, domain_scope: Optional[List[str]] = None, top_k: int = 5) -> Optional[List[Dict[str, Any]]]:
    global _SUB_CACHE_HITS, _SUB_CACHE_MISSES
    key = _build_sub_key(query, domain_scope, top_k)
    cached = _VECTOR_SUB_CACHE.get(key)
    if cached is not None:
        _SUB_CACHE_HITS += 1
        logger.info("Sub-Result Cache HIT for Vector Agent ('%s')", query)
        return cached
    _SUB_CACHE_MISSES += 1
    return None


def set_cached_vector_sub_results(query: str, results: List[Dict[str, Any]], domain_scope: Optional[List[str]] = None, top_k: int = 5) -> None:
    key = _build_sub_key(query, domain_scope, top_k)
    _VECTOR_SUB_CACHE[key] = results


def get_cached_graph_sub_results(query: str, domain_scope: Optional[List[str]] = None, top_k: int = 15) -> Optional[List[Dict[str, Any]]]:
    global _SUB_CACHE_HITS, _SUB_CACHE_MISSES
    key = _build_sub_key(query, domain_scope, top_k)
    cached = _GRAPH_SUB_CACHE.get(key)
    if cached is not None:
        _SUB_CACHE_HITS += 1
        logger.info("Sub-Result Cache HIT for Graph Agent ('%s')", query)
        return cached
    _SUB_CACHE_MISSES += 1
    return None


def set_cached_graph_sub_results(query: str, results: List[Dict[str, Any]], domain_scope: Optional[List[str]] = None, top_k: int = 15) -> None:
    key = _build_sub_key(query, domain_scope, top_k)
    _GRAPH_SUB_CACHE[key] = results


def get_sub_cache_stats() -> Dict[str, Any]:
    return {
        "vector_cache_size": len(_VECTOR_SUB_CACHE),
        "graph_cache_size": len(_GRAPH_SUB_CACHE),
        "hits": _SUB_CACHE_HITS,
        "misses": _SUB_CACHE_MISSES,
    }
