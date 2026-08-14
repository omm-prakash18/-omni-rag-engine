"""
app/routers/ws.py — WebSocket endpoint for streaming real-time agent reasoning steps.

WS /ws/query
Receives JSON payload: {"query": "US inflation rate", "top_k": 10}
Streams structured event frames:
  {"type": "step",         "stage": "vector|crag|graph|synthesizer|classifier", "data": "message", "progressPct": 20}
  {"type": "contradiction","data": {...contradiction dict...}}
  {"type": "graph_update", "data": {...graph_data dict...}}
  {"type": "done",         "data": {...full QueryResponse dict...}}
  {"type": "error",        "data": "error message string"}
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.pipeline import run_omni_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Maps step index → (stage_key, progressPct)
_STAGE_MAP = {
    0: ("vector", 10),
    1: ("vector", 20),
    2: ("crag", 35),
    3: ("crag", 45),
    4: ("graph", 60),
    5: ("graph", 70),
    6: ("synthesizer", 80),
    7: ("synthesizer", 85),
    8: ("classifier", 92),
    9: ("classifier", 97),
}


@router.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected from %s", websocket.client)

    try:
        while True:
            raw_msg = await websocket.receive_text()

            try:
                data = json.loads(raw_msg)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": "Invalid JSON payload"})
                continue

            query_str = data.get("query", "").strip()
            top_k = int(data.get("top_k", 10))

            if not query_str:
                await websocket.send_json({"type": "error", "data": "Query string is required"})
                continue

            # Send initial progress frame so the UI shows activity immediately
            await websocket.send_json({
                "type": "step",
                "stage": "vector",
                "data": "1. Vector Agent: Querying Qdrant semantic store...",
                "progressPct": 5,
            })

            try:
                # Execute the full agent pipeline
                response = await run_omni_pipeline(query_str, top_k=top_k)
            except Exception as pipeline_err:
                logger.error("Pipeline error for query '%s': %s", query_str, pipeline_err, exc_info=True)
                await websocket.send_json({"type": "error", "data": str(pipeline_err)})
                continue

            # Stream step messages with stage + progress annotations
            for idx, step in enumerate(response.steps):
                stage, pct = _STAGE_MAP.get(idx, ("classifier", 95))
                await websocket.send_json({
                    "type": "step",
                    "stage": stage,
                    "data": step,
                    "progressPct": pct,
                })

            # Stream individual contradictions so the UI can render them incrementally
            for contradiction in response.contradictions:
                await websocket.send_json({
                    "type": "contradiction",
                    "data": contradiction.model_dump(mode="json"),
                })

            # Stream graph topology update
            await websocket.send_json({
                "type": "graph_update",
                "data": response.graph.model_dump(mode="json"),
            })

            # Final done frame with complete response payload
            await websocket.send_json({
                "type": "done",
                "data": response.model_dump(mode="json"),
                "progressPct": 100,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", websocket.client)
    except Exception as e:
        logger.error("Unexpected WebSocket error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except Exception:
            pass  # Client already gone — nothing we can do
