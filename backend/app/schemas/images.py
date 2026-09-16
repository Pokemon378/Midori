"""Pydantic schemas for image intake."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class ImageQualityInfo(BaseModel):
    """Quality metrics computed for an image (suitability only, not diagnosis)."""

    blur_score: float
    blur_status: Literal["acceptable", "blurry"]
    brightness_score: float
    brightness_status: Literal["acceptable", "too_dark", "too_bright"]


class ImageResponse(BaseModel):
    """Metadata response for an image stored by the intake module."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    filename: str
    stored_filename: str
    content_type: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    image_hash: str
    source: str
    storage_path: str
    quality_status: Literal[
        "RECEIVED", "QUALITY_CHECKED", "READY_FOR_AI", "LOW_QUALITY", "REJECTED"
    ]
    blur_score: Optional[float] = None
    brightness_score: Optional[float] = None
    quality: Optional[ImageQualityInfo] = None
    reasons: list[str] = []
    created_at: datetime
