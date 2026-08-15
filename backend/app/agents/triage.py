"""
app/agents/triage.py — Node 0: Triage / Gate Node.

Fast, near-zero cost initial classification node that gates incoming queries before pipeline execution.
Classifies query into:
- answerable: proceed to full parallel pipeline (Vector Agent + Graph Agent -> Synthesizer -> Classifier)
- single_fact: proceed to Vector Agent + Synthesizer (skip Graph Agent and Contradiction Classifier)
- off_topic: return direct honest response, skip pipeline entirely
- too_vague: return clarifying question prompt, skip pipeline entirely
- no_data_expected: return immediate no-corpus-match response, skip pipeline entirely
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Set

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Known corpus entities & keywords ingested into OmniPerspective database
CORPUS_KEYWORDS: Set[str] = {
    "cpi", "pce", "inflation", "gdp", "fed", "fomc", "interest rate", "interest rates",
    "benchmark rate", "economic growth", "bls", "bea", "reuters", "bloomberg", "ap",
    "cnbc", "wsj", "ft", "financial times", "wall street journal", "chained cpi",
    "headline cpi", "core pce", "nowcast", "annualized gdp", "federal reserve",
    "target range", "price index", "unweighted", "spot market"
}

# Off-topic triggers (coding, creative writing, non-financial general knowledge)
OFF_TOPIC_PATTERNS = [
    r"\b(poem|poetry|rhyme|song|story|essay|joke)\b",
    r"\b(python|javascript|java|c\+\+|code|coding|function|linked list|algorithm)\b",
    r"\b(capital of|weather in|who won|recipe|cook|movie|actor|music)\b",
    r"\b(who are you|what is your name|hello|hi|hey|test|demo)\b",
]

# Broad/vague economic prompts requiring clarification
TOO_VAGUE_PATTERNS = [
    r"^(tell me about the economy|what is the economy|explain the economy)$",
    r"^(what are economic indicators|explain financial metrics|economy news)$",
    r"^(how is the market|financial summary|tell me everything)$",
]

# Explicit out-of-corpus topics (companies/assets not ingested)
OUT_OF_CORPUS_TERMS = {
    "apple", "iphone", "tesla", "robotaxi", "nvidia", "bitcoin", "crypto",
    "microsoft", "amazon", "google", "meta", "goldman sachs", "salary",
    "super bowl", "nfl", "nba", "elections"
}


def run_triage_agent(query: str) -> Dict[str, Any]:
    """
    Classifies incoming query into one of 5 triage categories using word-boundary matching.
    Returns dict with category, reason, and direct_response (for gated queries).
    """
    query_clean = query.strip()
    query_low = query_clean.lower()

    # 1. Check Off-Topic / Conversational
    for pattern in OFF_TOPIC_PATTERNS:
        if re.search(pattern, query_low):
            logger.info("Triage Agent: Classified '%s' -> off_topic", query_clean)
            return {
                "category": "off_topic",
                "reason": "Query is conversational or unrelated to economic/financial metrics.",
                "direct_response": (
                    "I am OmniPerspective Engine, a specialized financial contradiction reasoning engine. "
                    "I cannot assist with creative writing, programming, or non-financial topics. "
                    "Please ask a question about US economic metrics (CPI, PCE, Fed Rate, or GDP)."
                ),
            }

    # 2. Check Too Vague
    for pattern in TOO_VAGUE_PATTERNS:
        if re.search(pattern, query_low):
            logger.info("Triage Agent: Classified '%s' -> too_vague", query_clean)
            return {
                "category": "too_vague",
                "reason": "Query scope is too broad for targeted retrieval.",
                "direct_response": (
                    "Your query is too broad. Please specify which economic metric or time period you wish to analyze "
                    "(e.g., 'May 2024 CPI inflation rate', 'Q1 2024 GDP growth', or 'Federal Reserve benchmark interest rate')."
                ),
            }

    # 3. Check Explicit Out of Corpus (no_data_expected) — word boundary matching to avoid 'nfl' matching 'inflation'
    if any(re.search(r"\b" + re.escape(term) + r"\b", query_low) for term in OUT_OF_CORPUS_TERMS):
        logger.info("Triage Agent: Classified '%s' -> no_data_expected", query_clean)
        return {
            "category": "no_data_expected",
            "reason": "Query targets an entity or topic outside corpus coverage.",
            "direct_response": (
                "The ingested corpus does not contain data on this specific entity or topic. "
                "OmniPerspective currently tracks macroeconomic indicators: US Inflation (CPI/PCE), "
                "Federal Reserve Interest Rates, and US GDP Growth."
            ),
        }

    # Lightweight index matching for corpus keywords (word boundaries)
    has_corpus_match = any(re.search(r"\b" + re.escape(kw) + r"\b", query_low) for kw in CORPUS_KEYWORDS)
    # Check for numerical rate queries like "cpi 3.2%" or "fed 5.25%"
    has_numeric_rate = bool(re.search(r"\b(cpi|pce|fed|gdp)\s+\d+(?:\.\d+)?%?\b", query_low))

    if not has_corpus_match and not has_numeric_rate:
        # Check if query mentions any specific domain terms
        words = set(re.findall(r"\b[a-z]{3,}\b", query_low))
        stopwords = {"what", "is", "the", "for", "in", "of", "and", "a", "an", "rate", "latest", "current", "show", "me", "find", "tell", "explain"}
        meaningful_words = words - stopwords

        if not meaningful_words or len(query_clean) < 4:
            logger.info("Triage Agent: Classified '%s' -> off_topic (low intent)", query_clean)
            return {
                "category": "off_topic",
                "reason": "Query lacks recognizable financial intent.",
                "direct_response": "Please ask a specific question regarding US inflation, interest rates, or GDP growth figures.",
            }

        # If real question but no corpus match
        logger.info("Triage Agent: Classified '%s' -> no_data_expected (no corpus keyword match)", query_clean)
        return {
            "category": "no_data_expected",
            "reason": "No matching entities found in the corpus index.",
            "direct_response": (
                "No matching records found in the corpus index for this topic. "
                "OmniPerspective currently covers US Inflation, Fed Interest Rates, and US GDP Growth."
            ),
        }

    # 4. Check Single Fact vs Answerable (multi-source / comparative)
    is_single_source = any(re.search(r"\b" + re.escape(src) + r"\b", query_low) for src in [
        "according to", "reported by", "bloomberg economics cpi nowcast", "associated press report",
        "what was the annualized", "did wall street journal report"
    ]) or ("what was" in query_low and "compared to" not in query_low)

    is_comparative = any(re.search(r"\b" + re.escape(comp) + r"\b", query_low) for comp in [
        "vs", "versus", "compared to", "difference", "disagreement", "higher or lower", "between"
    ])

    if is_single_source and not is_comparative:
        logger.info("Triage Agent: Classified '%s' -> single_fact", query_clean)
        return {
            "category": "single_fact",
            "reason": "Single factual lookup requested.",
            "direct_response": None,
        }

    # Default: Proceed to full pipeline
    logger.info("Triage Agent: Classified '%s' -> answerable", query_clean)
    return {
        "category": "answerable",
        "reason": "Answerable multi-source economic query.",
        "direct_response": None,
    }
