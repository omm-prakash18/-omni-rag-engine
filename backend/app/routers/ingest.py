"""
app/routers/ingest.py — FastAPI endpoints for manual & background ingestion.

POST /ingest/trigger — manually trigger an ingestion run
GET /ingest/status — check ingestion job history and statistics
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event_log import IngestionJob, Source
from app.schemas.api import (
    CustomIngestRequest,
    CustomIngestResponse,
    IngestStatusItem,
    IngestStatusResponse,
    IngestTriggerResponse,
)
from app.services.ingestion import ingest_custom_article, run_ingestion_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


@router.post("/trigger", response_model=IngestTriggerResponse)
async def trigger_ingestion(background_tasks: BackgroundTasks):
    """Manually trigger ingestion run in background."""
    try:
        background_tasks.add_task(run_ingestion_pipeline)
        return IngestTriggerResponse(
            status="started",
            message="Ingestion pipeline triggered in background.",
        )
    except Exception as e:
        logger.error("Failed to trigger ingestion: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom", response_model=CustomIngestResponse)
async def submit_custom_article(req: CustomIngestRequest):
    """Submit a custom news article/snippet for real-time indexing into vector & database stores."""
    try:
        chunks_count = await ingest_custom_article(
            source_name=req.source_name,
            title=req.title,
            content=req.content,
            author=req.author,
            url=req.url,
        )
        return CustomIngestResponse(
            status="success",
            source_name=req.source_name,
            chunks_created=chunks_count,
            message=f"Successfully indexed '{req.title}' ({chunks_count} semantic chunks created).",
        )
    except Exception as e:
        logger.error("Failed to ingest custom article: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=IngestStatusResponse)
async def get_ingestion_status(db: AsyncSession = Depends(get_db)):
    """Get status of recent ingestion jobs per source."""
    try:
        stmt = select(Source)
        res = await db.execute(stmt)
        sources = res.scalars().all()

        items = []
        for s in sources:
            job_stmt = (
                select(IngestionJob)
                .where(IngestionJob.source_id == s.id)
                .order_by(IngestionJob.started_at.desc())
                .limit(1)
            )
            job_res = await db.execute(job_stmt)
            last_job = job_res.scalar_one_or_none()

            items.append(
                IngestStatusItem(
                    source=s.name,
                    last_run=last_job.started_at if last_job else None,
                    articles_fetched=last_job.articles_fetched if last_job else 0,
                    chunks_created=last_job.chunks_created if last_job else 0,
                    status=last_job.status if last_job else "never_run",
                    error=last_job.error if last_job else None,
                )
            )

        return IngestStatusResponse(sources=items)
    except Exception as e:
        logger.error("Error fetching ingestion status: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

