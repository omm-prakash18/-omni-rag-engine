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
# ── Chat & Conversational Memory Schemas ─────────────────────────────────────
class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")  # "user" | "assistant" | "system"
    content: str = Field(min_length=1, max_length=2000)


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
    retrieval_explanation: Optional[Dict[str, Any]] = None  # Explainable Retrieval score breakdown


# ── Contradiction ─────────────────────────────────────────────────────────────
class Contradiction(BaseModel):
    id: str
    entity: str                    # e.g. "US Inflation Rate"
    metric: Optional[str] = None   # e.g. "CPI year-over-year"
    contradiction_type: ContradictionType
    reason: str                    # classifier explanation
    ai_resolution: Optional[str] = None # AI reconciliation summary
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


# ── User Preferences (Part 1 Customization) ──────────────────────────────────
class UserPreferences(BaseModel):
    source_weights: Optional[Dict[str, float]] = None  # Outlet weight multiplier (e.g. {"Reuters": 1.5, "FT": 0.5})
    recency_bias: bool = False                          # True = boost recent articles in ranking
    contradiction_threshold: float = Field(default=0.0, ge=0.0, le=1.0) # Filter threshold for edge rendering
    domain_scope: Optional[List[str]] = None           # Metadata scope filter (e.g. ["finance", "geopolitics"])
    answer_depth: str = Field(default="full")           # "full" | "summary"
    pinned_entities: Optional[List[str]] = None         # Entities always tracked/rendered
    theme_tokens: Optional[Dict[str, str]] = None       # Custom UI theme tokens (accents, density)


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    filters: Optional[QueryFilters] = None
    preferences: Optional[UserPreferences] = None
    conversation_id: Optional[str] = None              # Conversational Memory session ID
    history: Optional[List[ChatMessage]] = None         # Multi-turn conversation history
    user_id: Optional[str] = None                      # User ID for personalized interaction ranking
    top_k: int = Field(default=10, ge=1, le=50)


class QueryResponse(BaseModel):
    query: str
    resolved_query: Optional[str] = None               # Conversational memory resolved query
    multi_hop_subqueries: Optional[List[str]] = None   # Multi-hop subquery decomposition
    contradictions: List[Contradiction] = []
    graph: GraphData = GraphData()
    consensus_summary: Optional[Dict[str, Any]] = None
    retry_efficacy: Optional[Dict[str, Any]] = None     # Self-correcting retry loop efficacy tracking
    detected_language: Optional[str] = "en"            # Cross-lingual detection
    warnings: List[str] = []       # Warnings if narrow user preferences drop context coverage
    steps: List[str] = []          # agent reasoning trace
    cached: bool = False
    demo_mode: bool = False        # True when no real API key configured


# ── Ingest ────────────────────────────────────────────────────────────────────
class CustomIngestRequest(BaseModel):
    source_name: str = Field(default="Custom Ingestion", min_length=2, max_length=100)
    title: str = Field(default="User Submitted Article", min_length=3, max_length=200)
    content: str = Field(min_length=20, max_length=20000)
    author: Optional[str] = None
    url: Optional[str] = None


class CustomIngestResponse(BaseModel):
    status: str
    source_name: str
    chunks_created: int
    message: str


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
