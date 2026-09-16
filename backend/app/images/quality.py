"""Image quality checks: resolution, blur, brightness.

All metrics are deterministic and suitability-only — they say nothing about
disease or pests. Thresholds are configurable in one place.
"""

import io
import os
from typing import Any

from PIL import Image

# --- Configuration (MVP defaults; tune after validation) ---------------------

# Resolution (phone/camera friendly; deliberately not demanding).
MIN_WIDTH = int(os.getenv("IMAGE_MIN_WIDTH", "200"))
MIN_HEIGHT = int(os.getenv("IMAGE_MIN_HEIGHT", "200"))

# Blur: Laplacian variance over the grayscale image. Higher = sharper.
BLUR_ACCEPT_THRESHOLD = float(os.getenv("IMAGE_BLUR_THRESHOLD", "60.0"))

# Brightness: mean grayscale intensity (0–255).
BRIGHTNESS_DARK_THRESHOLD = float(os.getenv("IMAGE_BRIGHTNESS_DARK", "50.0"))
BRIGHTNESS_BRIGHT_THRESHOLD = float(os.getenv("IMAGE_BRIGHTNESS_BRIGHT", "215.0"))


def compute_quality(image_bytes: bytes) -> dict[str, Any]:
    """Decode the image and compute all quality metrics.

    Returns a dict with:
    - ``decoded``: whether the image could be decoded
    - ``width``/``height``: dimensions (None if undecodable)
    - ``blur_score``/``blur_status``
    - ``brightness_score``/``brightness_status``
    - ``reasons``: list of human-readable quality concerns
    - ``acceptable``: overall suitability verdict
    """
    reasons: list[str] = []

    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            img.verify()  # structural integrity
        with Image.open(io.BytesIO(image_bytes)) as img:
            img = img.convert("L")  # grayscale for metrics
            width, height = img.size
    except Exception:
        return {
            "decoded": False,
            "width": None,
            "height": None,
            "blur_score": None,
            "blur_status": None,
            "brightness_score": None,
            "brightness_status": None,
            "reasons": ["Image could not be decoded"],
            "acceptable": False,
        }

    # Resolution
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        reasons.append(
            f"Resolution {width}x{height} is below the minimum "
            f"{MIN_WIDTH}x{MIN_HEIGHT}"
        )

    # Blur: Laplacian variance (deterministic, explainable focus metric).
    blur_score = _laplacian_variance(img)
    blur_status = (
        "acceptable" if blur_score >= BLUR_ACCEPT_THRESHOLD else "blurry"
    )
    if blur_status == "blurry":
        reasons.append(f"Image appears blurry (focus score {blur_score:.1f})")

    # Brightness: mean grayscale intensity 0-255.
    pixels = list(img.getdata())
    brightness_score = sum(pixels) / len(pixels)
    if brightness_score < BRIGHTNESS_DARK_THRESHOLD:
        brightness_status = "too_dark"
        reasons.append(f"Image is too dark (brightness {brightness_score:.1f})")
    elif brightness_score > BRIGHTNESS_BRIGHT_THRESHOLD:
        brightness_status = "too_bright"
        reasons.append(f"Image is too bright (brightness {brightness_score:.1f})")
    else:
        brightness_status = "acceptable"

    return {
        "decoded": True,
        "width": width,
        "height": height,
        "blur_score": round(blur_score, 2),
        "blur_status": blur_status,
        "brightness_score": round(brightness_score, 2),
        "brightness_status": brightness_status,
        "reasons": reasons,
        "acceptable": not reasons,
    }


def _laplacian_variance(img: Image.Image) -> float:
    """Variance of the Laplacian of a grayscale PIL image.

    Implemented with pure PIL operations so no extra dependency (numpy/
    opencv) is required. A sharper image yields a higher variance.
    """
    width, height = img.size
    pixels = list(img.getdata())
    variances: list[float] = []
    for y in range(1, height - 1):
        row = y * width
        for x in range(1, width - 1):
            center = pixels[row + x]
            lap = (
                -4 * center
                + pixels[row + x - 1]
                + pixels[row + x + 1]
                + pixels[row - width + x]
                + pixels[row + width + x]
            )
            variances.append(lap)
    if not variances:
        return 0.0
    mean = sum(variances) / len(variances)
    return sum((v - mean) ** 2 for v in variances) / len(variances)
