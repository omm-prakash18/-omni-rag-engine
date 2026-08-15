"""
app/routers/external_api.py — Authenticated Read-Only External REST API (A5).

Endpoints:
- POST /api/keys: Generate new API key credentials
- GET /api/v1/graph: Read-only REST endpoint returning full entity-claim graph, consensus indicators,
  contradiction classifications, and source reliability scores.
  Authenticated via X-API-Key header with per-key rate limiting.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.pipeline import run_omni_pipeline
from app.database import AsyncSessionLocal, get_db
from app.models.features import ApiKey

logger = logging.getLogger(__name__)

router = APIRouter(tags=["external_api"])

# In-memory sliding window rate limiter per API key hash: {key_hash: [timestamp1, timestamp2, ...]}
_RATE_LIMIT_BUCKETS: Dict[str, List[float]] = {}


def _hash_key(api_key: str) -> str:
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()


async def verify_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """FastAPI Dependency enforcing API Key authentication & sliding-window rate limiting."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'X-API-Key' header in request.",
        )

    khash = _hash_key(x_api_key)
    stmt = select(ApiKey).where(ApiKey.key_hash == khash, ApiKey.active == True)
    res = await db.execute(stmt)
    key_obj = res.scalar_one_or_none()

    if not key_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or deactivated API key provided.",
        )

    # Enforce Rate Limiting per Key
    now = time.time()
    window_start = now - 60.0
    history = _RATE_LIMIT_BUCKETS.get(khash, [])
    # Prune timestamps older than 60 seconds
    valid_history = [t for t in history if t > window_start]
    
    if len(valid_history) >= key_obj.rate_limit_per_min:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({key_obj.rate_limit_per_min} requests/min). Please slow down.",
        )

    valid_history.append(now)
    _RATE_LIMIT_BUCKETS[khash] = valid_history

    return key_obj


# ── Key Provisioning Schemas & Endpoint ──────────────────────────────────────
class ApiKeyCreate(BaseModel):
    client_name: str = Field(min_length=2, max_length=100)
    rate_limit_per_min: int = Field(default=60, ge=1, le=1000)


class ApiKeyCreatedResponse(BaseModel):
    client_name: str
    api_key: str  # Plaintext key shown ONLY once on creation
    key_prefix: str
    rate_limit_per_min: int
    message: str


@router.post("/api/keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate, db: AsyncSession = Depends(get_db)):
    """Provision a new authenticated API Key."""
    raw_secret = "omni_" + secrets.token_hex(20)
    key_hash = _hash_key(raw_secret)
    key_prefix = raw_secret[:10]

    api_key_obj = ApiKey(
        client_name=payload.client_name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        rate_limit_per_min=payload.rate_limit_per_min,
        active=True,
    )
    db.add(api_key_obj)
    await db.commit()
    logger.info("Provisioned new ApiKey for client '%s' (prefix=%s)", payload.client_name, key_prefix)

    return ApiKeyCreatedResponse(
        client_name=payload.client_name,
        api_key=raw_secret,
        key_prefix=key_prefix,
        rate_limit_per_min=payload.rate_limit_per_min,
        message="Store this API key securely. It will not be shown again.",
    )


# ── Read-Only External REST Endpoint ──────────────────────────────────────────
@router.get("/api/v1/graph")
async def get_external_graph(
    query: str = Query(min_length=3, max_length=500),
    key_obj: ApiKey = Depends(verify_api_key),
):
    """
    Read-only REST endpoint returning graph entities, claims, edges, consensus,
    contradiction classifications, and source reliability for a query/topic.
    """
    pipeline_res = await run_omni_pipeline(query)

    return {
        "query": pipeline_res.query,
        "authenticated_client": key_obj.client_name,
        "consensus_summary": getattr(pipeline_res, "consensus_summary", {}),
        "contradictions": [c.model_dump(mode="json") for c in pipeline_res.contradictions],
        "graph": pipeline_res.graph.model_dump(mode="json"),
        "cached": pipeline_res.cached,
    }
