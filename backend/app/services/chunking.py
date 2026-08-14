"""
app/services/chunking.py — Semantic chunking + metadata extraction.

Uses LlamaIndex SemanticSplitterNodeParser when a Gemini API key is
configured. Falls back to simple sentence-window splitting otherwise.

Per-chunk metadata extracted:
  - sentiment (TextBlob polarity)
  - claimed_scope: {date_range, geography, methodology} (rule-based heuristics)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Geography keyword vocabulary (extend as needed)
_GEO_TERMS = {
    "US", "USA", "United States", "America", "EU", "Europe", "European Union",
    "UK", "Britain", "China", "Japan", "India", "Brazil", "Germany", "France",
    "global", "worldwide", "international", "domestic", "emerging markets",
}

# Methodology keywords
_METHOD_TERMS = {
    "year-over-year", "yoy", "month-over-month", "mom", "seasonally adjusted",
    "annualized", "consensus", "estimate", "revised", "preliminary", "final",
    "core", "headline", "PCE", "CPI", "GDP deflator",
}

# Date pattern (YYYY or Month YYYY or Q1 YYYY)
_DATE_PATTERN = re.compile(
    r"\b(?:Q[1-4]\s+)?\d{4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"(?:uary|ruary|ch|il|e|y|ust|tember|ober|ember)?\s+\d{4}\b",
    re.IGNORECASE,
)


@dataclass
class ChunkMetadata:
    chunk_id: str
    raw_text: str
    author: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sentiment: Optional[float] = None
    claimed_scope: Dict[str, Any] = field(default_factory=dict)
    source_name: Optional[str] = None
    source_id: Optional[str] = None


def _extract_sentiment(text: str) -> float:
    """TextBlob polarity in [-1, 1]. Returns 0.0 if TextBlob unavailable."""
    try:
        from textblob import TextBlob
        return round(TextBlob(text).sentiment.polarity, 4)
    except Exception:
        return 0.0


def _extract_claimed_scope(text: str) -> Dict[str, Optional[str]]:
    """Rule-based heuristic extraction of date range, geography, methodology."""
    dates = _DATE_PATTERN.findall(text)
    geo_hits = [t for t in _GEO_TERMS if t.lower() in text.lower()]
    method_hits = [t for t in _METHOD_TERMS if t.lower() in text.lower()]

    return {
        "date_range": ", ".join(dates[:2]) if dates else None,
        "geography": ", ".join(geo_hits[:3]) if geo_hits else None,
        "methodology": ", ".join(method_hits[:2]) if method_hits else None,
    }


def _simple_split(text: str, chunk_size: int = 400, overlap: int = 80) -> List[str]:
    """
    Fallback: Sentence-aware chunking strategy when LlamaIndex semantic splitter is not usable.
    Groups complete sentences up to chunk_size to maintain semantic cohesion.
    """
    # Regex split on sentence endings: period, question mark, exclamation mark followed by whitespace/newline
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    sentences = sentence_endings.split(text)
    
    chunks = []
    current_chunk = []
    current_len = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        sent_len = len(sentence)
        # If adding sentence exceeds size, commit chunk
        if current_len + sent_len > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            
            # Maintain sentence overlap
            overlap_chunk = []
            overlap_len = 0
            for s in reversed(current_chunk):
                if overlap_len + len(s) < overlap:
                    overlap_chunk.insert(0, s)
                    overlap_len += len(s) + 1
                else:
                    break
            current_chunk = overlap_chunk
            current_len = overlap_len
            
        current_chunk.append(sentence)
        current_len += sent_len + 1
        
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return [c.strip() for c in chunks if len(c.strip()) >= 50]


def _semantic_split(text: str) -> List[str]:
    """
    LlamaIndex SemanticSplitterNodeParser backed by Gemini embeddings.
    Splits on semantic boundaries (claim boundaries), not fixed token windows.
    """
    try:
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.core import Document
        from llama_index.embeddings.gemini import GeminiEmbedding

        embed_model = GeminiEmbedding(
            model_name=settings.embedding_model,
            api_key=settings.gemini_api_key,
        )
        splitter = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=embed_model,
        )
        doc = Document(text=text)
        nodes = splitter.get_nodes_from_documents([doc])
        return [n.get_content() for n in nodes if n.get_content().strip()]
    except Exception as e:
        logger.warning("Semantic splitter failed (%s), using simple split", e)
        return _simple_split(text)


def chunk_article(
    raw_text: str,
    source_name: str,
    source_id: str,
    author: Optional[str] = None,
    title: Optional[str] = None,
    url: Optional[str] = None,
    published_at: Optional[datetime] = None,
) -> List[ChunkMetadata]:
    """
    Split an article into semantic chunks and enrich each with metadata.
    Returns a list of ChunkMetadata objects ready for extraction + storage.
    """
    import uuid

    if not raw_text or not raw_text.strip():
        return []

    # Choose splitter based on API availability
    if not settings.demo_mode:
        texts = _semantic_split(raw_text)
    else:
        texts = _simple_split(raw_text)

    chunks: List[ChunkMetadata] = []
    
    # Contextual Prefixing to carry standalone metadata without neighbor dependence
    meta_prefix_parts = []
    if source_name:
        meta_prefix_parts.append(f"Source: {source_name}")
    if title:
        meta_prefix_parts.append(f"Title: {title}")
    if published_at:
        meta_prefix_parts.append(f"Date: {published_at.strftime('%Y-%m-%d') if hasattr(published_at, 'strftime') else str(published_at)}")
    
    context_prefix = f"[{' | '.join(meta_prefix_parts)}] " if meta_prefix_parts else ""

    for text in texts:
        if len(text.strip()) < 50:  # skip very short fragments
            continue
            
        full_context_text = context_prefix + text.strip() if not text.strip().startswith("[Source:") else text.strip()

        chunks.append(
            ChunkMetadata(
                chunk_id=str(uuid.uuid4()),
                raw_text=full_context_text,
                author=author,
                title=title,
                url=url,
                published_at=published_at,
                sentiment=_extract_sentiment(text),
                claimed_scope=_extract_claimed_scope(text),
                source_name=source_name,
                source_id=source_id,
            )
        )

    logger.debug("Chunked '%s' → %d chunks", title or "article", len(chunks))
    return chunks
