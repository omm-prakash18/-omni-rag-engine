# The Omni-Perspective Engine — Build Spec

> A phased, de-risked spec for a multi-source contradiction-detection system.

---

## 0. Design Philosophy: Phase Before You Scale

Build in two phases:

- **Phase 1 (MVP, ~2-3 weeks):** Batch ingestion, single synthesis pass, static graph render.
  Goal: prove the LLM can reliably distinguish real contradictions from scope/methodology
  mismatches. Target: >85% precision on a hand-labeled eval set before scaling.
- **Phase 2 (Production):** Add Kafka streaming, WebSocket live updates, temporal slider,
  once Phase 1's contradiction-detection precision is measured and acceptable.

---

## 1. System Architecture

```
INGESTION LAYER (Phase 1: polling | Phase 2: Kafka)
        │
        ▼
CHUNKING & METADATA SERVICE
  - Semantic chunking (not fixed-window)
  - Extract: author, timestamp, source, sentiment, claimed scope
        │
        ▼
EXTRACTION SERVICE (LLM, cheap model)
  - Entities + relationships → Neo4j
  - Embeddings → Qdrant
  - Single source-of-truth event log (Postgres)
        │
   ┌────┴────┐
   ▼         ▼
Qdrant     Neo4j
   └────┬────┘
        ▼
QUERY-TIME AGENT ORCHESTRATION (LangGraph)
  Vector Agent ──┐
                 ├──▶ Synthesizer Agent ──▶ Contradiction Classifier
  Graph Agent ───┘
        │
        ▼
FASTAPI + WEBSOCKET GATEWAY
        │
        ▼
REACT FRONTEND (React Flow)
```

---

## 2. Backend Components

### 2.1 Ingestion Service (Python / FastAPI)
- Phase 1: scheduled polling job (APScheduler) hitting licensed APIs (NewsAPI, Reuters, SEC EDGAR).
- Phase 2: swap poller for Kafka producers, one topic per source category.

### 2.2 Chunking Service
- Semantic chunking via LlamaIndex `SemanticSplitterNodeParser`.
- Metadata schema per chunk:

```json
{
  "chunk_id": "uuid",
  "source_id": "reuters | bloomberg | ft | ...",
  "author": "string | null",
  "published_at": "ISO8601",
  "ingested_at": "ISO8601",
  "sentiment": "float [-1,1]",
  "claimed_scope": {
    "date_range": "string | null",
    "geography": "string | null",
    "methodology": "string | null"
  },
  "raw_text": "string",
  "status": "active | retracted | superseded"
}
```

### 2.3 Extraction Service
- LLM pass extracts entities + relationships.
- Write path: Postgres event log first → Qdrant + Neo4j reference that event ID.
- Nightly consistency job reconciles orphans.

### 2.4 Query-Time Agent Orchestration (LangGraph)
Four nodes:
1. **Vector Agent** — semantic search in Qdrant.
2. **Graph Agent** — Cypher query in Neo4j.
3. **Synthesizer Agent** — merges both, groups claims by entity+metric.
4. **Contradiction Classifier** — classifies each conflict as:
   - `direct_contradiction` — same entity, same metric, same scope, different value
   - `stale` — one claim is much older, likely superseded
   - `scope_mismatch` — different date range / geography / methodology
   - `methodology_mismatch` — explicitly different calculation method stated

### 2.5 API / WebSocket Layer (FastAPI)
- REST endpoint for one-shot queries (Phase 1).
- WebSocket endpoint for streaming agent steps + graph updates (Phase 2).

---

## 3. Databases

| Store    | Purpose                    | Notes                                         |
|----------|----------------------------|-----------------------------------------------|
| Qdrant   | Chunk embeddings           | Payload includes chunk metadata for filtering |
| Neo4j    | Entity/relationship graph  | Nodes: Entity, Claim, Source                  |
| Postgres | Event log / source of truth| Single write path both stores derive from     |
| Redis    | Job queue + cache          | Query result caching for repeated questions   |

---

## 4. Frontend (React + React Flow)

**Design direction:** Editorial, newsroom feel. Not a generic AI app dashboard.

- **Contradiction Edge:** dashed red animated line — reads as "unresolved tension."
- **Typography:** condensed grotesk for headlines + tabular-figures font for numbers.
- **Layout:** graph canvas as dominant surface.

### Components
1. **Graph Visualizer (React Flow)**
   - Custom nodes: `EntityNode`, `ClaimNode`, `SourceNode`
   - Custom edges: `ContradictionEdge` (red, animated), `SupportEdge`, `SupersedesEdge`
   - Clustering: collapse nodes past ~30 visible nodes
2. **Source-Tracing Split View** — side-by-side clause references with source + classifier reason
3. **Temporal Slider** — scrubs `published_at` range, re-filters the graph
4. **Live State (Phase 2)** — WebSocket streams agent reasoning + new graph nodes in real time

---

## 5. Build Order

1. Postgres schema + event log.
2. Ingestion service (polling).
3. Chunking + extraction service (dual-write to Qdrant + Neo4j).
4. LangGraph 4-node pipeline as standalone script + eval set.
5. FastAPI REST endpoint wrapping the LangGraph pipeline.
6. React Flow frontend against REST endpoint.
7. After validation: Kafka, WebSocket streaming, temporal slider live updates.

---

## 6. Open Risks

- Contradiction classifier precision/recall — needs an eval harness.
- Licensing for source content (no raw redistribution of full articles).
- Graph readability at scale — clustering strategy must be decided before launch.
- Cost model: query-time LLM calls (4 per query) vs. ingestion-time calls (1 per chunk).
