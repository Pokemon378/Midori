"""Sensor reading API routers."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.sensor_reading import SensorReading
from app.models.zone import Zone
from app.schemas.sensor_reading import SensorReadingCreate, SensorReadingResponse

router = APIRouter(tags=["Sensor Readings"])


@router.post(
    "/zones/{zone_id}/sensor-readings",
    response_model=SensorReadingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a sensor observation for a zone",
    description=(
        "Receive and store one environmental/pest observation for a specific "
        "zone. Values are software-generated observations for the SIH MVP "
        "(e.g. from a Digital Farm Simulator), not physical hardware values."
    ),
)
def create_sensor_reading(
    zone_id: int, payload: SensorReadingCreate, db: Session = Depends(get_db)
) -> SensorReading:
    """Validate and store one sensor reading for an existing zone."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )
    reading = SensorReading(zone_id=zone_id, **payload.model_dump())
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get(
    "/zones/{zone_id}/sensor-readings",
    response_model=list[SensorReadingResponse],
    summary="List sensor readings for a zone (newest first)",
    description=(
        "Return sensor readings for a zone, ordered by timestamp (newest "
        "first). Supports an optional `limit` between 1 and 500 (default 50)."
    ),
)
def list_sensor_readings(
    zone_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[SensorReading]:
    """Return the zone's sensor readings, newest first."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )
    return list(
        db.query(SensorReading)
        .filter(SensorReading.zone_id == zone_id)
        .order_by(SensorReading.timestamp.desc(), SensorReading.id.desc())
        .limit(limit)
        .all()
    )


@router.get(
    "/zones/{zone_id}/sensor-readings/latest",
    response_model=SensorReadingResponse,
    summary="Get the most recent sensor reading for a zone",
)
def get_latest_sensor_reading(
    zone_id: int, db: Session = Depends(get_db)
) -> SensorReading:
    """Return the most recent reading, or 404 if the zone has none."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )
    reading = (
        db.query(SensorReading)
        .filter(SensorReading.zone_id == zone_id)
        .order_by(SensorReading.timestamp.desc(), SensorReading.id.desc())
        .first()
    )
    if reading is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensor readings found for this zone",
        )
    return reading
