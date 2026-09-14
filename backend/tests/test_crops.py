"""Tests for crop APIs."""


def _setup_zone(client) -> int:
    farm = client.post(
        "/farms", json={"name": "Farm 01", "location": "Maharashtra"}
    ).json()
    return client.post(f"/farms/{farm['id']}/zones", json={"name": "Zone A"}).json()["id"]


CROP_PAYLOAD = {"crop_name": "Tomato", "crop_stage": "Vegetative", "sowing_date": "2026-08-01"}


def test_create_crop_for_valid_zone(client):
    zone_id = _setup_zone(client)
    response = client.post(f"/zones/{zone_id}/crop", json=CROP_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["zone_id"] == zone_id
    assert data["crop_name"] == "Tomato"
    assert data["crop_stage"] == "Vegetative"
    assert data["sowing_date"] == "2026-08-01"


def test_create_crop_invalid_zone_returns_404(client):
    response = client.post("/zones/999/crop", json=CROP_PAYLOAD)
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found."


def test_create_crop_only_one_per_zone(client):
    zone_id = _setup_zone(client)
    assert client.post(f"/zones/{zone_id}/crop", json=CROP_PAYLOAD).status_code == 201
    duplicate = client.post(f"/zones/{zone_id}/crop", json={"crop_name": "Maize"})
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Zone already has an assigned crop."


def test_create_crop_empty_name_fails(client):
    zone_id = _setup_zone(client)
    response = client.post(f"/zones/{zone_id}/crop", json={"crop_name": ""})
    assert response.status_code == 422


def test_create_crop_invalid_sowing_date_fails(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/crop", json={"crop_name": "Tomato", "sowing_date": "not-a-date"}
    )
    assert response.status_code == 422


def test_get_crop(client):
    zone_id = _setup_zone(client)
    client.post(f"/zones/{zone_id}/crop", json=CROP_PAYLOAD)
    response = client.get(f"/zones/{zone_id}/crop")
    assert response.status_code == 200
    assert response.json()["crop_name"] == "Tomato"


def test_get_crop_no_crop_assigned_returns_404(client):
    zone_id = _setup_zone(client)
    response = client.get(f"/zones/{zone_id}/crop")
    assert response.status_code == 404
    assert response.json()["detail"] == "No crop assigned to this zone."


def test_get_crop_invalid_zone_returns_404(client):
    response = client.get("/zones/999/crop")
    assert response.status_code == 404
