"""Image intake service: validate, store and quality-check crop images."""

import logging
import os
from typing import Any

from sqlalchemy.orm import Session

from app.images import quality, storage
from app.models.image_metadata import ImageMetadata
from app.models.zone import Zone

logger = logging.getLogger("midori.images")

VALID_SOURCES = {"simulated_camera", "uploaded", "replayed"}

# Internal status model (only statuses actually implemented are used).
STATUS_READY_FOR_AI = "READY_FOR_AI"
STATUS_LOW_QUALITY = "LOW_QUALITY"
STATUS_REJECTED = "REJECTED"


def process_upload(
    db: Session,
    zone: Zone,
    data: bytes,
    content_type: str | None,
    original_filename: str,
    source: str,
) -> dict[str, Any]:
    """Validate, store and quality-check an uploaded image.

    Returns a dict with ``rejected``/``reason`` for invalid files, or the
    created ``ImageMetadata`` plus computed quality info.
    """
    original_filename = storage.sanitize_filename(original_filename)

    # --- Validation (reject before touching the filesystem) ---------------
    if not data:
        return {"rejected": True, "reason": "Uploaded file is empty"}
    if not storage.content_type_supported(content_type):
        return {
            "rejected": True,
            "reason": f"Unsupported content type '{content_type}'. "
            f"Supported: {', '.join(sorted(set(storage.SUPPORTED_CONTENT_TYPES)))}.",
        }
    if len(data) > storage.MAX_FILE_SIZE:
        return {
            "rejected": True,
            "reason": f"File exceeds the maximum size of "
            f"{storage.MAX_FILE_SIZE} bytes",
        }

    quality_info = quality.compute_quality(data)
    if not quality_info["decoded"]:
        return {"rejected": True, "reason": "Image could not be decoded"}

    # --- Store -------------------------------------------------------------
    relative_path = storage.save_image(zone.id, content_type, data)
    quality_status = (
        STATUS_READY_FOR_AI if quality_info["acceptable"] else STATUS_LOW_QUALITY
    )

    record = ImageMetadata(
        zone_id=zone.id,
        filename=original_filename,
        stored_filename=os.path.basename(relative_path),
        content_type=(content_type or "").lower(),
        file_size=len(data),
        width=quality_info["width"],
        height=quality_info["height"],
        image_hash=storage.sha256_hex(data),
        source=source,
        storage_path=relative_path,
        quality_status=quality_status,
        blur_score=quality_info["blur_score"],
        brightness_score=quality_info["brightness_score"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        "image stored image_id=%s zone_id=%s status=%s source=%s",
        record.id,
        zone.id,
        record.quality_status,
        source,
    )
    return {"rejected": False, "record": record, "quality": quality_info}
