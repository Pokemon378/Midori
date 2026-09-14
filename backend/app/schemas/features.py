"""Pydantic schemas for the Feature Engine response."""

from typing import Literal, Optional

from pydantic import BaseModel

Trend = Literal[
    "increasing", "decreasing", "stable", "insufficient_data"
]


class MetricFeatures(BaseModel):
    """Statistics/trend/rate block for one continuous metric."""

    current: float
    average: float
    minimum: float
    maximum: float
    trend: Optional[Trend] = None
    change_rate_per_hour: Optional[float] = None


class LeafWetnessFeatures(MetricFeatures):
    """Leaf wetness features including estimated active duration."""

    active_duration_minutes: int


class RainfallFeatures(BaseModel):
    """Rainfall features; values are interval rainfall summed over the window."""

    total: float
    latest: float
    observation_count: int


class FeatureBlock(BaseModel):
    """All calculated features for one zone/window."""

    temperature: MetricFeatures
    humidity: MetricFeatures
    leaf_wetness: LeafWetnessFeatures
    soil_moisture: MetricFeatures
    pest_activity: MetricFeatures
    rainfall: RainfallFeatures


class ZoneFeaturesResponse(BaseModel):
    """Response for GET /zones/{zone_id}/features.

    Contextual indicators only — the Feature Engine does not perform
    risk scoring or disease diagnosis.
    """

    zone_id: int
    window: str
    observation_count: int
    features: FeatureBlock
