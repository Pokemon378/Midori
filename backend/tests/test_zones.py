"""Tests for zone APIs."""

FARM_PAYLOAD = {"name": "Farm 01", "location": "Maharashtra", "area_acres": 5.0}


def _create_farm(client) -> int:
    return client.post("/farms", json=FARM_PAYLOAD).json()["id"]


def test_create_zone_for_valid_farm(client):
    farm_id = _create_farm(client)
    response = client.post(f"/farms/{farm_id}/zones", json={"name": "Zone A"})
    assert response.status_code == 201
    data = response.json()
    assert data["farm_id"] == farm_id
    assert data["name"] == "Zone A"


def test_create_zone_invalid_farm_returns_404(client):
    response = client.post("/farms/999/zones", json={"name": "Zone A"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Farm not found."


def test_create_zone_empty_name_fails(client):
    farm_id = _create_farm(client)
    response = client.post(f"/farms/{farm_id}/zones", json={"name": ""})
    assert response.status_code == 422


def test_list_zones(client):
    farm_id = _create_farm(client)
    client.post(f"/farms/{farm_id}/zones", json={"name": "Zone A"})
    client.post(f"/farms/{farm_id}/zones", json={"name": "Zone B"})
    response = client.get(f"/farms/{farm_id}/zones")
    assert response.status_code == 200
    assert [z["name"] for z in response.json()] == ["Zone A", "Zone B"]


def test_get_zone(client):
    farm_id = _create_farm(client)
    zone = client.post(f"/farms/{farm_id}/zones", json={"name": "Zone A"}).json()
    response = client.get(f"/zones/{zone['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Zone A"


def test_get_non_existing_zone_returns_404(client):
    response = client.get("/zones/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found."
