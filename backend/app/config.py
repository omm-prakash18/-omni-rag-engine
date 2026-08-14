"""
app/config.py — Central configuration loaded from .env
All services import settings from here.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    llm_model: str = Field(default="gemini-1.5-flash", alias="LLM_MODEL")
    embedding_model: str = Field(
        default="models/text-embedding-004", alias="EMBEDDING_MODEL"
    )

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def parse_gemini_api_key(cls, v):
        if not v or v in ("your_gemini_api_key_here", "your_api_key_here"):
            return (
                os.environ.get("GEMINI_API_KEY")
                or os.environ.get("GOOGLE_API_KEY")
                or os.environ.get("API_KEY", "")
            )
        return v

    # ── NewsAPI ───────────────────────────────────────────────────────────────
    newsapi_key: str = Field(default="", alias="NEWSAPI_KEY")
    ingestion_queries: List[str] = Field(
        default=["US inflation rate", "Federal Reserve", "global GDP"],
        alias="INGESTION_QUERIES",
    )
    ingestion_interval_seconds: int = Field(
        default=3600, alias="INGESTION_INTERVAL_SECONDS"
    )

    # ── SQLite / Postgres ─────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./omni_perspective.db",
        alias="DATABASE_URL",
    )

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_mode: str = Field(default="local", alias="QDRANT_MODE")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="omni_chunks", alias="QDRANT_COLLECTION")
    qdrant_local_path: str = Field(default="./qdrant_storage", alias="QDRANT_LOCAL_PATH")

    # ── Neo4j ─────────────────────────────────────────────────────────────────
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: List[str] = Field(
        default=["http://localhost:8000", "http://127.0.0.1:5500"],
        alias="CORS_ORIGINS",
    )

    @field_validator("ingestion_queries", mode="before")
    @classmethod
    def parse_queries(cls, v):
        if isinstance(v, str):
            return [q.strip() for q in v.split(",") if q.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def demo_mode(self) -> bool:
        """True when no real Gemini API key is configured — uses stub data."""
        key = self.gemini_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        return not key or key in ("your_gemini_api_key_here", "")

    @property
    def has_newsapi(self) -> bool:
        return bool(self.newsapi_key) and self.newsapi_key != "your_newsapi_key_here"


@lru_cache
def get_settings() -> Settings:
    return Settings()
