"""Feature Engine API router."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.features.service import (
    SUPPORTED_WINDOWS,
    compute_features,
    fetch_window_readings,
)
from app.models.zone import Zone
from app.schemas.features import ZoneFeaturesResponse

router = APIRouter(tags=["Features"])


@router.get(
    "/zones/{zone_id}/features",
    response_model=ZoneFeaturesResponse,
    summary="Calculate crop-health monitoring features for a zone",
    description=(
        "Derive contextual monitoring features (statistics, trends, rates of "
        "change, leaf-wetness duration) from the zone's sensor observations "
        "within the requested time window (`30m`, `1h`, `6h`, `24h`).\n\n"
        "- Features are derived from sensor observations and are contextual "
        "indicators only.\n"
        "- The Feature Engine does **not** perform risk scoring, disease "
        "diagnosis, or camera triggering.\n"
        "- `current` values are the latest observation *inside the selected "
        "window*, not the latest database record.\n"
        "- Returns 404 if the zone does not exist or if no readings fall "
        "inside the requested window."
    ),
)
def get_zone_features(
    zone_id: int,
    window: str = Query(
        default="1h",
        description=f"Time window: one of {', '.join(SUPPORTED_WINDOWS)}.",
    ),
    db: Session = Depends(get_db),
) -> ZoneFeaturesResponse:
    """Compute monitoring features for a zone over the requested window."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )

    if window not in SUPPORTED_WINDOWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported window '{window}'. Supported: "
            f"{', '.join(SUPPORTED_WINDOWS)}.",
        )

    readings = fetch_window_readings(db, zone_id, window)
    if not readings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient sensor data for the requested window",
        )

    return ZoneFeaturesResponse(
        zone_id=zone_id,
        window=window,
        observation_count=len(readings),
        features=compute_features(readings),
    )
