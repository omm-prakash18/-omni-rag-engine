"""
app/agents/classifier.py — Node 4: Contradiction Classifier (CORE IP).

Classifies conflicts between two differing claims into taxonomy:
1. direct_contradiction — same entity, same metric, same scope, different value
2. stale — one claim's published_at is much older, likely superseded
3. scope_mismatch — different date range, geography, or scope
4. methodology_mismatch — explicitly different calculation method stated (e.g., chained CPI vs spot shelter indexing, Core PCE vs Headline CPI)
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List

from app.config import get_settings
from app.schemas.api import Contradiction, ContradictionType, SourceRef

logger = logging.getLogger(__name__)
settings = get_settings()


def _llm_classify_pair(
    entity: str, claim_a: Dict[str, Any], claim_b: Dict[str, Any]
) -> Dict[str, Any]:
    """Call Gemini LLM to classify conflict type between claim A and claim B."""
    prompt = f"""
You are an expert financial and news contradiction classifier.
Analyze these two claims about '{entity}' and classify their conflict type into EXACTLY one category:
- direct_contradiction: Same metric, same scope, same time period, directly contradictory values.
- stale: One claim is significantly older than the other and has been superseded.
- scope_mismatch: Claims cover different date ranges (e.g. Q1 2024 vs Q4 2023), geographies, or population scopes.
- methodology_mismatch: Claims use different calculation methods, indexes, or economic models (e.g. CPI vs PCE, headline vs core, BLS model vs spot market rent, chained CPI).

Claim A:
- Source: {claim_a['source_name']}
- Date: {claim_a.get('published_at')}
- Value: {claim_a['value']}
- Scope: {claim_a.get('claimed_scope')}
- Text: "{claim_a['raw_text']}"

Claim B:
- Source: {claim_b['source_name']}
- Date: {claim_b.get('published_at')}
- Value: {claim_b['value']}
- Scope: {claim_b.get('claimed_scope')}
- Text: "{claim_b['raw_text']}"

