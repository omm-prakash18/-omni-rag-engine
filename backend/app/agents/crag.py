"""
app/agents/crag.py — Corrective Retrieval-Augmented Generation (CRAG) Agent.

Implements the Corrective RAG pattern for contradiction detection:
1. Retrieval Evaluator: Evaluates relevance confidence of vector chunks retrieved from Qdrant.
2. Corrective Actions:
   - AMBIGUOUS / LOW RELEVANCE: Triggers Query Rewriting & Keyword Expansion.
   - NOISY: Filters out irrelevant fragments before synthesis.
3. Knowledge Refinement: Extracts clean claim sentences & scope tags for Synthesizer Node.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _score_chunk_relevance(query: str, chunk: Dict[str, Any]) -> float:
    """Evaluate relevance of a retrieved chunk against the query [0.0 to 1.0]."""
    query_clean = query.strip().lower()
    
    # Conversational / low-intent guardrail
    conversational = {"hi", "hello", "hey", "test", "demo", "ok", "a", "an", "the", "who", "what"}
    if query_clean in conversational or len(query_clean) < 3:
        return 0.0

    # Stopwords filter to focus relevance on domain keywords
    stopwords = {"and", "the", "for", "with", "between", "disagreement", "difference", "reported", "trends", "which", "claims", "that"}
    # Extract terms including percentage rates (e.g., 2.8%, 3.2%, 5.25%)
    raw_terms = re.findall(r"\b\d+(?:\.\d+)?%?\b|\b[a-zA-Z]{2,}\b", query)
    query_terms = [t.lower() for t in raw_terms if t.lower() not in stopwords]
    if not query_terms:
        return 0.0

    raw_text = (chunk.get("raw_text", "") + " " + chunk.get("title", "")).lower()
    
    # Synonym expansions
    synonyms = {
        "pce": ["pce", "personal consumption expenditures", "core pce"],
        "cpi": ["cpi", "consumer price index", "headline cpi"],
        "fed": ["fed", "federal reserve", "fomc", "benchmark"],
        "gdp": ["gdp", "gross domestic product", "growth"],
    }
    
    matches = 0
    for term in query_terms:
        if term in synonyms:
            if any(syn in raw_text for syn in synonyms[term]):
                matches += 1
        elif term in raw_text:
            matches += 1
    
    term_ratio = matches / len(query_terms)
    vector_score = chunk.get("score", 0.0)

    # If zero terms matched and vector similarity is weak (<0.15), score is 0.0
    if matches == 0 and vector_score < 0.15:
        return 0.0

    # Weighted combination of vector cosine similarity & term overlap
    combined_score = (vector_score * 0.3) + (term_ratio * 0.7)
    return round(combined_score, 4)


def _rewrite_search_query(query: str) -> str:
    """Corrective Query Rewriter — expands financial terms and acronyms using LLM or dictionary."""
    if not settings.demo_mode and settings.gemini_api_key:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=settings.gemini_api_key)
            prompt = f"""
You are an expert financial search engineer. Rewrite and expand the following query for a vector search engine to find source articles.
Focus on expanding economic acronyms (e.g. CPI -> Consumer Price Index, GDP -> Gross Domestic Product, PCE, Fed rate cuts) and adding relevant synonyms or indicators.
Return ONLY the final expanded query string.

