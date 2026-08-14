"""
app/services/qdrant_store.py — Qdrant vector store operations.

Handles:
- Collection initialisation
- Chunk upsert (dense embedding + sparse BM25 payload)
- Hybrid search (dense + keyword filtering)
- Point existence checks
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import get_settings

import os

# Ensure pure python protobuf
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

logger = logging.getLogger(__name__)
settings = get_settings()

VECTOR_SIZE = 768  # text-embedding-004 output dimension

# In-memory fallback vector store for environments without native C-extensions
_in_memory_store: Dict[str, Dict[str, Any]] = {}


def _client():
    from app.database import get_qdrant
    return get_qdrant()


def ensure_collection():
    """Create the Qdrant collection if it doesn't already exist."""
    try:
        from qdrant_client.models import Distance, VectorParams

        client = _client()
        existing = [c.name for c in client.get_collections().collections]
        if settings.qdrant_collection not in existing:
            client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            logger.info("Qdrant: created collection '%s'", settings.qdrant_collection)
    except Exception as e:
        logger.warning("Qdrant collection check failed (%s), using in-memory store", e)


def upsert_chunk(
    chunk_id: str,
    embedding: List[float],
    payload: Dict[str, Any],
) -> bool:
    """Upsert a single chunk vector with its metadata payload."""
    # Qdrant requires UUIDs or unsigned ints as point IDs.
    # We derive a stable UUID from the chunk_id string via uuid5 so re-ingestion
    # of the same chunk yields the same point ID (idempotent upsert).
    import uuid as _uuid
    qdrant_point_id = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, chunk_id))

    # Ensure chunk_id is always stored in the payload for retrieval
    payload = {**payload, "chunk_id": chunk_id}

    _in_memory_store[chunk_id] = {
        "vector": embedding,
        "payload": payload,
    }
    try:
        from qdrant_client.models import PointStruct
        ensure_collection()
        client = _client()
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[PointStruct(id=qdrant_point_id, vector=embedding, payload=payload)],
        )
    except Exception as e:
        logger.warning("Qdrant client upsert skipped (%s); saved to in-memory store", e)
    return True


def search_chunks(
    query_embedding: List[float],
    top_k: int = 10,
    score_threshold: float = 0.1,
    filter_payload: Optional[Dict[str, Any]] = None,
    query_text: str = "",
) -> List[Dict[str, Any]]:
    """
    Dense semantic search. Uses Qdrant client or in-memory cosine & term similarity fallback.
    """
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        ensure_collection()
        client = _client()

        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_embedding,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        if results:
            return [
                {"chunk_id": str(r.id), "score": r.score, "payload": r.payload or {}}
                for r in results
            ]
    except Exception as e:
        logger.warning("Qdrant search failed (%s), using in-memory vector search", e)

    # In-memory cosine similarity + term overlap fallback
    def cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b + 1e-9)

    query_terms = [t.lower() for t in query_text.split() if len(t) > 2]
    scored = []
    for cid, data in _in_memory_store.items():
        sim = cosine_sim(query_embedding, data["vector"])
        payload_text = (data["payload"].get("raw_text", "") + " " + data["payload"].get("title", "")).lower()
        term_matches = sum(1 for term in query_terms if term in payload_text) if query_terms else 0
        term_score = term_matches / max(len(query_terms), 1) if query_terms else 0.0

        final_score = max(sim, term_score)
        if final_score >= score_threshold or term_matches > 0:
            scored.append({"chunk_id": cid, "score": final_score, "payload": data["payload"]})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def keyword_search(
    keyword: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Keyword-based scroll over payload text field (BM25 approximation).
    Falls back to scroll with text filter or in-memory keyword matching.
    """
    try:
        ensure_collection()
        client = _client()
        from qdrant_client.models import Filter, FieldCondition, MatchText

        results, _ = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=Filter(
                must=[FieldCondition(key="raw_text", match=MatchText(text=keyword))]
            ),
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )
        if results:
            return [
                {"chunk_id": str(r.id), "score": 0.5, "payload": r.payload or {}}
                for r in results
            ]
    except Exception as e:
        logger.warning("Qdrant keyword search failed: %s", e)

    # In-memory keyword fallback
    results = []
    kw_lower = keyword.lower()
    for cid, data in _in_memory_store.items():
        text = data.get("payload", {}).get("raw_text", "").lower()
        if kw_lower in text:
            results.append({"chunk_id": cid, "score": 0.5, "payload": data["payload"]})
    return results[:top_k]


def collection_count() -> int:
    """Return total number of vectors in the collection."""
    try:
        ensure_collection()
        info = _client().get_collection(settings.qdrant_collection)
        return info.points_count or 0
    except Exception:
        return 0
