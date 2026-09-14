"""Tests for farm APIs."""

FARM_PAYLOAD = {"name": "Farm 01", "location": "Maharashtra", "area_acres": 5.0}


def test_create_farm(client):
    response = client.post("/farms", json=FARM_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Farm 01"
    assert data["location"] == "Maharashtra"
    assert data["area_acres"] == 5.0
    assert "created_at" in data


def test_create_farm_without_area(client):
    response = client.post("/farms", json={"name": "Farm 02", "location": "Punjab"})
    assert response.status_code == 201
    assert response.json()["area_acres"] is None


def test_create_farm_empty_name_fails(client):
    response = client.post("/farms", json={"name": "", "location": "X"})
    assert response.status_code == 422


def test_create_farm_invalid_area_fails(client):
    response = client.post("/farms", json={"name": "F", "location": "X", "area_acres": -1})
    assert response.status_code == 422


def test_list_farms(client):
    client.post("/farms", json=FARM_PAYLOAD)
    client.post("/farms", json={"name": "Farm 02", "location": "Punjab"})
    response = client.get("/farms")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_farm(client):
    created = client.post("/farms", json=FARM_PAYLOAD).json()
    response = client.get(f"/farms/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Farm 01"


def test_get_non_existing_farm_returns_404(client):
    response = client.get("/farms/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Farm not found."
