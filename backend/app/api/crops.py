"""Crop API routers."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.crop import Crop
from app.models.zone import Zone
from app.schemas.crop import CropCreate, CropResponse

router = APIRouter(tags=["Crops"])


@router.post(
    "/zones/{zone_id}/crop",
    response_model=CropResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_crop(
    zone_id: int, payload: CropCreate, db: Session = Depends(get_db)
) -> Crop:
    """Assign crop information to an existing zone (one active crop per zone)."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found."
        )
    if zone.crop is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zone already has an assigned crop.",
        )
    crop = Crop(zone_id=zone_id, **payload.model_dump())
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


@router.get("/zones/{zone_id}/crop", response_model=CropResponse)
def get_crop(zone_id: int, db: Session = Depends(get_db)) -> Crop:
    """Return the crop assigned to a zone, or 404 if none/no zone."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found."
        )
    if zone.crop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No crop assigned to this zone.",
        )
    return zone.crop
