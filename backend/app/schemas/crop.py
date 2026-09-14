"""Pydantic schemas for crops."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CropCreate(BaseModel):
    """Request schema for creating/assigning a crop to a zone."""

    crop_name: str = Field(min_length=1, max_length=120)
    crop_stage: str | None = Field(default=None, max_length=80)
    sowing_date: date | None = None


class CropResponse(BaseModel):
    """Response schema for a crop."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    crop_name: str
    crop_stage: str | None
    sowing_date: date | None
    created_at: datetime
