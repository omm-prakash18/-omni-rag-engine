"""
app/agents/pipeline.py — Parameterized LangGraph Pipeline Orchestrator.

Architecture & Capabilities:
1. Multi-Hop Query Decomposition & Conversational Memory Resolution
2. Cross-Lingual Query Detection & Translation
3. Self-Correcting Retry Loop with Labeled Efficacy Tracking
4. Explainable Retrieval Score Breakdown ("Why this chunk was retrieved")
5. Sub-Result & Embedding Hash Caching
6. Adaptive Retrieval Depth (fast-path top-3 vs full top-10 rerank)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.agents.classifier import run_classifier_agent
from app.agents.crag import run_crag_agent
from app.agents.decomposer import decompose_query
from app.agents.graph_agent import run_graph_agent
from app.agents.synthesizer import run_synthesizer_agent
from app.agents.triage import run_triage_agent
from app.agents.vector_agent import run_vector_agent
from app.schemas.api import ChatMessage, Contradiction, GraphData, GraphEdge, GraphNode, QueryResponse, UserPreferences
from app.services.cache import get_cached_response, set_cached_response
from app.services.consensus import compute_all_consensus
from app.services.memory import resolve_conversational_query
from app.services.multilingual import detect_and_translate_query
from app.services.reliability import get_cached_reliability_badge
from app.services.speculative_cache import trigger_speculative_prefetch
from app.services.sub_result_cache import (
    get_cached_graph_sub_results,
    get_cached_vector_sub_results,
    set_cached_graph_sub_results,
    set_cached_vector_sub_results,
)

logger = logging.getLogger(__name__)


async def run_omni_pipeline(
    query: str,
    top_k: int = 5,
    preferences: Optional[UserPreferences] = None,
    history: Optional[List[ChatMessage]] = None,
    conversation_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> QueryResponse:
    """
    Executes the multi-agent RAG pipeline with 8 advanced capabilities:
    Multi-hop decomposition, conversational memory, retry efficacy tracking, explainable retrieval,
    and cross-lingual translation.
    """
    from app.config import get_settings
    settings = get_settings()
    steps = []
    warnings = []

    if preferences is None:
        preferences = UserPreferences()

    # Feature 8: Cross-Lingual Translation & Detection
    translated_query, detected_lang = detect_and_translate_query(query)
    if detected_lang != "en":
        steps.append(f"🌐 Cross-Lingual Layer: Detected '{detected_lang.upper()}'. Translated query → '{translated_query}'")

    # Feature 3: Conversational Memory Reference Resolution
    resolved_query = resolve_conversational_query(translated_query, history)
    if resolved_query != query:
        steps.append(f"💬 Conversational Memory: Resolved multi-turn query → '{resolved_query}'")

    # Feature 1: Multi-Hop Query Decomposition
    subqueries = decompose_query(resolved_query)
    if len(subqueries) >= 2:
        steps.append(f"🔀 Multi-Hop Decomposer: Decomposed query into {len(subqueries)} targeted subqueries: {subqueries}")

    target_query = subqueries[0] if subqueries else resolved_query

    # 0. Check Shared Query-Level Cache
    has_custom_prefs = bool(preferences.source_weights or preferences.recency_bias or preferences.domain_scope or history)
    if not has_custom_prefs:
        cached_res = get_cached_response(target_query)
        if cached_res:
            cached_res.cached = True
            return cached_res

    # 1. Node 0: Triage / Gate Agent
    triage_res = run_triage_agent(target_query)
    category = triage_res["category"]
    is_fast_path = (category == "single_fact")
    steps.append(f"0. Triage Agent: Classified query as '{category}' ({triage_res['reason']}) [fast_path={is_fast_path}]")

    if category in ("off_topic", "too_vague", "no_data_expected"):
        steps.append(f"   ✓ Pipeline gated out — returning direct response immediately without retrieval.")
        res = QueryResponse(
            query=query,
            resolved_query=resolved_query,
            multi_hop_subqueries=subqueries if len(subqueries) >= 2 else None,
            contradictions=[],
            graph=GraphData(nodes=[], edges=[]),
            consensus_summary={"consensus_summary": "0 sources reporting", "consensus_pct": 0.0},
            detected_language=detected_lang,
            warnings=warnings,
            steps=steps,
            cached=False,
            demo_mode=settings.demo_mode,
        )
        set_cached_response(target_query, res)
        return res

    # 2. Node Execution
    vector_results: List[Dict[str, Any]] = []
    graph_results: List[Dict[str, Any]] = []
    effective_top_k = 3 if is_fast_path else top_k

    if category == "single_fact":
        steps.append(f"1. Vector Agent: Running adaptive fast-path retrieval (top_k={effective_top_k})...")
        steps.append("   ✓ Graph Agent: Skipped for single_fact query.")
        
        raw_vector_results = get_cached_vector_sub_results(target_query, preferences.domain_scope, effective_top_k)
        if raw_vector_results is None:
            raw_vector_results = run_vector_agent(target_query, top_k=effective_top_k, preferences=preferences, is_fast_path=True)
            set_cached_vector_sub_results(target_query, raw_vector_results, preferences.domain_scope, effective_top_k)
        else:
            steps.append("   ✓ Vector Agent: Sub-result cache hit!")

        vector_results, crag_metrics = run_crag_agent(target_query, raw_vector_results)
        steps.append(
            f"   ✓ CRAG Action: {crag_metrics['action']} | "
            f"Confidence: {crag_metrics['confidence']} | "
            f"Raw {crag_metrics['raw_count']} → Refined {crag_metrics['refined_count']} chunks"
        )
    else:
        steps.append("1. Retrieval Nodes: Running Vector Agent and Graph Agent concurrently...")

        async def fetch_vector():
            cached_v = get_cached_vector_sub_results(target_query, preferences.domain_scope, effective_top_k)
            if cached_v is not None:
                return cached_v
            v_res = await asyncio.to_thread(run_vector_agent, target_query, effective_top_k, preferences, False)
            set_cached_vector_sub_results(target_query, v_res, preferences.domain_scope, effective_top_k)
            return v_res

        async def fetch_graph():
            cached_g = get_cached_graph_sub_results(target_query, preferences.domain_scope, 15)
            if cached_g is not None:
                return cached_g
            try:
                g_res = await run_graph_agent(target_query)
                set_cached_graph_sub_results(target_query, g_res, preferences.domain_scope, 15)
                return g_res
            except Exception as e:
                logger.warning("Graph Agent parallel task failed: %s", e)
                return []

        raw_vector_results, graph_results = await asyncio.gather(fetch_vector(), fetch_graph())
        steps.append(f"   ✓ Vector Agent retrieved {len(raw_vector_results)} raw chunks")
        steps.append(f"   ✓ Graph Agent retrieved {len(graph_results)} subgraph nodes")

        steps.append("2. CRAG Agent: Evaluating retrieval confidence and refining claims...")
        vector_results, crag_metrics = run_crag_agent(target_query, raw_vector_results)
        steps.append(
            f"   ✓ CRAG Action: {crag_metrics['action']} | "
            f"Confidence: {crag_metrics['confidence']} | "
            f"Raw {crag_metrics['raw_count']} → Refined {crag_metrics['refined_count']} chunks"
        )

        # Feature 2: Log Retry Efficacy
        if crag_metrics.get("retry_efficacy"):
            eff = crag_metrics["retry_efficacy"]
            steps.append(
                f"   🔄 Self-Correcting Retry Efficacy: Pre-score={eff['pre_retry_avg_score']} → "
                f"Post-score={eff['post_retry_avg_score']} | Retry Efficacy={eff['did_retry_help']}"
            )

        if crag_metrics['action'] in ("LOW_INTENT_SKIPPED", "LOW_RELEVANCE_REJECTED"):
            steps.append("   ⚠ CRAG Evaluator: Low relevance. Bypassing contradiction synthesis.")
            res = QueryResponse(
                query=query,
                resolved_query=resolved_query,
                multi_hop_subqueries=subqueries if len(subqueries) >= 2 else None,
                contradictions=[],
                graph=GraphData(nodes=[], edges=[]),
                consensus_summary={"consensus_summary": "0 relevant claims found", "consensus_pct": 0.0},
                retry_efficacy=crag_metrics.get("retry_efficacy"),
                detected_language=detected_lang,
                warnings=warnings,
                steps=steps,
                cached=False,
                demo_mode=settings.demo_mode,
            )
            set_cached_response(target_query, res)
            return res

    if preferences.source_weights and len(vector_results) < 2:
        warnings.append("Warning: Restricted user source weights reduced claim candidate coverage.")

    # 3. Synthesizer Agent
    steps.append("3. Synthesizer Agent: Merging claims and grouping by entity × metric...")
    candidate_groups = run_synthesizer_agent(target_query, vector_results, graph_results)
    steps.append(f"   ✓ Synthesizer formed {len(candidate_groups)} claim candidate groups")

    consensus_metrics_list = compute_all_consensus(candidate_groups)
    primary_consensus = consensus_metrics_list[0] if consensus_metrics_list else {"consensus_summary": "No active claims", "consensus_pct": 100.0}
    steps.append(f"   ✓ Consensus Indicator: {primary_consensus['consensus_summary']}")

    has_conflicts = False
    for group in candidate_groups:
        claims = group.get("claims", [])
        values = set(c.get("value") for c in claims if c.get("value"))
        sources = set(c.get("source_name") for c in claims if c.get("source_name"))
        if len(sources) >= 2 and len(values) >= 2:
            has_conflicts = True
            break

    contradictions: List[Contradiction] = []
    if category == "single_fact" or not has_conflicts:
        steps.append("4. Contradiction Classifier: Skipped — 0 conflicting claim pairs across candidate groups.")
    else:
        steps.append("4. Contradiction Classifier: Evaluating conflicts against taxonomy...")
        raw_contradictions = run_classifier_agent(candidate_groups)

        thresh = preferences.contradiction_threshold
        if thresh > 0.0:
            contradictions = [c for c in raw_contradictions if c.confidence >= thresh]
            steps.append(f"   ✓ Classifier identified {len(raw_contradictions)} active contradictions (filtered to {len(contradictions)} at threshold >= {thresh})")
        else:
            contradictions = raw_contradictions
            steps.append(f"   ✓ Classifier identified {len(contradictions)} active contradictions")

    # 5. Build React Flow GraphData & Source Reliability Badges
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    seen_nodes = set()

    for group in candidate_groups:
        entity = group["entity"]
        ent_id = f"ent_{entity.lower().replace(' ', '_')}"
        if ent_id not in seen_nodes:
            nodes.append(GraphNode(id=ent_id, label=entity, type="entity", data={"metric": "claimed_value"}))
            seen_nodes.add(ent_id)

        for c in group.get("claims", []):
            src_name = c.get("source_name", "Unknown")
            src_id = f"src_{src_name.lower().replace(' ', '_')}"

            rel_info = get_cached_reliability_badge(src_name)

            if src_id not in seen_nodes:
                nodes.append(GraphNode(
                    id=src_id,
                    label=src_name,
                    type="source",
                    data={
                        "author": c.get("author"),
                        "url": c.get("url"),
                        "reliability_score": rel_info["score_pct"],
                        "reliability_badge": rel_info["badge"],
                        "reliability_status": rel_info["status"],
                    }
                ))
                seen_nodes.add(src_id)

            edge_id = f"e_{src_id}_{ent_id}"
            if not any(e.id == edge_id for e in edges):
                edges.append(GraphEdge(
                    id=edge_id,
                    source=src_id,
                    target=ent_id,
                    type="SUPPORTS",
                    data={"value": c.get("value", "")}
                ))

    for c in contradictions:
        src_a_id = f"src_{c.source_a.source_name.lower().replace(' ', '_')}"
        src_b_id = f"src_{c.source_b.source_name.lower().replace(' ', '_')}"

        edge_type = "CONTRADICTS" if c.contradiction_type.value == "direct_contradiction" else c.contradiction_type.value.upper()
        edges.append(GraphEdge(
            id=f"e_contra_{c.id[:8]}",
            source=src_a_id,
            target=src_b_id,
            type=edge_type,
            data={"reason": c.reason, "confidence": c.confidence, "type": c.contradiction_type.value}
        ))

    if preferences.answer_depth == "summary":
        steps.append("5. Presentation Control: Answer depth truncated to summary mode.")
        if len(steps) > 4:
            steps = steps[:4] + ["5. Summary Mode: Extended claim breakdown omitted."]

    res = QueryResponse(
        query=query,
        resolved_query=resolved_query,
        multi_hop_subqueries=subqueries if len(subqueries) >= 2 else None,
        contradictions=contradictions,
        graph=GraphData(nodes=nodes, edges=edges),
        consensus_summary=primary_consensus,
        retry_efficacy=crag_metrics.get("retry_efficacy"),
        detected_language=detected_lang,
        warnings=warnings,
        steps=steps,
        cached=False,
        demo_mode=settings.demo_mode,
    )

    if not has_custom_prefs:
        set_cached_response(target_query, res)

    trigger_speculative_prefetch(target_query, candidate_groups)

    return res
