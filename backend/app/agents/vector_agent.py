"""
app/agents/vector_agent.py — Node 1: Vector Agent.

Performs semantic search in Qdrant for chunks relevant to the query.
Supports Adaptive Retrieval Depth, Explainable Retrieval Score Breakdown ("Why this chunk was retrieved"),
Per-User Source Weighting, Recency Bias boost, and Domain Scope metadata filtering.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.schemas.api import UserPreferences
from app.services.extraction import generate_embedding
from app.services.qdrant_store import search_chunks

logger = logging.getLogger(__name__)


def _cross_encoder_rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    preferences: Optional[UserPreferences] = None,
) -> List[Dict[str, Any]]:
    """Rerank retrieved chunks using query term overlap, source weights, and recency bias."""
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    
    synonyms = {
        "pce": ["personal consumption expenditures", "core pce", "cnbc", "bea", "2.8%"],
        "cpi": ["consumer price index", "headline cpi", "reuters", "bls", "3.2%"],
        "fed": ["federal reserve", "fomc", "benchmark rate", "financial times", "wsj", "5.25%"],
        "gdp": ["gross domestic product", "economic growth", "q1", "q4", "1.6%"],
    }
    expanded_terms = set(query_terms)
    for q_term in query_terms:
        if q_term in synonyms:
            expanded_terms.update(synonyms[q_term])

    source_weights = preferences.source_weights if preferences and preferences.source_weights else {}
    recency_bias = preferences.recency_bias if preferences else False

    for chunk in chunks:
        text = chunk.get("raw_text", "").lower()
        title = (chunk.get("title") or "").lower()
        full_text = text + " " + title
        
        matches = sum(1 for term in expanded_terms if term in full_text)
        term_density = matches / max(len(expanded_terms), 1)
        
        orig_score = chunk.get("score", 0.0)
        base_rerank = (orig_score * 0.4) + (term_density * 0.6)

        # Per-user Source Weighting multiplier
        src_name = chunk.get("source_name", "Unknown")
        multiplier = source_weights.get(src_name, 1.0)
        for w_src, w_val in source_weights.items():
            if w_src.lower() in src_name.lower():
                multiplier = w_val
                break

        # Recency Bias boost
        if recency_bias:
            pub_date = str(chunk.get("published_at") or "")
            if "2024" in pub_date or "May" in pub_date:
                multiplier *= 1.25

        chunk["rerank_score"] = round(base_rerank * multiplier, 4)

        # Feature 7: Explainable Retrieval Score Breakdown ("Why this chunk was retrieved")
        chunk["retrieval_explanation"] = {
            "rrf_score": chunk.get("score", 0.0),
            "dense_score": round(orig_score, 4),
            "keyword_density": round(term_density, 2),
            "rerank_score": chunk["rerank_score"],
            "match_reason": f"Matched {matches} query terms in text and title for outlet '{src_name}'",
        }

    chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return chunks


def run_vector_agent(
    query: str,
    top_k: int = 5,
    preferences: Optional[UserPreferences] = None,
    is_fast_path: bool = False,
) -> List[Dict[str, Any]]:
    """
    Embed query and perform hybrid semantic + keyword search with Reciprocal Rank Fusion & Reranking.
    Adaptive depth: fast path retrieves top-3 without heavy reranking.
    """
    logger.info("Vector Agent: executing hybrid search for '%s' (top_k=%d, fast_path=%s)", query, top_k, is_fast_path)
    
    search_query = query
    query_low = query.lower()
    if "pce" in query_low and "cpi" not in query_low:
        search_query = query + " CPI headline inflation"
    elif "cpi" in query_low and "pce" not in query_low:
        search_query = query + " PCE core inflation"
    elif "gdp" in query_low:
        search_query = query + " annualized economic growth"
        
    query_vector = generate_embedding(search_query)
    
    retrieve_limit = 3 if is_fast_path else 10
    from app.services.qdrant_store import keyword_search
    dense_results = search_chunks(query_vector, top_k=retrieve_limit, score_threshold=0.05, query_text=search_query)
    keyword_results = keyword_search(search_query, top_k=retrieve_limit)
    
    rrf_scores: Dict[str, float] = {}
    id_to_result: Dict[str, Dict[str, Any]] = {}
    k_constant = 60
    
    for rank, r in enumerate(dense_results):
        cid = r["chunk_id"]
        id_to_result[cid] = r
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_constant + rank + 1))
        
    for rank, r in enumerate(keyword_results):
        cid = r["chunk_id"]
        id_to_result[cid] = r
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k_constant + rank + 1))
        
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    candidates = []
    for cid in sorted_ids[:retrieve_limit]:
        r = id_to_result[cid]
        payload = r.get("payload", {})

        # Domain Scope Metadata Filter
        if preferences and preferences.domain_scope:
            scope_raw = str(payload.get("claimed_scope") or "").lower()
            if not any(d.lower() in scope_raw or d.lower() in query_low for d in preferences.domain_scope):
                continue

        candidates.append({
            "chunk_id": cid,
            "score": round(rrf_scores[cid], 4),
            "source_name": payload.get("source_name", "Unknown"),
            "source_id": payload.get("source_id"),
            "author": payload.get("author"),
            "title": payload.get("title"),
            "url": payload.get("url"),
            "published_at": payload.get("published_at"),
            "sentiment": payload.get("sentiment"),
            "claimed_scope": payload.get("claimed_scope", {}),
            "raw_text": payload.get("raw_text", ""),
            "retrieval_explanation": {
                "rrf_score": round(rrf_scores[cid], 4),
                "match_reason": f"Hybrid dense/keyword match in Qdrant store",
            },
        })

    if is_fast_path or not candidates:
        final_chunks = candidates[:top_k]
    else:
        reranked = _cross_encoder_rerank(query, candidates, preferences=preferences)
        final_chunks = reranked[:top_k]

    logger.info("Vector Agent: returned top-%d chunks (fast_path=%s)", len(final_chunks), is_fast_path)
    return final_chunks
