"""Pydantic schemas for zones."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ZoneCreate(BaseModel):
    """Request schema for creating a zone."""

    name: str = Field(min_length=1, max_length=120)


class ZoneResponse(BaseModel):
    """Response schema for a zone."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_id: int
    name: str
    created_at: datetime
