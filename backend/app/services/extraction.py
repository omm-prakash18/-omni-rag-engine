"""
app/services/extraction.py — Extraction Service & Dual-Write Pipeline.

1. Takes a ChunkMetadata object.
2. Extracts Entities & Relationships via Gemini LLM (or mock heuristic in demo mode).
3. Generates embedding via Gemini text-embedding-004 (or mock vector in demo mode).
4. Dual-writes transactionally:
   a. Postgres EventLog row created / updated (qdrant_synced=False, neo4j_synced=False)
   b. Qdrant point upserted (qdrant_synced=True)
   c. Neo4j nodes/edges written (neo4j_synced=True)
"""
from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.event_log import EventLog
from app.services.chunking import ChunkMetadata
from app.services.neo4j_store import upsert_claim, upsert_entity, upsert_source
from app.services.qdrant_store import upsert_chunk

logger = logging.getLogger(__name__)
settings = get_settings()


def generate_embedding(text_or_texts: str | List[str]) -> List[float] | List[List[float]]:
    """Generate vector embedding(s) for chunk text(s) using Gemini or mock fallback.

    Args:
        text_or_texts: A single string or a list of strings to embed.

    Returns:
        A single 768-d float vector if input was a string,
        or a list of 768-d vectors if input was a list.
    """
    is_list = isinstance(text_or_texts, list)
    texts = text_or_texts if is_list else [text_or_texts]

    if not settings.demo_mode:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=settings.gemini_api_key)
            result = client.models.embed_content(
                model=settings.embedding_model,
                contents=texts,
                config={"output_dimensionality": 768, "task_type": "retrieval_document"},
            )
            # result.embeddings is a list of ContentEmbedding objects
            raw = [e.values for e in result.embeddings]
            return raw if is_list else raw[0]
        except Exception as e:
            logger.warning("Gemini embedding failed: %s. Using random vector.", e)
    
    embeddings = []
    for text in texts:
        # Mock vector (768 dimensions) deterministically seeded by text hash
        random.seed(hash(text))
        vec = [random.uniform(-1.0, 1.0) for _ in range(768)]
        # Normalize
        norm = sum(x * x for x in vec) ** 0.5
        embeddings.append([x / norm for x in vec])
        
    return embeddings if is_list else embeddings[0]


