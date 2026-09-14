"""Pydantic schemas for farms."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FarmCreate(BaseModel):
    """Request schema for creating a farm."""

    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=200)
    area_acres: float | None = Field(default=None, gt=0, le=100000)


class FarmResponse(BaseModel):
    """Response schema for a farm."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str
    area_acres: float | None
    created_at: datetime
