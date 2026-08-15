"""
app/routers/flags.py — User-Flaggable Corrections Queue API (A3).

Allows users to submit correction flags on contradiction/scope edges.
Stores flags in a human review queue for audit before any score or model feedback update.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.features import UserFlag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flags", tags=["flags"])


class UserFlagCreate(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    edge_id: Optional[str] = Field(default=None, max_length=100)
    entity: str = Field(min_length=2, max_length=200)
    source_a: str = Field(min_length=2, max_length=100)
    source_b: str = Field(min_length=2, max_length=100)
    user_note: str = Field(min_length=5, max_length=2000)


class UserFlagResponse(BaseModel):
    id: str
    query: str
    edge_id: Optional[str]
    entity: str
    source_a: str
    source_b: str
    user_note: str
    status: str
    created_at: str


@router.post("", response_model=UserFlagResponse, status_code=status.HTTP_201_CREATED)
async def submit_user_flag(payload: UserFlagCreate, db: AsyncSession = Depends(get_db)):
    """Submit a correction flag on a contradiction or scope edge."""
    flag = UserFlag(
        query=payload.query,
        edge_id=payload.edge_id,
        entity=payload.entity,
        source_a=payload.source_a,
        source_b=payload.source_b,
        user_note=payload.user_note,
        status="pending",
    )
    db.add(flag)
    await db.commit()
    await db.refresh(flag)
    logger.info("UserFlag submitted for entity '%s' (flag_id=%s)", flag.entity, flag.id)

    return UserFlagResponse(
        id=flag.id,
        query=flag.query,
        edge_id=flag.edge_id,
        entity=flag.entity,
        source_a=flag.source_a,
        source_b=flag.source_b,
        user_note=flag.user_note,
        status=flag.status,
        created_at=flag.created_at.isoformat(),
    )


@router.get("", response_model=List[UserFlagResponse])
async def list_user_flags(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve items from the human review queue for evaluation."""
    stmt = select(UserFlag).order_by(UserFlag.created_at.desc())
    if status_filter:
        stmt = stmt.where(UserFlag.status == status_filter)

    res = await db.execute(stmt)
    flags = res.scalars().all()

    return [
        UserFlagResponse(
            id=f.id,
            query=f.query,
            edge_id=f.edge_id,
            entity=f.entity,
            source_a=f.source_a,
            source_b=f.source_b,
            user_note=f.user_note,
            status=f.status,
            created_at=f.created_at.isoformat(),
        )
        for f in flags
    ]