Query: "{query}"
"""
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
            )
            expanded = response.text.strip()
            if expanded:
                logger.info("CRAG LLM Query Rewriter expanded '%s' → '%s'", query, expanded)
                return expanded
        except Exception as e:
            logger.warning("CRAG LLM Query Rewriter failed (%s), falling back to dictionary.", e)

    # Heuristic dictionary-based fallback
    query_low = query.lower()
    replacements = {
        "cpi": "Consumer Price Index inflation rate BLS",
        "pce": "Personal Consumption Expenditures price index BEA",
        "fed": "Federal Reserve benchmark interest rate FOMC",
        "gdp": "Gross Domestic Product annualized economic growth rate",
    }
    
    expanded = query
    for key, val in replacements.items():
        if key in query_low:
            expanded = expanded + " " + val
            
    logger.info("CRAG Heuristic Query Rewriter expanded '%s' → '%s'", query, expanded)
    return expanded


def run_crag_agent(query: str, raw_chunks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Executes Corrective RAG evaluation and filtering over raw retrieved chunks.
    Returns: (refined_chunks, crag_metrics)
    """
    query_clean = query.strip().lower()
    conversational = {"hi", "hello", "hey", "test", "demo", "ok", "a", "an", "the", "who", "what"}

    # Guardrail check for low-intent query
    if query_clean in conversational or len(query_clean) < 3:
        logger.info("CRAG Agent: Low-intent / conversational query detected ('%s'). Skipping retrieval.", query)
        metrics = {
            "action": "LOW_INTENT_SKIPPED",
            "avg_relevance": 0.0,
            "raw_count": len(raw_chunks),
            "refined_count": 0,
            "confidence": "REJECTED",
        }
        return [], metrics

    logger.info("CRAG Agent: Evaluating %d raw retrieved chunks...", len(raw_chunks))

    evaluated_chunks = []
    total_score = 0.0

    for chunk in raw_chunks:
        rel_score = _score_chunk_relevance(query, chunk)
        total_score += rel_score
        
        # Quality threshold: only keep chunks above relevance score 0.30
        if rel_score >= 0.30:
            c = dict(chunk)
            c["crag_score"] = rel_score
            evaluated_chunks.append(c)

    avg_relevance = (total_score / len(raw_chunks)) if raw_chunks else 0.0
    action = "CORRECT_PASS"

    # Trigger Corrective Actions based on retrieval confidence score
    if avg_relevance < 0.25 and len(evaluated_chunks) == 0:
        action = "LOW_RELEVANCE_REJECTED"
        logger.warning("CRAG Triggered: Query '%s' yielded 0 relevant chunks (avg relevance %.2f).", query, avg_relevance)
    elif avg_relevance < 0.40 or len(evaluated_chunks) < 2:
        action = "CORRECTIVE_REWRITE_AND_EXPAND"
        expanded_query = _rewrite_search_query(query)
        logger.warning("CRAG Triggered: Retrieval confidence low (%.2f). Executing Corrective Query Expansion.", avg_relevance)
        
        # Re-evaluating with expanded term matching fallback
        from app.services.qdrant_store import keyword_search
        fallback_results = keyword_search(expanded_query, top_k=10)
        
        for fb in fallback_results:
            payload = fb.get("payload", {})
            fb_chunk = {
                "chunk_id": fb.get("chunk_id"),
                "score": fb.get("score", 0.5),
                "source_name": payload.get("source_name", "Unknown"),
                "source_id": payload.get("source_id"),
                "author": payload.get("author"),
                "title": payload.get("title"),
                "url": payload.get("url"),
                "published_at": payload.get("published_at"),
                "sentiment": payload.get("sentiment"),
                "claimed_scope": payload.get("claimed_scope", {}),
                "raw_text": payload.get("raw_text", ""),
                "crag_score": 0.65,
            }
            fb_score = _score_chunk_relevance(query, fb_chunk)
            if fb_score >= 0.35 and not any(c["chunk_id"] == fb_chunk["chunk_id"] for c in evaluated_chunks):
                evaluated_chunks.append(fb_chunk)

    # Sort by CRAG score descending
    evaluated_chunks.sort(key=lambda x: x.get("crag_score", 0.0), reverse=True)

    metrics = {
        "action": action,
        "avg_relevance": round(avg_relevance, 2),
        "raw_count": len(raw_chunks),
        "refined_count": len(evaluated_chunks),
        "confidence": "HIGH" if avg_relevance > 0.6 else ("CORRECTED" if evaluated_chunks else "REJECTED"),
    }

    logger.info("CRAG Agent Complete: Action=%s, Raw=%d → Refined=%d", action, len(raw_chunks), len(evaluated_chunks))
    return evaluated_chunks, metrics
