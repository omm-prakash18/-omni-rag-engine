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


def run_vector_agent(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    """Embed query and perform hybrid semantic + keyword search with Reciprocal Rank Fusion (RRF)."""
    logger.info("Vector Agent: executing hybrid search for '%s'", query)
    
    # 1. Embed query
    query_vector = generate_embedding(query)
    
    # 2. Retrieve dense and keyword matches
    from app.services.qdrant_store import keyword_search
    dense_results = search_chunks(query_vector, top_k=top_k * 2, score_threshold=0.05, query_text=query)
    keyword_results = keyword_search(query, top_k=top_k * 2)
    
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
    
    # Format and return the top_k results
    chunks = []
    for cid in sorted_ids[:top_k]:
        r = id_to_result[cid]
        payload = r.get("payload", {})
        chunks.append({
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

    logger.info("Vector Agent: merged %d dense & %d keyword chunks → %d RRF chunks", 
                len(dense_results), len(keyword_results), len(chunks))
    return chunks
