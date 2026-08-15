"""
app/routers/query.py — FastAPI endpoint for one-shot query execution.

POST /query
- Computes hash of query string
- Checks Redis / in-memory cache
- If miss: runs 4-node agent pipeline
- Caches response for 300 seconds
"""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, HTTPException

from app.agents.pipeline import run_omni_pipeline
from app.config import get_settings
from app.database import cache_get, cache_set
from app.schemas.api import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["Query"])


@router.post("/query", response_model=QueryResponse)
async def execute_query(req: QueryRequest):
    """
    Run one-shot contradiction query across vector & graph stores.
    Returns detected contradictions, graph topology (React Flow compatible), and reasoning trace.
    """
    try:
        # Cache key from query hash
        cache_key = f"omni_query:{hashlib.md5(req.query.lower().strip().encode()).hexdigest()}"
        cached_data = await cache_get(cache_key)

        if cached_data:
            logger.info("Serving query '%s' from cache", req.query)
            data = json.loads(cached_data)
            data["cached"] = True
            return QueryResponse(**data)

        # Run pipeline
        response = await run_omni_pipeline(
            query=req.query,
            top_k=req.top_k,
            preferences=req.preferences,
            history=req.history,
            conversation_id=req.conversation_id,
            user_id=req.user_id,
        )
        response.demo_mode = settings.demo_mode

        # Save to cache
        await cache_set(cache_key, response.model_dump_json(), ttl=300)

        return response

    except Exception as e:
        logger.error("Error executing query '%s': %s", req.query, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing query.")
