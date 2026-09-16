"""Tests for image intake (Step 6).

All test images are generated deterministically in-memory with Pillow —
no external files or network. Conftest provides an isolated test database.
"""

import io
import os

import pytest
from PIL import Image

from app.images import quality, storage


# --- Deterministic test image builders ----------------------------------------


def _png_bytes(width=400, height=300, color=(60, 120, 60), noisy=False) -> bytes:
    """Build a deterministic PNG. `noisy=True` creates sharp edges (in focus)."""
    img = Image.new("RGB", (width, height), color)
    if noisy:
        # Checkerboard of 2x2 blocks -> very high Laplacian variance.
        px = img.load()
        for y in range(height):
            for x in range(width):
                v = 255 if ((x // 2) + (y // 2)) % 2 == 0 else 0
                px[x, y] = (v, v, v)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(width=400, height=300, color=(60, 120, 60), noisy=True) -> bytes:
    img = Image.new("RGB", (width, height), color)
    if noisy:
        px = img.load()
        for y in range(height):
            for x in range(width):
                v = 255 if ((x // 2) + (y // 2)) % 2 == 0 else 0
                px[x, y] = (v, v, v)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _webp_bytes(width=400, height=300) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (80, 140, 80)).save(buf, format="WEBP")
    return buf.getvalue()


def _setup_zone(client) -> int:
    farm = client.post(
        "/farms", json={"name": "Image Farm", "location": "Maharashtra"}
    ).json()
    return client.post(
        f"/farms/{farm['id']}/zones", json={"name": "Zone Img"}
    ).json()["id"]


def _upload(client, zone_id, data, filename="test.png", content_type="image/png",
            source="uploaded"):
    return client.post(
        f"/zones/{zone_id}/images",
        files={"file": (filename, data, content_type)},
        data={"source": source},
    )


@pytest.fixture(autouse=True)
def _tmp_storage(tmp_path, monkeypatch):
    """Redirect image storage to a temp dir for every test."""
    monkeypatch.setattr(storage, "BASE_STORAGE_DIR", str(tmp_path / "images"))
    yield


# --- Upload / formats ----------------------------------------------------------


def test_upload_valid_jpeg(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _jpeg_bytes(), "crop.jpg", "image/jpeg")
    assert r.status_code == 201
    body = r.json()
    assert body["quality_status"] == "READY_FOR_AI"
    assert body["content_type"] == "image/jpeg"
    assert body["width"] == 400 and body["height"] == 300
    assert body["quality"]["blur_status"] == "acceptable"


def test_upload_valid_png(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _png_bytes(noisy=True), "crop.png", "image/png")
    assert r.status_code == 201
    assert r.json()["quality_status"] == "READY_FOR_AI"


def test_upload_valid_webp(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _webp_bytes(), "crop.webp", "image/webp")
    assert r.status_code == 201
    assert r.json()["quality_status"] in ("READY_FOR_AI", "LOW_QUALITY")


def test_unsupported_file_type_rejected(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, b"not an image", "notes.txt", "text/plain")
    assert r.status_code == 400
    assert "Unsupported content type" in r.json()["detail"]


def test_gif_rejected(client):
    zone_id = _setup_zone(client)
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, format="GIF")
    r = _upload(client, zone_id, buf.getvalue(), "anim.gif", "image/gif")
    assert r.status_code == 400


def test_empty_upload_rejected(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, b"", "empty.png", "image/png")
    assert r.status_code == 400
    assert "empty" in r.json()["detail"]


def test_corrupted_image_rejected(client):
    zone_id = _setup_zone(client)
    # Valid PNG magic bytes, garbage body -> decode must fail.
    data = b"\x89PNG\r\n\x1a\n" + os.urandom(64).hex().encode()
    r = _upload(client, zone_id, data, "broken.png", "image/png")
    assert r.status_code == 400
    assert "decoded" in r.json()["detail"]


def test_file_too_large_rejected(client, monkeypatch):
    zone_id = _setup_zone(client)
    monkeypatch.setattr(storage, "MAX_FILE_SIZE", 100)
    r = _upload(client, zone_id, _jpeg_bytes(), "big.jpg", "image/jpeg")
    assert r.status_code == 400
    assert "maximum size" in r.json()["detail"]


def test_nonexistent_zone_returns_404(client):
    r = _upload(client, 999999, _jpeg_bytes(), "crop.jpg", "image/jpeg")
    assert r.status_code == 404
    assert r.json()["detail"] == "Zone not found"


def test_invalid_source_rejected(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _jpeg_bytes(), "c.jpg", "image/jpeg", source="drone")
    assert r.status_code == 400


# --- Quality checks -------------------------------------------------------------


def test_below_minimum_resolution_is_low_quality(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _png_bytes(width=50, height=40, noisy=True), "tiny.png",
                "image/png")
    assert r.status_code == 201
    body = r.json()
    assert body["quality_status"] == "LOW_QUALITY"
    assert any("Resolution" in reason for reason in body["reasons"])


def test_blurry_image_is_low_quality(client):
    zone_id = _setup_zone(client)
    # Flat uniform color -> zero Laplacian variance -> blurry.
    r = _upload(client, zone_id, _jpeg_bytes(noisy=False), "flat.jpg", "image/jpeg")
    assert r.status_code == 201
    body = r.json()
    assert body["quality"]["blur_status"] == "blurry"
    assert body["quality_status"] == "LOW_QUALITY"
    assert any("blurry" in reason for reason in body["reasons"])


def test_too_dark_image_is_low_quality(client):
    zone_id = _setup_zone(client)
    # Plain dark image (no checkerboard, which would average out to mid-gray).
    r = _upload(client, zone_id, _png_bytes(color=(5, 5, 5), noisy=False), "dark.png",
                "image/png")
    body = r.json()
    assert body["quality"]["brightness_status"] == "too_dark"
    assert body["quality_status"] == "LOW_QUALITY"


def test_too_bright_image_is_low_quality(client):
    zone_id = _setup_zone(client)
    # Plain white image (no checkerboard, which would average out to mid-gray).
    r = _upload(client, zone_id, _png_bytes(color=(255, 255, 255), noisy=False),
                "bright.png", "image/png")
    body = r.json()
    assert body["quality"]["brightness_status"] == "too_bright"
    assert body["quality_status"] == "LOW_QUALITY"


def test_good_quality_image_is_ready_for_ai(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _png_bytes(noisy=True), "good.png", "image/png")
    body = r.json()
    assert body["quality_status"] == "READY_FOR_AI"
    assert body["reasons"] == []
    assert body["quality"]["blur_status"] == "acceptable"
    assert body["quality"]["brightness_status"] == "acceptable"


def test_quality_functions_are_deterministic(client):
    data = _jpeg_bytes()
    first = quality.compute_quality(data)
    second = quality.compute_quality(data)
    assert first == second


# --- Retrieval -------------------------------------------------------------------


def test_get_image_metadata(client):
    zone_id = _setup_zone(client)
    created = _upload(client, zone_id, _jpeg_bytes(), "meta.jpg", "image/jpeg").json()
    r = client.get(f"/images/{created['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == created["id"]
    assert body["filename"] == "meta.jpg"
    assert body["zone_id"] == zone_id
    assert body["source"] == "uploaded"
    assert "image_hash" in body and len(body["image_hash"]) == 64


def test_get_image_metadata_nonexistent(client):
    r = client.get("/images/999999")
    assert r.status_code == 404


def test_list_zone_images(client):
    zone_id = _setup_zone(client)
    for i in range(3):
        _upload(client, zone_id, _jpeg_bytes(color=(50 + i, 120, 60)), f"c{i}.jpg",
                "image/jpeg")
    r = client.get(f"/zones/{zone_id}/images")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_list_zone_images_limit(client):
    zone_id = _setup_zone(client)
    for i in range(3):
        _upload(client, zone_id, _jpeg_bytes(color=(50 + i, 120, 60)), f"c{i}.jpg",
                "image/jpeg")
    r = client.get(f"/zones/{zone_id}/images?limit=2")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_images_nonexistent_zone(client):
    r = client.get("/zones/999999/images")
    assert r.status_code == 404


# --- Storage safety ---------------------------------------------------------------


def test_storage_filename_is_unique_and_safe(client):
    zone_id = _setup_zone(client)
    names = set()
    for i in range(3):
        rec = _upload(client, zone_id, _jpeg_bytes(), "c.jpg", "image/jpeg").json()
        names.add(rec["stored_filename"])
        # Never the client filename; always inside the zone directory.
        assert rec["stored_filename"] != "c.jpg"
        assert rec["storage_path"].startswith(f"zone_{zone_id}{os.sep}")
    assert len(names) == 3  # unique names, no overwrites


def test_sanitized_filename_strips_traversal(client):
    assert storage.sanitize_filename("../../etc/passwd") == "passwd"
    assert storage.sanitize_filename("..\\..\\windows\\system32") == "system32"
    assert storage.sanitize_filename("") == "upload"
    # Path components are stripped; result can never traverse directories.
    assert storage.sanitize_filename("../..") in ("..", "")
    assert "/" not in storage.sanitize_filename("../../etc/passwd")
    assert "\\" not in storage.sanitize_filename("..\\..\\x")


def test_file_actually_stored_on_disk(client, tmp_path):
    zone_id = _setup_zone(client)
    rec = _upload(client, zone_id, _jpeg_bytes(), "disk.jpg", "image/jpeg").json()
    full = os.path.join(str(tmp_path), "images", rec["storage_path"])
    assert os.path.exists(full)
    with open(full, "rb") as handle:
        assert handle.read() == _jpeg_bytes()


# --- Sources ----------------------------------------------------------------------


def test_simulated_camera_source(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _jpeg_bytes(), "cam.jpg", "image/jpeg",
                source="simulated_camera")
    assert r.status_code == 201
    assert r.json()["source"] == "simulated_camera"


def test_replayed_source(client):
    zone_id = _setup_zone(client)
    r = _upload(client, zone_id, _jpeg_bytes(), "rep.jpg", "image/jpeg", source="replayed")
    assert r.status_code == 201
    assert r.json()["source"] == "replayed"
