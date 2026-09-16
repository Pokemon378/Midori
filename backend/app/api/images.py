"""Image intake API router."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.images import service
from app.images.quality import BLUR_ACCEPT_THRESHOLD, BRIGHTNESS_BRIGHT_THRESHOLD, BRIGHTNESS_DARK_THRESHOLD
from app.models.image_metadata import ImageMetadata
from app.models.zone import Zone
from app.schemas.images import ImageResponse

router = APIRouter(tags=["Images"])
logger = logging.getLogger("midori.images")


def _to_response(record: ImageMetadata) -> ImageResponse:
    """Attach computed quality info to the metadata response."""
    data = ImageResponse.model_validate(record).model_dump()
    if record.blur_score is not None:
        data["quality"] = {
            "blur_score": record.blur_score,
            "blur_status": (
                "acceptable" if (record.blur_score or 0) >= BLUR_ACCEPT_THRESHOLD else "blurry"
            ),
            "brightness_score": record.brightness_score or 0.0,
            "brightness_status": _brightness_status(record.brightness_score),
        }
    return ImageResponse(**data)


def _brightness_status(score: Optional[float]) -> str:
    if score is None:
        return "acceptable"
    if score < BRIGHTNESS_DARK_THRESHOLD:
        return "too_dark"
    if score > BRIGHTNESS_BRIGHT_THRESHOLD:
        return "too_bright"
    return "acceptable"


@router.post(
    "/zones/{zone_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a crop image for a zone",
    description=(
        "Receive a crop image (JPEG/JPG, PNG or WEBP), validate it, store it "
        "on the local filesystem and run quality checks (resolution, blur, "
        "brightness).\n\n"
        "- Accepted images become `READY_FOR_AI` for the future AI Vision step.\n"
        "- Technically valid but poor-quality images become `LOW_QUALITY`.\n"
        "- Invalid, corrupted or oversized files are rejected with HTTP 400.\n\n"
        "This endpoint does NOT diagnose disease or pests — that is Step 7 (AI Vision)."
    ),
)
async def upload_zone_image(
    zone_id: int,
    file: UploadFile = File(..., description="Image file (JPEG, PNG or WEBP)."),
    source: str = Form(
        default="uploaded",
        description="Image origin: uploaded, simulated_camera or replayed.",
    ),
    db: Session = Depends(get_db),
) -> ImageResponse:
    """Upload, validate, store and quality-check an image for a zone."""
    if source not in service.VALID_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source '{source}'. "
            f"Valid: {', '.join(sorted(service.VALID_SOURCES))}.",
        )

    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )

    data = await file.read()
    result = service.process_upload(
        db,
        zone,
        data,
        file.content_type,
        file.filename or "upload",
        source,
    )
    if result["rejected"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=result["reason"]
        )

    logger.info("image uploaded zone_id=%s filename=%s", zone_id, file.filename)
    response = _to_response(result["record"])
    response.quality = (
        result["quality"] and
        {
            "blur_score": result["quality"]["blur_score"],
            "blur_status": result["quality"]["blur_status"],
            "brightness_score": result["quality"]["brightness_score"],
            "brightness_status": result["quality"]["brightness_status"],
        }
    )
    response.reasons = result["quality"]["reasons"]
    return response


@router.get(
    "/zones/{zone_id}/images",
    response_model=list[ImageResponse],
    summary="List image metadata for a zone",
    description="Return image metadata records for a zone, newest first.",
)
def list_zone_images(
    zone_id: int,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum records (1-500)."),
    db: Session = Depends(get_db),
) -> list[ImageResponse]:
    """Return image metadata for a zone, newest first."""
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found"
        )
    records = (
        db.query(ImageMetadata)
        .filter(ImageMetadata.zone_id == zone_id)
        .order_by(ImageMetadata.created_at.desc(), ImageMetadata.id.desc())
        .limit(limit)
        .all()
    )
    return [_to_response(r) for r in records]


@router.get(
    "/images/{image_id}",
    response_model=ImageResponse,
    summary="Get image metadata by ID",
    description="Return the metadata record for a specific image.",
)
def get_image(image_id: int, db: Session = Depends(get_db)) -> ImageResponse:
    """Return metadata for a specific image."""
    record = db.get(ImageMetadata, image_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )
    return _to_response(record)
