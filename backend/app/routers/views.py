"""
app/routers/views.py — Custom Workspace Views API (Part 1.3).

Allows users to save reusable graph layout & filter combinations (e.g. "My Macro Finance Dashboard").
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.features import CustomView
from app.schemas.api import UserPreferences

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/views", tags=["views"])


class CustomViewCreate(BaseModel):
    view_name: str = Field(min_length=2, max_length=100)
    query: str = Field(min_length=3, max_length=500)
    layout_config: Optional[Dict[str, Any]] = None  # Node positions, zoom level
    preferences: Optional[UserPreferences] = None


class CustomViewResponse(BaseModel):
    id: str
    view_name: str
    query: str
    layout_config: Optional[Dict[str, Any]]
    preferences: Optional[UserPreferences]
    created_at: str


@router.post("", response_model=CustomViewResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_view(payload: CustomViewCreate, db: AsyncSession = Depends(get_db)):
    """Save a workspace view configuration for future reuse."""
    view = CustomView(
        view_name=payload.view_name,
        query=payload.query,
        layout_config=json.dumps(payload.layout_config) if payload.layout_config else None,
        preferences_config=json.dumps(payload.preferences.model_dump(mode="json")) if payload.preferences else None,
    )
    db.add(view)
    await db.commit()
    await db.refresh(view)
    logger.info("Saved CustomView '%s' (id=%s)", view.view_name, view.id)

    return CustomViewResponse(
        id=view.id,
        view_name=view.view_name,
        query=view.query,
        layout_config=json.loads(view.layout_config) if view.layout_config else None,
        preferences=UserPreferences(**json.loads(view.preferences_config)) if view.preferences_config else None,
        created_at=view.created_at.isoformat(),
    )


@router.get("", response_model=List[CustomViewResponse])
async def list_custom_views(db: AsyncSession = Depends(get_db)):
    """List all saved workspace views."""
    stmt = select(CustomView).order_by(CustomView.created_at.desc())
    res = await db.execute(stmt)
    views = res.scalars().all()

    return [
        CustomViewResponse(
            id=v.id,
            view_name=v.view_name,
            query=v.query,
            layout_config=json.loads(v.layout_config) if v.layout_config else None,
            preferences=UserPreferences(**json.loads(v.preferences_config)) if v.preferences_config else None,
            created_at=v.created_at.isoformat(),
        )
        for v in views
    ]
