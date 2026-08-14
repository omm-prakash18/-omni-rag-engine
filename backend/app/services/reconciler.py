"""
app/services/reconciler.py — Nightly/on-demand consistency job.

Scans Postgres EventLog table for rows where `qdrant_synced=False` or `neo4j_synced=False`
and attempts to resync them to ensure data consistency across vector and graph stores.
"""
from __future__ import annotations

import json
import logging
from typing import Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.event_log import EventLog, Source
from app.services.extraction import generate_embedding
from app.services.neo4j_store import upsert_claim, upsert_entity, upsert_source
from app.services.qdrant_store import upsert_chunk

logger = logging.getLogger(__name__)


async def reconcile_unlinked_chunks() -> Dict[str, int]:
    """Scan and re-sync orphaned or failed chunks."""
    stats = {"scanned": 0, "qdrant_resynced": 0, "neo4j_resynced": 0}

    async with AsyncSessionLocal() as db:
        stmt = select(EventLog).where(
            (EventLog.qdrant_synced == False) | (EventLog.neo4j_synced == False)  # noqa: E712
        )
        result = await db.execute(stmt)
        unlinked_chunks = result.scalars().all()

        stats["scanned"] = len(unlinked_chunks)
        logger.info("Reconciler: found %d unsynced chunks", len(unlinked_chunks))

        for chunk in unlinked_chunks:
            # 1. Resync Qdrant
            if not chunk.qdrant_synced:
                embedding = generate_embedding(chunk.raw_text)
                claimed_scope = json.loads(chunk.claimed_scope) if chunk.claimed_scope else {}
                
                src_name = "Unknown"
                if chunk.source_id:
                    src_res = await db.execute(select(Source.name).where(Source.id == chunk.source_id))
                    src_name = src_res.scalar_one_or_none() or "Unknown"

                payload = {
                    "chunk_id": chunk.id,
                    "source_name": src_name,
                    "source_id": chunk.source_id,
                    "author": chunk.author,
                    "title": chunk.title,
                    "url": chunk.url,
                    "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
                    "sentiment": chunk.sentiment,
                    "claimed_scope": claimed_scope,
                    "raw_text": chunk.raw_text,
                }
                if upsert_chunk(chunk.id, embedding, payload):
                    chunk.qdrant_synced = True
                    stats["qdrant_resynced"] += 1

            # 2. Resync Neo4j
            if not chunk.neo4j_synced and chunk.source_id:
                src_res = await db.execute(select(Source.name).where(Source.id == chunk.source_id))
                src_name = src_res.scalar_one_or_none() or "Unknown"
                
                await upsert_source(chunk.source_id, src_name)
                # Resync claim node
                claimed_scope = json.loads(chunk.claimed_scope) if chunk.claimed_scope else {}
                ok = await upsert_claim(
                    chunk_id=chunk.id,
                    source_id=chunk.source_id,
                    entity_id="economic_indicator",
                    predicate="claims",
                    value="reconciled_value",
                    published_at=chunk.published_at.isoformat() if chunk.published_at else None,
                    claimed_scope=claimed_scope,
                )
                if ok:
                    chunk.neo4j_synced = True
                    stats["neo4j_resynced"] += 1

        await db.commit()
    
    logger.info("Reconciliation complete: %s", stats)
    return stats
