"""
app/agents/pipeline.py — LangGraph Pipeline Orchestrator with CRAG (Corrective RAG).

Nodes:
1. Vector Agent — Qdrant semantic search
2. CRAG Agent — Corrective Retrieval-Augmented Generation evaluation & query expansion
3. Graph Agent — Neo4j Cypher query
4. Synthesizer Agent — Merge & group claims by entity x metric
5. Contradiction Classifier — 4-type taxonomy classification
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict

from app.agents.classifier import run_classifier_agent
from app.agents.crag import run_crag_agent
from app.agents.graph_agent import run_graph_agent
from app.agents.synthesizer import run_synthesizer_agent
from app.agents.vector_agent import run_vector_agent
from app.schemas.api import Contradiction, GraphData, GraphEdge, GraphNode, QueryResponse

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    query: str
    top_k: int
    vector_results: List[Dict[str, Any]]
    graph_results: List[Dict[str, Any]]
    candidate_groups: List[Dict[str, Any]]
    contradictions: List[Contradiction]
    steps: List[str]


async def run_omni_pipeline(query: str, top_k: int = 10) -> QueryResponse:
    """
    Executes the LangGraph agent pipeline enhanced with Corrective RAG (CRAG).
    Returns structured QueryResponse with contradictions, graph nodes/edges, and reasoning steps.
    """
    from app.config import get_settings
    settings = get_settings()
    steps = []

    # Start Node 3 (Graph Agent) concurrently as a background task
    graph_task: asyncio.Task = asyncio.create_task(run_graph_agent(query))

    # Node 1: Vector Agent
    steps.append("1. Vector Agent: Querying Qdrant vector store...")
    raw_vector_results = run_vector_agent(query, top_k=top_k)
    steps.append(f"   ✓ Vector Agent retrieved {len(raw_vector_results)} raw semantic chunks")

    # Node 2: CRAG Agent (Corrective Retrieval-Augmented Generation)
    steps.append("2. CRAG Agent: Evaluating retrieval confidence and refining claims...")
    vector_results, crag_metrics = run_crag_agent(query, raw_vector_results)
    steps.append(
        f"   ✓ CRAG Action: {crag_metrics['action']} | "
        f"Confidence: {crag_metrics['confidence']} | "
        f"Raw {crag_metrics['raw_count']} → Refined {crag_metrics['refined_count']} chunks"
    )

    # Node 3: Graph Agent (await the background task, handle errors gracefully)
    steps.append("3. Graph Agent: Querying Neo4j entity graph...")
    try:
        graph_results = await graph_task
        steps.append(f"   ✓ Graph Agent retrieved {len(graph_results)} subgraph nodes")
    except Exception as graph_err:
        logger.warning("Graph Agent failed (non-fatal): %s", graph_err)
        graph_results = []
        steps.append("   ⚠ Graph Agent unavailable — continuing without graph context")

    # Node 4: Synthesizer Agent
    steps.append("4. Synthesizer Agent: Merging claims and grouping by entity × metric...")
    candidate_groups = run_synthesizer_agent(query, vector_results, graph_results)
    steps.append(f"   ✓ Synthesizer formed {len(candidate_groups)} claim candidate groups")

    # Node 5: Contradiction Classifier
    steps.append("5. Contradiction Classifier: Evaluating conflicts against taxonomy...")
    contradictions = run_classifier_agent(candidate_groups)
    steps.append(f"   ✓ Classifier identified {len(contradictions)} active contradictions")

    # Build React Flow compatible GraphData from contradictions and vector results
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    seen_nodes = set()

    for c in contradictions:
        # Entity node
        ent_id = f"ent_{c.entity.lower().replace(' ', '_')}"
        if ent_id not in seen_nodes:
            nodes.append(GraphNode(id=ent_id, label=c.entity, type="entity", data={"metric": c.metric}))
            seen_nodes.add(ent_id)

        # Source A node
        src_a_id = f"src_{c.source_a.source_name.lower().replace(' ', '_')}"
        if src_a_id not in seen_nodes:
            nodes.append(GraphNode(
                id=src_a_id,
                label=c.source_a.source_name,
                type="source",
                data={"author": c.source_a.author, "url": c.source_a.url}
            ))
            seen_nodes.add(src_a_id)

        # Source B node
        src_b_id = f"src_{c.source_b.source_name.lower().replace(' ', '_')}"
        if src_b_id not in seen_nodes:
            nodes.append(GraphNode(
                id=src_b_id,
                label=c.source_b.source_name,
                type="source",
                data={"author": c.source_b.author, "url": c.source_b.url}
            ))
            seen_nodes.add(src_b_id)

        # Support edges
        edges.append(GraphEdge(
            id=f"e_{src_a_id}_{ent_id}", source=src_a_id, target=ent_id, type="SUPPORTS", data={"value": c.source_a.excerpt[:40]}
        ))
        edges.append(GraphEdge(
            id=f"e_{src_b_id}_{ent_id}", source=src_b_id, target=ent_id, type="SUPPORTS", data={"value": c.source_b.excerpt[:40]}
        ))

        # Contradiction edge between sources
        edge_type = "CONTRADICTS" if c.contradiction_type.value == "direct_contradiction" else c.contradiction_type.value.upper()
        edges.append(GraphEdge(
            id=f"e_contra_{c.id[:8]}",
            source=src_a_id,
            target=src_b_id,
            type=edge_type,
            data={"reason": c.reason, "confidence": c.confidence, "type": c.contradiction_type.value}
        ))

    return QueryResponse(
        query=query,
        contradictions=contradictions,
        graph=GraphData(nodes=nodes, edges=edges),
        steps=steps,
        cached=False,
        demo_mode=settings.demo_mode,
    )