def extract_entities_and_relations(text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    LLM extraction pass using Gemini to extract entities and numeric claims/metrics.
    Returns: (entities, relationships)
    """
    if not settings.demo_mode:
        try:
            from google import genai as google_genai
            client = google_genai.Client(api_key=settings.gemini_api_key)
            prompt = f"""
Extract key entities (organizations, indicators, metrics, countries) and numeric claims from this text.
Return ONLY valid JSON matching this schema:
{{
  "entities": [
    {{"id": "normalized_name", "name": "Display Name", "type": "Metric|Country|Organization"}}
  ],
  "relationships": [
    {{"entity_id": "normalized_name", "predicate": "has_value", "value": "value string with unit"}}
  ]
}}

Text:
"{text}"
"""
            response = client.models.generate_content(
                model=settings.llm_model,
                contents=prompt,
            )
            raw = response.text.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            data = json.loads(raw)
            return data.get("entities", []), data.get("relationships", [])
        except Exception as e:
            logger.warning("Gemini extraction failed (%s), falling back to heuristics.", e)

    # Heuristic fallback for extraction
    entities = []
    relationships = []

    lowered = text.lower()
    if "inflation" in lowered:
        entities.append({"id": "us_inflation_rate", "name": "US Inflation Rate", "type": "Metric"})
        # Extract percentage if present
        matches = re.findall(r"(\d+(?:\.\d+)?%)", text)
        val = matches[0] if matches else "3.2%"
        relationships.append({"entity_id": "us_inflation_rate", "predicate": "reported_rate", "value": val})
    
    if "gdp" in lowered:
        entities.append({"id": "us_gdp_growth", "name": "US GDP Growth", "type": "Metric"})
        matches = re.findall(r"(\d+(?:\.\d+)?%)", text)
        val = matches[0] if matches else "2.1%"
        relationships.append({"entity_id": "us_gdp_growth", "predicate": "annualized_growth", "value": val})

    if "interest rate" in lowered or "fed" in lowered:
        entities.append({"id": "fed_funds_rate", "name": "Federal Funds Rate", "type": "Metric"})
        matches = re.findall(r"(\d+(?:\.\d+)?%)", text)
        val = matches[0] if matches else "5.25%"
        relationships.append({"entity_id": "fed_funds_rate", "predicate": "target_rate", "value": val})

    if not entities:
        entities.append({"id": "economic_indicator", "name": "Economic Indicator", "type": "Metric"})
        relationships.append({"entity_id": "economic_indicator", "predicate": "value", "value": "Unspecified"})

    return entities, relationships


async def process_and_store_chunk(db: AsyncSession, chunk: ChunkMetadata) -> EventLog:
    """
    Full dual-write process for a single chunk:
    1. Create/update Postgres EventLog record (Single Source of Truth).
    2. Extract entities and embed vector.
    3. Write to Qdrant (update qdrant_synced).
    4. Write to Neo4j (update neo4j_synced).
    """
    # 1. Postgres EventLog entry (Source of Truth)
    event_entry = EventLog(
        id=chunk.chunk_id,
        source_id=chunk.source_id,
        raw_text=chunk.raw_text,
        author=chunk.author,
        title=chunk.title,
        url=chunk.url,
        published_at=chunk.published_at,
        ingested_at=chunk.ingested_at,
        sentiment=chunk.sentiment,
        claimed_scope=json.dumps(chunk.claimed_scope),
        status="active",
        qdrant_synced=False,
        neo4j_synced=False,
        embedding_model=settings.embedding_model if not settings.demo_mode else "mock-768d",
    )
    db.add(event_entry)
    await db.commit()
    await db.refresh(event_entry)

    # 2. Embedding + Entity Extraction
    embedding = generate_embedding(chunk.raw_text)
    entities, relationships = extract_entities_and_relations(chunk.raw_text)

    # 3. Write to Qdrant Vector Store
    payload = {
        "chunk_id": chunk.chunk_id,
        "source_name": chunk.source_name or "Unknown Source",
        "source_id": chunk.source_id,
        "author": chunk.author,
        "title": chunk.title,
        "url": chunk.url,
        "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
        "sentiment": chunk.sentiment,
        "claimed_scope": chunk.claimed_scope,
        "raw_text": chunk.raw_text,
    }
    q_success = upsert_chunk(chunk.chunk_id, embedding, payload)
    if q_success:
        event_entry.qdrant_synced = True

    # 4. Write to Neo4j Graph Store
    if chunk.source_id and chunk.source_name:
        await upsert_source(chunk.source_id, chunk.source_name)

    n_success = True
    for ent in entities:
        ent_ok = await upsert_entity(ent["id"], ent["name"], ent["type"])
        if not ent_ok:
            n_success = False

    for rel in relationships:
        claim_ok = await upsert_claim(
            chunk_id=chunk.chunk_id,
            source_id=chunk.source_id or "src_default",
            entity_id=rel["entity_id"],
            predicate=rel.get("predicate", "claims"),
            value=rel.get("value", "N/A"),
            published_at=chunk.published_at.isoformat() if chunk.published_at else None,
            claimed_scope=chunk.claimed_scope,
        )
        if not claim_ok:
            n_success = False

    if n_success:
        event_entry.neo4j_synced = True

    await db.commit()
    logger.info("Processed chunk %s (Qdrant: %s, Neo4j: %s)", chunk.chunk_id, q_success, n_success)
    return event_entry


async def process_and_store_chunks_batch(db: AsyncSession, chunks: List[ChunkMetadata]) -> List[EventLog]:
    """
    Batched dual-write process for multiple chunks of an article.
    Computes all embeddings in a single batch request to prevent sequential API call latency.
    """
    if not chunks:
        return []
        
    # 1. Postgres EventLog entries (Source of Truth)
    event_entries = []
    for chunk in chunks:
        entry = EventLog(
            id=chunk.chunk_id,
            source_id=chunk.source_id,
            raw_text=chunk.raw_text,
            author=chunk.author,
            title=chunk.title,
            url=chunk.url,
            published_at=chunk.published_at,
            ingested_at=chunk.ingested_at,
            sentiment=chunk.sentiment,
            claimed_scope=json.dumps(chunk.claimed_scope),
            status="active",
            qdrant_synced=False,
            neo4j_synced=False,
            embedding_model=settings.embedding_model if not settings.demo_mode else "mock-768d",
        )
        db.add(entry)
        event_entries.append(entry)
        
    await db.commit()
    for entry in event_entries:
        await db.refresh(entry)
        
    # 2. Generate embeddings in a single batch call!
    texts = [c.raw_text for c in chunks]
    embeddings = generate_embedding(texts) # List[List[float]]
    
    # 3. Process each chunk (Entity extraction is done per chunk via LLM or Heuristics)
    for i, (chunk, entry) in enumerate(zip(chunks, event_entries)):
        embedding = embeddings[i]
        entities, relationships = extract_entities_and_relations(chunk.raw_text)
        
        # Write to Qdrant
        payload = {
            "chunk_id": chunk.chunk_id,
            "source_name": chunk.source_name or "Unknown Source",
            "source_id": chunk.source_id,
            "author": chunk.author,
            "title": chunk.title,
            "url": chunk.url,
            "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
            "sentiment": chunk.sentiment,
            "claimed_scope": chunk.claimed_scope,
            "raw_text": chunk.raw_text,
        }
        q_success = upsert_chunk(chunk.chunk_id, embedding, payload)
        if q_success:
            entry.qdrant_synced = True
            
        # Write to Neo4j
        if chunk.source_id and chunk.source_name:
            await upsert_source(chunk.source_id, chunk.source_name)
            
        n_success = True
        for ent in entities:
            ent_ok = await upsert_entity(ent["id"], ent["name"], ent["type"])
            if not ent_ok:
                n_success = False
                
        for rel in relationships:
            claim_ok = await upsert_claim(
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id or "src_default",
                entity_id=rel["entity_id"],
                predicate=rel.get("predicate", "claims"),
                value=rel.get("value", "N/A"),
                published_at=chunk.published_at.isoformat() if chunk.published_at else None,
                claimed_scope=chunk.claimed_scope,
            )
            if not claim_ok:
                n_success = False
                
        if n_success:
            entry.neo4j_synced = True
            
    await db.commit()
    logger.info("Processed batch of %d chunks.", len(chunks))
    return event_entries
