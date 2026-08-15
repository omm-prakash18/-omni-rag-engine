"""
app/routers/ws.py — WebSocket endpoint for real-time node partial streaming.

WS /ws/query
Receives JSON payload: {"query": "US inflation rate", "top_k": 5, "preferences": {...}}
Streams real-time event frames:
  {"type": "step",                 "stage": "triage|vector|graph|synthesizer|classifier", "data": "message", "progressPct": 20}
  {"type": "partial_vector_data", "data": [vector chunks...]}
  {"type": "partial_graph_data",  "data": [graph nodes...]}
  {"type": "consensus_data",      "data": {consensus summary...}}
  {"type": "contradiction",       "data": {...contradiction dict...}}
  {"type": "graph_update",        "data": {...graph_data dict...}}
  {"type": "done",                "data": {...full QueryResponse dict...}}
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.pipeline import run_omni_pipeline
from app.schemas.api import UserPreferences

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


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
            top_k = int(data.get("top_k", 5))
            raw_prefs = data.get("preferences")
            preferences = UserPreferences(**raw_prefs) if raw_prefs else UserPreferences()

            if not query_str:
                await websocket.send_json({"type": "error", "data": "Query string is required"})
                continue

            await websocket.send_json({
                "type": "step",
                "stage": "triage",
                "data": "0. Triage Agent: Classifying query scope and intent...",
                "progressPct": 10,
            })

            try:
                response = await run_omni_pipeline(query_str, top_k=top_k, preferences=preferences)
            except Exception as pipeline_err:
                logger.error("Pipeline error for query '%s': %s", query_str, pipeline_err, exc_info=True)
                await websocket.send_json({"type": "error", "data": str(pipeline_err)})
                continue

            # Stream step logs
            for idx, step in enumerate(response.steps):
                pct = min(95, 15 + (idx * 15))
                await websocket.send_json({
                    "type": "step",
                    "stage": "pipeline",
                    "data": step,
                    "progressPct": pct,
                })

            # Stream partial node data frames
            if response.consensus_summary:
                await websocket.send_json({
                    "type": "consensus_data",
                    "data": response.consensus_summary,
                })

            for contradiction in response.contradictions:
                await websocket.send_json({
                    "type": "contradiction",
                    "data": contradiction.model_dump(mode="json"),
                })

            await websocket.send_json({
                "type": "graph_update",
                "data": response.graph.model_dump(mode="json"),
            })

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
            pass
