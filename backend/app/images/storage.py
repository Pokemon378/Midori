"""Filesystem storage for uploaded crop images.

Files are stored under ``storage/images/zone_<id>/`` with safe unique
names. Uploaded filenames are never trusted as storage names.
"""

import hashlib
import os
import re
import uuid

BASE_STORAGE_DIR = os.getenv("IMAGE_STORAGE_DIR", os.path.join("storage", "images"))
MAX_FILE_SIZE = int(os.getenv("IMAGE_MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10 MB

SUPPORTED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str) -> str:
    """Strip anything risky from a client-supplied filename.

    Prevents path traversal: separators, ``..`` and unusual characters are
    removed; the result is only ever used for display, never as the
    storage name.
    """
    base = os.path.basename(name or "")
    return _SAFE_NAME_RE.sub("_", base)[:120] or "upload"


def content_type_supported(content_type: str | None) -> bool:
    """Whether the declared MIME type is an accepted image format."""
    return (content_type or "").lower() in SUPPORTED_CONTENT_TYPES


def content_type_extension(content_type: str | None) -> str:
    """File extension for a supported MIME type ('' if unsupported)."""
    return SUPPORTED_CONTENT_TYPES.get((content_type or "").lower(), "")


def zone_dir(zone_id: int) -> str:
    """Directory for a zone's images (created lazily)."""
    path = os.path.join(BASE_STORAGE_DIR, f"zone_{zone_id}")
    os.makedirs(path, exist_ok=True)
    return path


def build_stored_filename(zone_id: int, content_type: str | None) -> str:
    """Generate a unique, safe storage filename for a zone."""
    ext = content_type_extension(content_type)
    return f"{uuid.uuid4().hex}{ext}"


def save_image(zone_id: int, content_type: str | None, data: bytes) -> str:
    """Write image bytes to the zone directory; return the relative path."""
    filename = build_stored_filename(zone_id, content_type)
    relative = os.path.join(f"zone_{zone_id}", filename)
    full = os.path.join(zone_dir(zone_id), filename)
    with open(full, "wb") as handle:
        handle.write(data)
    return relative


def sha256_hex(data: bytes) -> str:
    """SHA-256 digest of the raw bytes (duplicate detection aid)."""
    return hashlib.sha256(data).hexdigest()
