"""
app/agents/vector_agent.py — Node 1: Vector Agent.

Performs semantic search in Qdrant for chunks relevant to the query.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.extraction import generate_embedding
from app.services.qdrant_store import search_chunks

logger = logging.getLogger(__name__)


def _cross_encoder_rerank(query: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rerank retrieved chunks using query-chunk term matching and semantic overlap cross-scoring."""
    query_terms = [t.lower() for t in query.split() if len(t) > 2]
    
    # Financial acronym synonym expansion for reranker
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

    for chunk in chunks:
        text = chunk.get("raw_text", "").lower()
        title = (chunk.get("title") or "").lower()
        full_text = text + " " + title
        
        matches = sum(1 for term in expanded_terms if term in full_text)
        term_density = matches / max(len(expanded_terms), 1)
        
        # Boost score using cross-encoder term overlap
        orig_score = chunk.get("score", 0.0)
        chunk["rerank_score"] = round((orig_score * 0.4) + (term_density * 0.6), 4)

    # Sort by rerank score descending
    chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return chunks


def run_vector_agent(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Embed query and perform hybrid semantic + keyword search with Reciprocal Rank Fusion (RRF) & Reranking."""
    logger.info("Vector Agent: executing hybrid search & reranking for '%s' (top_k=%d)", query, top_k)
    
    # Query Expansion for metric comparisons
    search_query = query
    query_low = query.lower()
    if "pce" in query_low and "cpi" not in query_low:
        search_query = query + " CPI headline inflation"
    elif "cpi" in query_low and "pce" not in query_low:
        search_query = query + " PCE core inflation"
    elif "gdp" in query_low:
        search_query = query + " annualized economic growth"
        
    # 1. Embed query
    query_vector = generate_embedding(search_query)
    
    # 2. Retrieve dense and keyword matches (retrieve top-10 for reranking)
    from app.services.qdrant_store import keyword_search
    dense_results = search_chunks(query_vector, top_k=10, score_threshold=0.05, query_text=search_query)
    keyword_results = keyword_search(search_query, top_k=10)
    
    # 3. Reciprocal Rank Fusion (RRF)
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
        
    # Sort by combined RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Format candidates
    candidates = []
    for cid in sorted_ids[:10]:
        r = id_to_result[cid]
        payload = r.get("payload", {})
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
        })

    # 4. Rerank candidates down to top_k
    reranked_chunks = _cross_encoder_rerank(query, candidates)
    final_chunks = reranked_chunks[:top_k]

    logger.info("Vector Agent: merged %d dense & %d keyword chunks → reranked top-%d chunks", 
                len(dense_results), len(keyword_results), len(final_chunks))
    return final_chunks
