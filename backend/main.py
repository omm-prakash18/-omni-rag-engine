"""
backend/main.py — FastAPI Application Entrypoint for Omni-Perspective Engine Backend.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

# Set pure python protobuf implementation before importing any modules (Python 3.14 compatibility)
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import cleanup_expired_cache, shutdown as db_shutdown, startup as db_startup
from app.routers import ingest, query, ws
from app.services.ingestion import run_ingestion_pipeline

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("omni_engine")
settings = get_settings()

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Omni-Perspective Engine Backend...")
    # 1. Startup DB connections
    await db_startup()

    # 2. Run initial seed ingestion so search works out of the box
    try:
        logger.info("Running initial seed ingestion...")
        await run_ingestion_pipeline()
    except Exception as e:
        logger.warning("Initial seed ingestion error: %s", e)

    # 3. Start periodic background scheduler
    # Always schedule cache cleanup (every 5 minutes)
    scheduler.add_job(
        cleanup_expired_cache,
        "interval",
        minutes=5,
        id="cache_cleanup",
        replace_existing=True,
    )
    if settings.ingestion_interval_seconds > 0:
        scheduler.add_job(
            run_ingestion_pipeline,
            "interval",
            seconds=settings.ingestion_interval_seconds,
            id="ingestion_poller",
            replace_existing=True,
        )
    scheduler.start()
    logger.info(
        "APScheduler started (cache cleanup: 5m, ingestion poll: %ds)",
        settings.ingestion_interval_seconds,
    )

    yield  # App runs here

    logger.info("Shutting down Omni-Perspective Engine Backend...")
    if scheduler.running:
        scheduler.shutdown()
    await db_shutdown()


app = FastAPI(
    title="Omni-Perspective Engine API",
    description="Multi-Source Contradiction Detection API powered by LangGraph, Qdrant, and Neo4j.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=False,  # credentials=True is incompatible with wildcard origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(query.router)
app.include_router(ingest.router)
app.include_router(ws.router)
app.include_router(flags.router)
app.include_router(topics.router)
app.include_router(external_api.router)

# No-cache headers helper
_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

# Mount Frontend static files with no-cache to ensure latest HTML/CSS/JS is served
@app.get("/")
async def serve_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if not os.path.exists(index_path):
        index_path = os.path.join(PROJECT_ROOT, "index.html")
    return FileResponse(index_path, headers=_NO_CACHE_HEADERS)

@app.get("/styles.css")
async def serve_css():
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    if not os.path.exists(css_path):
        css_path = os.path.join(PROJECT_ROOT, "styles.css")
    return FileResponse(css_path, headers=_NO_CACHE_HEADERS, media_type="text/css")

@app.get("/main.js")
async def serve_js():
    js_path = os.path.join(FRONTEND_DIR, "main.js")
    if not os.path.exists(js_path):
        js_path = os.path.join(PROJECT_ROOT, "main.js")
    return FileResponse(js_path, headers=_NO_CACHE_HEADERS, media_type="application/javascript")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "demo_mode": settings.demo_mode,
        "has_newsapi": settings.has_newsapi,
        "database_url": settings.database_url,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )
