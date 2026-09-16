"""Risk Engine service: Feature Engine output -> explainable risk assessment.

Consumes features produced by the existing Feature Engine service (no
duplicate sensor-reading calculations) and stores each assessment so the
risk trend can be computed from real history.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.risk_assessment import RiskAssessment
from app.risk import calculations as rc

logger = logging.getLogger("midori.risk")


def _previous_level_rank(db: Session, zone_id: int, window: str) -> Optional[int]:
    """Rank (0..3) of the most recent prior assessment, if any."""
    previous = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.zone_id == zone_id, RiskAssessment.window == window)
        .order_by(RiskAssessment.created_at.desc(), RiskAssessment.id.desc())
        .first()
    )
    if previous is None or previous.risk_score is None:
        return None
    return rc.LEVELS.index(previous.risk_level) if previous.risk_level in rc.LEVELS else None


def calculate_risk_trend(previous_rank: Optional[int], current_level: str) -> str:
    """Compare current level with the last stored assessment.

    insufficient_data when there is no usable prior assessment.
    """
    if previous_rank is None or current_level == "INSUFFICIENT_DATA":
        return "insufficient_data"
    current_rank = rc.LEVELS.index(current_level) if current_level in rc.LEVELS else None
    if current_rank is None:
        return "insufficient_data"
    if current_rank > previous_rank:
        return "increasing"
    if current_rank < previous_rank:
        return "decreasing"
    return "stable"


def build_assessment(
    db: Session, zone_id: int, window: str, features: dict[str, Any]
) -> dict[str, Any]:
    """Compute, log, store and return a risk assessment for a zone/window.

    When `features` is empty (Feature Engine found no data), a valid
    INSUFFICIENT_DATA response is produced — no score is invented.
    """
    logger.info("risk calculation requested zone_id=%s window=%s", zone_id, window)

    score = rc.calculate_risk_score(features)
    level = rc.calculate_risk_level(score)
    factors = rc.calculate_risk_factors(features) if features else []
    previous_rank = _previous_level_rank(db, zone_id, window)
    trend = calculate_risk_trend(previous_rank, level)
    camera = rc.should_trigger_camera(level, features, len(factors)) if features else False

    if features:
        db.add(
            RiskAssessment(
                zone_id=zone_id,
                window=window,
                risk_score=score,
                risk_level=level,
                camera_trigger=camera,
            )
        )
        db.commit()

    logger.info(
        "risk result zone_id=%s window=%s level=%s camera_trigger=%s",
        zone_id,
        window,
        level,
        camera,
    )

    return {
        "zone_id": zone_id,
        "window": window,
        "risk_score": score,
        "risk_level": level,
        "risk_trend": trend,
        "camera_trigger": camera,
        "risk_factors": factors,
        "generated_at": datetime.now(timezone.utc),
    }
