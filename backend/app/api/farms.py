"""Farm API routers."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.farm import Farm
from app.schemas.farm import FarmCreate, FarmResponse

router = APIRouter(prefix="/farms", tags=["Farms"])


@router.post("", response_model=FarmResponse, status_code=status.HTTP_201_CREATED)
def create_farm(payload: FarmCreate, db: Session = Depends(get_db)) -> Farm:
    """Create a new farm."""
    farm = Farm(**payload.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("", response_model=list[FarmResponse])
def list_farms(db: Session = Depends(get_db)) -> list[Farm]:
    """Return all farms."""
    return list(db.query(Farm).order_by(Farm.id).all())


@router.get("/{farm_id}", response_model=FarmResponse)
def get_farm(farm_id: int, db: Session = Depends(get_db)) -> Farm:
    """Return a single farm, or 404 if it does not exist."""
    farm = db.get(Farm, farm_id)
    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found."
        )
    return farm
