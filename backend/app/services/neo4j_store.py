"""
app/services/neo4j_store.py — Neo4j graph store operations.

Node types: Entity, Claim, Source
Edge types: CLAIMS, CONTRADICTS, SUPERSEDES, SUPPORTS

All operations are no-ops (returning empty results) when Neo4j is not available,
so the rest of the pipeline degrades gracefully to vector-only mode.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _driver():
    from app.database import get_neo4j, neo4j_available
    if not neo4j_available:
        return None
    return get_neo4j()


# ── Write operations ──────────────────────────────────────────────────────────

async def upsert_source(source_id: str, name: str) -> bool:
    driver = _driver()
    if not driver:
        return False
    async with driver.session() as session:
        await session.run(
            "MERGE (s:Source {id: $id}) SET s.name = $name",
            id=source_id, name=name,
        )
    return True


async def upsert_entity(entity_id: str, name: str, entity_type: str) -> bool:
    driver = _driver()
    if not driver:
        return False
    async with driver.session() as session:
        await session.run(
            "MERGE (e:Entity {id: $id}) SET e.name = $name, e.type = $type",
            id=entity_id, name=name, type=entity_type,
        )
    return True


async def upsert_claim(
    chunk_id: str,
    source_id: str,
    entity_id: str,
    predicate: str,
    value: str,
    published_at: Optional[str] = None,
    claimed_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    driver = _driver()
    if not driver:
        return False
    async with driver.session() as session:
        # Create Claim node
        await session.run(
            """
            MERGE (c:Claim {chunk_id: $chunk_id, entity_id: $entity_id, predicate: $predicate})
            SET c.value = $value, c.published_at = $published_at,
                c.claimed_scope = $claimed_scope
            """,
            chunk_id=chunk_id,
            entity_id=entity_id,
            predicate=predicate,
            value=value,
            published_at=published_at,
            claimed_scope=str(claimed_scope) if claimed_scope else None,
        )
        # CLAIMS edge: Entity ──[CLAIMS]──▶ Claim
        await session.run(
            """
            MATCH (e:Entity {id: $entity_id})
            MATCH (c:Claim {chunk_id: $chunk_id, entity_id: $entity_id, predicate: $predicate})
            MERGE (e)-[:CLAIMS]->(c)
            """,
            entity_id=entity_id, chunk_id=chunk_id, predicate=predicate,
        )
        # CLAIMS edge: Source ──[CLAIMS]──▶ Claim
        await session.run(
            """
            MATCH (s:Source {id: $source_id})
            MATCH (c:Claim {chunk_id: $chunk_id, entity_id: $entity_id, predicate: $predicate})
            MERGE (s)-[:CLAIMS]->(c)
            """,
            source_id=source_id, chunk_id=chunk_id,
            entity_id=entity_id, predicate=predicate,
        )
    return True


async def add_contradicts_edge(
    chunk_id_a: str, chunk_id_b: str, entity_id: str,
    predicate: str, reason: str,
) -> bool:
    driver = _driver()
    if not driver:
        return False
    async with driver.session() as session:
        await session.run(
            """
            MATCH (a:Claim {chunk_id: $chunk_a, entity_id: $entity_id, predicate: $pred})
            MATCH (b:Claim {chunk_id: $chunk_b, entity_id: $entity_id, predicate: $pred})
            MERGE (a)-[r:CONTRADICTS]->(b)
            SET r.reason = $reason
            """,
            chunk_a=chunk_id_a, chunk_b=chunk_id_b,
            entity_id=entity_id, pred=predicate, reason=reason,
        )
    return True


# ── Query operations ──────────────────────────────────────────────────────────

async def query_subgraph(entity_names: List[str], limit: int = 50) -> List[Dict[str, Any]]:
    """Return Claims + Sources for given entity names. Used by the graph agent."""
    driver = _driver()
    if not driver:
        return []
    async with driver.session() as session:
        result = await session.run(
            """
            UNWIND $names AS name
            MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower(name)
            MATCH (e)-[:CLAIMS]->(c:Claim)<-[:CLAIMS]-(s:Source)
            RETURN e.name AS entity, e.id AS entity_id,
                   c.predicate AS predicate, c.value AS value,
                   c.published_at AS published_at, c.claimed_scope AS claimed_scope,
                   c.chunk_id AS chunk_id,
                   s.name AS source_name, s.id AS source_id
            LIMIT $limit
            """,
            names=entity_names, limit=limit,
        )
        return [dict(record) async for record in result]


async def query_contradictions_in_graph(limit: int = 100) -> List[Dict[str, Any]]:
    """Return all CONTRADICTS edges already stored in the graph."""
    driver = _driver()
    if not driver:
        return []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (a:Claim)-[r:CONTRADICTS]->(b:Claim)
            RETURN a.chunk_id AS chunk_a, b.chunk_id AS chunk_b,
                   a.entity_id AS entity_id, a.predicate AS predicate,
                   r.reason AS reason
            LIMIT $limit
            """,
            limit=limit,
        )
        return [dict(record) async for record in result]
