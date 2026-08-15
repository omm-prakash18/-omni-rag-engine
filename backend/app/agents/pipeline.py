"""
app/agents/pipeline.py — Optimized LangGraph Pipeline Orchestrator with Phase A Features.

Architecture:
1. Shared Cache — LRU query hash lookup
2. Node 0: Triage / Gate Agent — Fast classification & early exit for off-topic/vague/out-of-corpus queries
3. Node 1 & 3: Vector Agent + Graph Agent — Parallel retrieval execution
4. Node 2: CRAG Agent — Knowledge refinement & relevance confidence check
5. Node 4: Synthesizer Agent — Claim merging & Lost-in-Middle reordering
6. Feature A2: Consensus Strength Indicator computation
7. Conditional Edge: Early Exit if 0 claim conflicts exist across candidate groups or for single_fact queries
8. Node 5: Contradiction Classifier — Entity-group batched structured classification
9. Feature A1: Source Reliability badge enrichment on GraphNodes
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict

from app.agents.classifier import run_classifier_agent
from app.agents.crag import run_crag_agent
from app.agents.graph_agent import run_graph_agent
from app.agents.synthesizer import run_synthesizer_agent
from app.agents.triage import run_triage_agent
from app.agents.vector_agent import run_vector_agent
from app.schemas.api import Contradiction, GraphData, GraphEdge, GraphNode, QueryResponse
from app.services.cache import get_cached_response, set_cached_response
from app.services.consensus import compute_all_consensus
from app.services.reliability import get_cached_reliability_badge

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    query: str
    top_k: int
    triage_category: str
    vector_results: List[Dict[str, Any]]
    graph_results: List[Dict[str, Any]]
    candidate_groups: List[Dict[str, Any]]
    contradictions: List[Contradiction]
    steps: List[str]


async def run_omni_pipeline(query: str, top_k: int = 5) -> QueryResponse:
    """
    Executes the optimized LangGraph pipeline with Phase A feature enrichments.
    """
    from app.config import get_settings
    settings = get_settings()
    steps = []

    # 0. Check Shared Query Cache
    cached_res = get_cached_response(query)
    if cached_res:
        cached_res.cached = True
        return cached_res

    # 1. Node 0: Triage / Gate Agent
    triage_res = run_triage_agent(query)
    category = triage_res["category"]
    steps.append(f"0. Triage Agent: Classified query as '{category}' ({triage_res['reason']})")

    # Early Exit for Gated Queries (off_topic, too_vague, no_data_expected)
    if category in ("off_topic", "too_vague", "no_data_expected"):
        steps.append(f"   ✓ Pipeline gated out — returning direct response immediately without retrieval.")
        res = QueryResponse(
            query=query,
            contradictions=[],
            graph=GraphData(nodes=[], edges=[]),
            consensus_summary={"summary": "0 sources reporting", "consensus_pct": 0.0},
            steps=steps,
            cached=False,
            demo_mode=settings.demo_mode,
        )
        set_cached_response(query, res)
        return res

    # 2. Node Execution based on Triage Category
    vector_results: List[Dict[str, Any]] = []
    graph_results: List[Dict[str, Any]] = []

    if category == "single_fact":
        steps.append("1. Vector Agent: Querying Qdrant vector store (single_fact route)...")
        steps.append("   ✓ Graph Agent: Skipped for single_fact query.")
        raw_vector_results = run_vector_agent(query, top_k=top_k)
        steps.append(f"   ✓ Vector Agent retrieved {len(raw_vector_results)} raw semantic chunks")

        vector_results, crag_metrics = run_crag_agent(query, raw_vector_results)
        steps.append(
            f"   ✓ CRAG Action: {crag_metrics['action']} | "
            f"Confidence: {crag_metrics['confidence']} | "
            f"Raw {crag_metrics['raw_count']} → Refined {crag_metrics['refined_count']} chunks"
        )
    else:
        steps.append("1. Retrieval Nodes: Running Vector Agent and Graph Agent concurrently...")
        
        async def fetch_vector():
            return await asyncio.to_thread(run_vector_agent, query, top_k)

        async def fetch_graph():
            try:
                return await run_graph_agent(query)
            except Exception as e:
                logger.warning("Graph Agent parallel task failed: %s", e)
                return []

        raw_vector_results, graph_results = await asyncio.gather(fetch_vector(), fetch_graph())
        steps.append(f"   ✓ Vector Agent retrieved {len(raw_vector_results)} raw chunks")
        steps.append(f"   ✓ Graph Agent retrieved {len(graph_results)} subgraph nodes")

        steps.append("2. CRAG Agent: Evaluating retrieval confidence and refining claims...")
        vector_results, crag_metrics = run_crag_agent(query, raw_vector_results)
        steps.append(
            f"   ✓ CRAG Action: {crag_metrics['action']} | "
            f"Confidence: {crag_metrics['confidence']} | "
            f"Raw {crag_metrics['raw_count']} → Refined {crag_metrics['refined_count']} chunks"
        )

        if crag_metrics['action'] in ("LOW_INTENT_SKIPPED", "LOW_RELEVANCE_REJECTED"):
            steps.append("   ⚠ CRAG Evaluator: Low relevance. Bypassing contradiction synthesis.")
            res = QueryResponse(
                query=query,
                contradictions=[],
                graph=GraphData(nodes=[], edges=[]),
                consensus_summary={"summary": "0 relevant claims found", "consensus_pct": 0.0},
                steps=steps,
                cached=False,
                demo_mode=settings.demo_mode,
            )
            set_cached_response(query, res)
            return res

    # 3. Node 4: Synthesizer Agent
    steps.append("3. Synthesizer Agent: Merging claims and grouping by entity × metric...")
    candidate_groups = run_synthesizer_agent(query, vector_results, graph_results)
    steps.append(f"   ✓ Synthesizer formed {len(candidate_groups)} claim candidate groups")

    # Feature A2: Compute Consensus Strength Indicators across candidate groups
    consensus_metrics_list = compute_all_consensus(candidate_groups)
    primary_consensus = consensus_metrics_list[0] if consensus_metrics_list else {"summary": "No active claims", "consensus_pct": 100.0}
    steps.append(f"   ✓ Consensus Indicator: {primary_consensus['consensus_summary']}")

    # Early Exit for Classifier: check if any candidate group has conflicting claim values
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
        contradictions = run_classifier_agent(candidate_groups)
        steps.append(f"   ✓ Classifier identified {len(contradictions)} active contradictions")

    # 5. Build React Flow GraphData & Feature A1 Source Reliability Badges
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

            # Feature A1: Retrieve source reliability badge
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

    # Add contradiction conflict edges between sources
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

    res = QueryResponse(
        query=query,
        contradictions=contradictions,
        graph=GraphData(nodes=nodes, edges=edges),
        consensus_summary=primary_consensus,
        steps=steps,
        cached=False,
        demo_mode=settings.demo_mode,
    )
    set_cached_response(query, res)
    return res
