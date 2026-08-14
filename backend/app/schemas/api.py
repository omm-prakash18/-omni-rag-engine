"""
app/schemas/api.py — Pydantic request/response schemas for all API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Contradiction Types ───────────────────────────────────────────────────────
class ContradictionType(str, Enum):
    direct_contradiction = "direct_contradiction"
    stale = "stale"
    scope_mismatch = "scope_mismatch"
    methodology_mismatch = "methodology_mismatch"


# ── Chunk / Source references ─────────────────────────────────────────────────
class SourceRef(BaseModel):
    chunk_id: str
    source_name: str
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    excerpt: str  # short paraphrase — NOT full text (copyright)
    url: Optional[str] = None
    sentiment: Optional[float] = None
    claimed_scope: Optional[Dict[str, Any]] = None


# ── Contradiction ─────────────────────────────────────────────────────────────
class Contradiction(BaseModel):
    id: str
    entity: str                    # e.g. "US Inflation Rate"
    metric: Optional[str] = None   # e.g. "CPI year-over-year"
    contradiction_type: ContradictionType
    reason: str                    # classifier explanation
    confidence: float = Field(ge=0.0, le=1.0)
    source_a: SourceRef
    source_b: SourceRef


# ── Graph ─────────────────────────────────────────────────────────────────────
class GraphNode(BaseModel):
    id: str
    label: str
    type: str   # "entity" | "claim" | "source"
    data: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    id: str
    source: str   # node id
    target: str   # node id
    type: str     # "CLAIMS" | "CONTRADICTS" | "SUPERSEDES" | "SUPPORTS"
    data: Dict[str, Any] = {}


class GraphData(BaseModel):
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []


# ── Query Request / Response ──────────────────────────────────────────────────
class QueryFilters(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sources: Optional[List[str]] = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    filters: Optional[QueryFilters] = None
    top_k: int = Field(default=10, ge=1, le=50)


class QueryResponse(BaseModel):
    query: str
    contradictions: List[Contradiction] = []
    graph: GraphData = GraphData()
    steps: List[str] = []          # agent reasoning trace
    cached: bool = False
    demo_mode: bool = False        # True when no real API key configured


# ── Ingest ────────────────────────────────────────────────────────────────────
class IngestTriggerResponse(BaseModel):
    status: str
    job_id: Optional[int] = None
    message: str


class IngestStatusItem(BaseModel):
    source: str
    last_run: Optional[datetime] = None
    articles_fetched: int = 0
    chunks_created: int = 0
    status: str = "never_run"
    error: Optional[str] = None


class IngestStatusResponse(BaseModel):
    sources: List[IngestStatusItem] = []


# ── WebSocket message frames ──────────────────────────────────────────────────
class WsFrame(BaseModel):
    type: str   # "step" | "contradiction" | "graph_update" | "done" | "error"
    data: Any
