"""Zone API routers."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.farm import Farm
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneResponse

router = APIRouter(tags=["Zones"])


@router.post(
    "/farms/{farm_id}/zones",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_zone(
    farm_id: int, payload: ZoneCreate, db: Session = Depends(get_db)
) -> Zone:
    """Create a zone inside an existing farm."""
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found."
        )
    zone = Zone(farm_id=farm_id, name=payload.name)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/farms/{farm_id}/zones", response_model=list[ZoneResponse])
def list_zones(farm_id: int, db: Session = Depends(get_db)) -> list[Zone]:
    """Return all zones belonging to a farm."""
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found."
        )
    return list(db.query(Zone).filter(Zone.farm_id == farm_id).order_by(Zone.id).all())


@router.get("/zones/{zone_id}", response_model=ZoneResponse)
def get_zone(zone_id: int, db: Session = Depends(get_db)) -> Zone:
    """Return a single zone, or 404 if it does not exist."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found."
        )
    return zone
