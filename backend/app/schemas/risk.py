"""Pydantic schemas for the Risk Engine response."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL", "INSUFFICIENT_DATA"]
RiskTrend = Literal["increasing", "decreasing", "stable", "insufficient_data"]


class RiskFactor(BaseModel):
    """One deterministic, explainable risk factor."""

    code: str
    observation: str
    effect: Literal["increases_risk"]
    reason: str


class RiskResponse(BaseModel):
    """Explainable environmental crop-health risk assessment.

    The risk score is NOT a disease probability and NOT a diagnosis —
    it is a contextual 0-100 indicator for the MVP.
    """

    zone_id: int
    window: str
    risk_score: Optional[float] = None
    risk_level: RiskLevel
    risk_trend: RiskTrend
    camera_trigger: bool
    risk_factors: list[RiskFactor]
    generated_at: datetime
