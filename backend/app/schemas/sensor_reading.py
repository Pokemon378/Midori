"""Pydantic schemas for sensor readings.

All metric values are software-generated observations for the SIH MVP
(not physical hardware values).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SensorReadingCreate(BaseModel):
    """Request schema for a sensor observation.

    timestamp is timezone-aware ISO 8601 (e.g. "2026-09-15T10:00:00+05:30").
    """

    timestamp: datetime
    temperature: float = Field(ge=-50, le=70, description="Air temperature in Celsius")
    humidity: float = Field(ge=0, le=100, description="Relative humidity (%)")
    rainfall: float = Field(ge=0, description="Rainfall for the period (mm)")
    leaf_wetness: float = Field(ge=0, le=100, description="Leaf wetness, MVP scale 0-100")
    soil_moisture: float = Field(ge=0, le=100, description="Soil moisture, MVP scale 0-100")
    pest_activity: float = Field(ge=0, le=100, description="Pest activity index, MVP scale 0-100")


class SensorReadingResponse(BaseModel):
    """Response schema for a stored sensor reading."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    timestamp: datetime
    temperature: float
    humidity: float
    rainfall: float
    leaf_wetness: float
    soil_moisture: float
    pest_activity: float
    created_at: datetime
