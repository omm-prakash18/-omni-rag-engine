"""
app/services/ingestion.py — Scheduled and Manual Ingestion Service.

Pulls news articles (via NewsAPI or mock seed dataset when in demo mode),
chunks them using `chunk_article`, and dual-writes them to the databases.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.event_log import IngestionJob, Source
from app.services.chunking import chunk_article
from app.services.extraction import process_and_store_chunk, process_and_store_chunks_batch

logger = logging.getLogger(__name__)
settings = get_settings()

# Demo seed dataset for testing contradiction detection immediately without API keys
SAMPLE_ARTICLES = [
    {
        "source_name": "Reuters",
        "author": "Jonathan Cable",
        "title": "US CPI inflation unexpectedly falls to 3.2% in May",
        "url": "https://reuters.com/markets/us-inflation-may-2024",
        "published_at": "2024-05-15T12:00:00Z",
        "content": (
            "WASHINGTON, May 15 — US consumer prices were unchanged in May as cheaper gasoline "
            "offset higher rental housing costs. According to the Bureau of Labor Statistics, "
            "the headline annual CPI inflation rate dropped to 3.2% year-over-year, coming in lower "
            "than market expectations of 3.4%. Core CPI, excluding food and energy, rose 0.2% on a "
            "monthly basis. Analysts attribute the cooling rate to declining energy prices and "
            "moderating supply chain pressures across North America."
        ),
    },
    {
        "source_name": "Bloomberg",
        "author": "Anna Wong",
        "title": "Bloomberg Economics CPI model signals inflation sticky at 3.8%",
        "url": "https://bloomberg.com/news/articles/us-cpi-nowcast-sticky",
        "published_at": "2024-05-15T14:30:00Z",
        "content": (
            "NEW YORK, May 15 — While government statistics point to a cooling trend, Bloomberg "
            "Economics' proprietary CPI model estimates true underlying annual inflation at 3.8% "
            "for May 2024. The divergence stems from Bloomberg's real-time shelter cost indexing, "
            "which incorporates spot market rent renewals rather than lagged BLS survey data. "
            "Economists warn that persistent service sector inflation could keep Federal Reserve "
            "interest rates higher for longer than Wall Street consensus currently anticipates."
        ),
    },
    {
        "source_name": "Financial Times",
        "author": "Colby Smith",
        "title": "Federal Reserve holds interest rates steady at 5.25%-5.50%",
        "url": "https://ft.com/content/fed-rate-decision-may-2024",
        "published_at": "2024-05-16T18:00:00Z",
        "content": (
            "WASHINGTON, May 16 — The Federal Reserve maintained its benchmark interest rate in a "
            "range of 5.25% to 5.50% following its two-day policy meeting. Chair Jerome Powell stated "
            "that while inflation has eased over the past year, progress toward the Fed's 2.0% target "
            "remains uncertain. The Federal Open Market Committee noted that GDP growth slowed to an "
            "annualized 1.6% in the first quarter of 2024, down from 3.4% in Q4 2023."
        ),
    },
    {
        "source_name": "Associated Press",
        "author": "Christopher Rugaber",
        "title": "AP Analysis: Annualized US Inflation calculated at 3.9% under alternative basket",
        "url": "https://apnews.com/article/us-economy-inflation-analysis",
        "published_at": "2024-05-17T09:15:00Z",
        "content": (
            "WASHINGTON, May 17 — An AP econometric analysis of consumer expenditures suggests "
            "that annual US inflation measured 3.9% in May 2024 when using an unweighted chained CPI "
            "basket. The calculation includes regional transport spikes that traditional national "
            "averages mute. The finding contrasts with official BLS numbers and highlights how "
            "regional cost-of-living variances distort national consensus policy metrics."
        ),
    },
    {
        "source_name": "Wall Street Journal",
        "author": "Nick Timiraos",
        "title": "Fed cuts benchmark interest rate target to 5.00%-5.25% in surprise policy move",
        "url": "https://wsj.com/economy/central-banking/fed-interest-rate-target-cut-500",
        "published_at": "2024-05-16T18:30:00Z",
        "content": (
            "WASHINGTON, May 16 — In a surprise policy update, Wall Street Journal reports that "
            "the Federal Reserve set the target Federal Funds benchmark interest rate at 5.00% to 5.25%. "
            "Diverging from consensus expectations of 5.25% to 5.50%, the FOMC monetary policy committee "
            "adjusted policy stance following private banking liquidity consultations."
        ),
    },
    {
        "source_name": "CNBC",
        "author": "Jeff Cox",
        "title": "Core PCE vs Headline CPI: BEA reports Core PCE inflation at 2.8% in May",
        "url": "https://cnbc.com/2024/05/17/core-pce-inflation-rate-may.html",
        "published_at": "2024-05-17T11:00:00Z",
        "content": (
            "ENGLEWOOD CLIFFS, N.J., May 17 — The Bureau of Economic Analysis reports the Core PCE "
            "Price Index registered 2.8% year-over-year for May 2024. Economists emphasize that "
            "Core PCE excludes volatile food and energy components, providing a different perspective "
            "from the BLS Headline CPI inflation rate of 3.2% which includes all expenditure categories."
        ),
    },
]


async def _get_or_create_source(db: AsyncSession, name: str) -> Source:
    stmt = select(Source).where(Source.name == name)
    result = await db.execute(stmt)
    src = result.scalar_one_or_none()
    if not src:
        src = Source(name=name, api_type="newsapi" if settings.has_newsapi else "mock")
        db.add(src)
        await db.commit()
        await db.refresh(src)
    return src


async def run_ingestion_pipeline(queries: Optional[List[str]] = None) -> IngestionJob:
    """Run ingestion cycle: fetches articles, chunks them, dual-writes to stores."""
    async with AsyncSessionLocal() as db:
        job = IngestionJob(started_at=datetime.now(timezone.utc), status="running")
        db.add(job)
        await db.commit()
        await db.refresh(job)

        articles_to_process = []

        if settings.has_newsapi:
            # Real NewsAPI fetch
            logger.info("Ingesting from NewsAPI for queries: %s", settings.ingestion_queries)
            async with httpx.AsyncClient(timeout=10.0) as client:
                for q in (queries or settings.ingestion_queries):
                    try:
                        resp = await client.get(
                            "https://newsapi.org/v2/everything",
                            params={
                                "q": q,
                                "apiKey": settings.newsapi_key,
                                "language": "en",
                                "pageSize": 10,
                                "sortBy": "publishedAt",
                            },
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            for art in data.get("articles", []):
                                if art.get("content") or art.get("description"):
                                    articles_to_process.append({
                                        "source_name": art.get("source", {}).get("name", "NewsAPI"),
                                        "author": art.get("author"),
                                        "title": art.get("title"),
                                        "url": art.get("url"),
                                        "published_at": art.get("publishedAt"),
                                        "content": art.get("content") or art.get("description"),
                                    })
                    except Exception as e:
                        logger.error("NewsAPI fetch error for query '%s': %s", q, e)
        else:
            # Demo fallback mode with sample articles
            logger.info("Ingesting demo seed articles (No NewsAPI key configured)")
            articles_to_process = SAMPLE_ARTICLES

        job.articles_fetched = len(articles_to_process)
        total_chunks = 0

        for art in articles_to_process:
            src = await _get_or_create_source(db, art["source_name"])
            
            pub_dt = None
            if art.get("published_at"):
                try:
                    pub_dt = datetime.fromisoformat(art["published_at"].replace("Z", "+00:00"))
                except Exception:
                    pub_dt = datetime.now(timezone.utc)

            chunks = chunk_article(
                raw_text=art["content"],
                source_name=src.name,
                source_id=src.id,
                author=art.get("author"),
                title=art.get("title"),
                url=art.get("url"),
                published_at=pub_dt,
            )

            if chunks:
                await process_and_store_chunks_batch(db, chunks)
                total_chunks += len(chunks)

        job.chunks_created = total_chunks
        job.completed_at = datetime.now(timezone.utc)
        job.status = "done"
        await db.commit()
        await db.refresh(job)
        logger.info("Ingestion job #%d complete: %d articles, %d chunks", job.id, job.articles_fetched, job.chunks_created)
        return job