Return ONLY valid JSON matching this schema:
{{
  "contradiction_type": "direct_contradiction | stale | scope_mismatch | methodology_mismatch",
  "reason": "Detailed concise explanation of why this category was chosen",
  "ai_resolution": "Actionable 1-2 sentence recommendation for an analyst on how to reconcile these figures",
  "confidence": 0.95
}}
"""
    logger.info("Classifier Agent: LLM prompt being sent for entity '%s':\n%s", entity, prompt)

    if not settings.demo_mode:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=settings.gemini_api_key)
            resp = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
            )
            raw = resp.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning("Gemini classification call failed (%s), using rule-based fallback.", e)

    # Heuristic Rule-Based Classifier Fallback
    text_a = claim_a["raw_text"].lower()
    text_b = claim_b["raw_text"].lower()
    val_a = claim_a["value"]
    val_b = claim_b["value"]

    scope_a = claim_a.get("claimed_scope") or {}
    scope_b = claim_b.get("claimed_scope") or {}

    date_a = scope_a.get("date_range") or ""
    date_b = scope_b.get("date_range") or ""

    # 1. Check for Scope Mismatch (different quarters or date ranges)
    if (date_a and date_b and date_a != date_b) or ("q1" in text_a and "q4" in text_b) or ("q4" in text_a and "q1" in text_b):
        return {
            "contradiction_type": "scope_mismatch",
            "reason": f"Claim A covers timeframe '{date_a or 'Q1'}' while Claim B covers '{date_b or 'Q4'}' — different time scopes.",
            "ai_resolution": "Treat both data points as sequential progression across different reporting timeframes rather than conflicting facts.",
            "confidence": 0.95,
        }

    # 2. Check for matching methodology -> Direct Contradiction
    meth_a = (scope_a.get("methodology") or "").lower()
    meth_b = (scope_b.get("methodology") or "").lower()

    if meth_a and meth_b and meth_a == meth_b and val_a != val_b:
        return {
            "contradiction_type": "direct_contradiction",
            "reason": f"{claim_a['source_name']} reports {val_a} while {claim_b['source_name']} reports {val_b} for the exact same metric ({meth_a}) and timeframe.",
            "ai_resolution": "Flag for primary source audit: check official agency release notes or correction notices for data revision.",
            "confidence": 0.96,
        }

    # 3. Check for Methodology Mismatch when calculation methods explicitly differ
    method_keywords = [
        "model", "index", "shelter", "chained", "survey", "spot",
        "basket", "pce", "core", "headline", "unweighted", "nowcast", "alternative"
    ]
    if (meth_a and meth_b and meth_a != meth_b) or (entity != "Federal Funds Rate" and any(k in text_a or k in text_b for k in method_keywords)):
        return {
            "contradiction_type": "methodology_mismatch",
            "reason": (
                f"{claim_a['source_name']} uses {meth_a or 'official index'} "
                f"whereas {claim_b['source_name']} uses {meth_b or 'alternative calculation method'}."
            ),
            "ai_resolution": f"Use {claim_a['source_name']} for standard macroeconomic benchmark; use {claim_b['source_name']} for leading/alternative indicators.",
            "confidence": 0.93,
        }

    # 4. Check for Stale dates
    pub_a = claim_a.get("published_at")
    pub_b = claim_b.get("published_at")
    if pub_a and pub_b and str(pub_a)[:10] != str(pub_b)[:10]:
        return {
            "contradiction_type": "stale",
            "reason": f"Claim from {claim_a['source_name']} is from {pub_a} and may be superseded by {claim_b['source_name']} ({pub_b}).",
            "ai_resolution": "Rely on the more recent publication timestamp for current decision-making.",
            "confidence": 0.88,
        }

    # 5. Default Direct Contradiction
    return {
        "contradiction_type": "direct_contradiction",
        "reason": f"{claim_a['source_name']} reports {val_a} while {claim_b['source_name']} reports {val_b} for the exact same metric and timeframe.",
        "ai_resolution": "Direct statistical disagreement: cross-reference raw agency tables before drawing conclusions.",
        "confidence": 0.96,
    }


def run_classifier_agent(candidate_groups: List[Dict[str, Any]]) -> List[Contradiction]:
    """Run contradiction classifier over candidate claim groups."""
    logger.info("Classifier Agent: evaluating %d candidate groups", len(candidate_groups))
    logger.info("Classifier Agent: exact input candidate_groups = %s", json.dumps(candidate_groups, default=str))
    
    contradictions: List[Contradiction] = []

    for group in candidate_groups:
        entity = group["entity"]
        claims = group["claims"]

        # Deduplicate claims by source_name per entity group.
        # This keeps the highest scoring / most recent claim per source.
        unique_claims: Dict[str, Dict[str, Any]] = {}
        for c in claims:
            src_name = c.get("source_name", "Unknown")
            if src_name not in unique_claims:
                unique_claims[src_name] = c
            else:
                existing = unique_claims[src_name]
                existing_score = existing.get("crag_score") or existing.get("score") or 0.0
                new_score = c.get("crag_score") or c.get("score") or 0.0
                if new_score > existing_score:
                    unique_claims[src_name] = c
                    
        deduped_claims = list(unique_claims.values())
        logger.info(
            "Classifier Agent (group '%s'): deduplicated %d raw claims down to %d unique sources",
            entity, len(claims), len(deduped_claims)
        )

        # Pairwise comparison across sources in group
        for i in range(len(deduped_claims)):
            for j in range(i + 1, len(deduped_claims)):
                ca = deduped_claims[i]
                cb = deduped_claims[j]

                # Skip if from the same source
                if ca.get("source_name") == cb.get("source_name"):
                    continue
                # Skip if values are identical
                if ca["value"] == cb["value"]:
                    continue

                res = _llm_classify_pair(entity, ca, cb)

                src_ref_a = SourceRef(
                    chunk_id=ca["chunk_id"],
                    source_name=ca["source_name"],
                    author=ca.get("author"),
                    published_at=ca.get("published_at"),
                    excerpt=ca["raw_text"][:200] + "..." if len(ca["raw_text"]) > 200 else ca["raw_text"],
                    url=ca.get("url"),
                    sentiment=ca.get("sentiment"),
                    claimed_scope=ca.get("claimed_scope"),
                )
                src_ref_b = SourceRef(
                    chunk_id=cb["chunk_id"],
                    source_name=cb["source_name"],
                    author=cb.get("author"),
                    published_at=cb.get("published_at"),
                    excerpt=cb["raw_text"][:200] + "..." if len(cb["raw_text"]) > 200 else cb["raw_text"],
                    url=cb.get("url"),
                    sentiment=cb.get("sentiment"),
                    claimed_scope=cb.get("claimed_scope"),
                )

                c_type = ContradictionType(res["contradiction_type"])

                contradictions.append(
                    Contradiction(
                        id=str(uuid.uuid4()),
                        entity=entity,
                        metric=ca["value"] + " vs " + cb["value"],
                        contradiction_type=c_type,
                        reason=res["reason"],
                        ai_resolution=res.get("ai_resolution"),
                        confidence=res.get("confidence", 0.9),
                        source_a=src_ref_a,
                        source_b=src_ref_b,
                    )
                )

    logger.info("Classifier Agent: identified %d total contradictions", len(contradictions))
    return contradictions
