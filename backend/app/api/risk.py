"""Risk Engine API router."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.features.service import (
    SUPPORTED_WINDOWS,
    compute_features,
    fetch_window_readings,
)
from app.models.zone import Zone
from app.risk.service import build_assessment
from app.schemas.risk import RiskResponse

router = APIRouter(tags=["Risk"])
logger = logging.getLogger("midori.risk")


@router.get(
    "/zones/{zone_id}/risk",
    response_model=RiskResponse,
    summary="Assess environmental crop-health risk for a zone",
    description=(
        "Consume the Feature Engine output for the requested window "
        "(`30m`, `1h`, `6h`, `24h`) and produce an explainable "
        "crop-health risk assessment.\n\n"
        "- The risk score is a contextual environmental indicator, NOT a "
        "disease probability or diagnosis.\n"
        "- `camera_trigger` is a software decision for a future "
        "Camera/Image Intake module; no image is captured.\n"
        "- If no sensor data exists in the window, a valid response with "
        "`risk_level: INSUFFICIENT_DATA` and a null score is returned."
    ),
)
def get_zone_risk(
    zone_id: int,
    window: str = Query(
        default="1h",
        description=f"Time window: one of {', '.join(SUPPORTED_WINDOWS)}.",
    ),
    db: Session = Depends(get_db),
) -> RiskResponse:
    """Return the risk assessment for a zone over the requested window."""
    if window not in SUPPORTED_WINDOWS:
        logger.warning("invalid risk window requested: %s", window)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid window '{window}'. Supported: "
            f"{', '.join(SUPPORTED_WINDOWS)}.",
        )

    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )

    readings = fetch_window_readings(db, zone_id, window)
    features = compute_features(readings) if readings else {}
    return RiskResponse(**build_assessment(db, zone_id, window, features))
