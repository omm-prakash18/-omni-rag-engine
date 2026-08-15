"""
app/agents/graph_agent.py — Node 2: Graph Agent.

Queries Neo4j Cypher graph store for entities and relationships related to the query.
When Neo4j is unavailable, synthesizes entity-graph records from the in-memory vector
store so the Synthesizer Agent is not starved of graph-side data.

Debug logging:
- Logs the exact keywords sent to Cypher
- Logs the Cypher template being executed
- Logs WHY graph returns 0 (Neo4j absent vs empty vs no match)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Cypher template logged verbatim so debug output is traceable
_CYPHER_TEMPLATE = """
UNWIND $names AS name
MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower(name)
MATCH (e)-[:CLAIMS]->(c:Claim)<-[:CLAIMS]-(s:Source)
RETURN e.name AS entity, e.id AS entity_id,
       c.predicate AS predicate, c.value AS value,
       c.published_at AS published_at, c.claimed_scope AS claimed_scope,
       c.chunk_id AS chunk_id,
       s.name AS source_name, s.id AS source_id
LIMIT $limit
"""


def _extract_entity_keywords(query: str) -> List[str]:
    """Extract key search terms from user query for Cypher query matching."""
    stopwords = {
        "what", "is", "the", "for", "in", "of", "and", "a", "an",
        "rate", "latest", "current", "show", "me", "find", "outlook",
    }
    words = re.findall(r"\w+", query)
    keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    logger.debug(
        "Graph Agent: entity keywords extracted from query '%s' → %s",
        query, keywords,
    )
    return keywords or ["inflation", "gdp", "fed"]


def _build_graph_records_from_vector_store(keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Fallback: synthesize entity-graph records from the in-memory vector store.
    This ensures the Synthesizer Agent has multi-source entity data when Neo4j
    is unavailable, preserving the pipeline's claim-grouping logic.
    """
    from app.services.qdrant_store import _in_memory_store
    records: List[Dict[str, Any]] = []
    kw_lower = [k.lower() for k in keywords]

    for chunk_id, data in _in_memory_store.items():
        payload = data.get("payload", {})
        raw_text = payload.get("raw_text", "").lower()
        title     = payload.get("title", "").lower()
        combined  = raw_text + " " + title

        if not any(kw in combined for kw in kw_lower):
            continue

        # Determine entity name matching extraction logic in synthesizer
        if "gdp" in combined:
            entity_name = "US GDP Growth"
            predicate   = "gdp_growth_rate"
        elif "fed" in combined or "interest rate" in combined or "fomc" in combined:
            entity_name = "Federal Funds Rate"
            predicate   = "benchmark_interest_rate"
        elif "inflation" in combined or "cpi" in combined or "pce" in combined:
            entity_name = "US Inflation Rate"
            predicate   = "inflation_rate"
        else:
            entity_name = "Economic Indicator"
            predicate   = "economic_metric"

        # Extract a value so the synthesizer can use it
        import re as _re
        vals = _re.findall(r"(\d+(?:\.\d+)?%)", payload.get("raw_text", ""))
        value = vals[0] if vals else "N/A"

        records.append({
            "entity":      entity_name,
            "entity_id":   entity_name.lower().replace(" ", "_"),
            "predicate":   predicate,
            "value":       value,
            "published_at":payload.get("published_at"),
            "claimed_scope": payload.get("claimed_scope", {}),
            "chunk_id":    chunk_id,
            "source_name": payload.get("source_name", "Unknown"),
            "source_id":   payload.get("source_id"),
        })

    logger.info(
        "Graph Agent (vector fallback): synthesized %d entity-graph records from in-memory store",
        len(records),
    )
    return records


async def run_graph_agent(query: str) -> List[Dict[str, Any]]:
    """Query Neo4j graph store for subgraph matching query keywords.

    Falls back to in-memory vector store entity synthesis when Neo4j is unavailable.
    All decisions are logged so 0-result causes are always traceable.
    """
    from app.services.neo4j_store import query_subgraph
    from app.database import neo4j_available  # read the liveness flag directly

    logger.info("Graph Agent: querying graph for '%s'", query)
    keywords = _extract_entity_keywords(query)

    if not neo4j_available:
        logger.warning(
            "Graph Agent: Neo4j is NOT available (neo4j_available=False). "
            "Cypher query WILL NOT be sent. Would have searched keywords=%s with Cypher:\n%s",
            keywords, _CYPHER_TEMPLATE,
        )
        logger.warning(
            "Graph Agent: falling back to in-memory vector store entity synthesis."
        )
        fallback = _build_graph_records_from_vector_store(keywords)
        logger.info(
            "Graph Agent: returning %d records via vector-store fallback (Neo4j absent)",
            len(fallback),
        )
        return fallback

    # Neo4j is available — send real Cypher
    logger.info(
        "Graph Agent: sending Cypher to Neo4j | keywords=%s | template: %s",
        keywords, _CYPHER_TEMPLATE,
    )
    graph_results = await query_subgraph(keywords, limit=15)

    if len(graph_results) == 0:
        logger.warning(
            "Graph Agent: Neo4j query returned 0 rows for keywords=%s. "
            "Check: (1) MATCH (n) RETURN count(n) > 0 in Neo4j, "
            "(2) entity names at ingestion vs query keywords (case/normalization), "
            "(3) Cypher path Entity-[:CLAIMS]->Claim<-[:CLAIMS]-Source exists.",
            keywords,
        )

    logger.info("Graph Agent: found %d subgraph records (via Neo4j)", len(graph_results))
    return graph_results
