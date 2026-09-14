"""Tests for sensor reading APIs."""

from datetime import datetime, timedelta, timezone

VALID_READING = {
    "timestamp": "2026-09-15T10:00:00+05:30",
    "temperature": 29.4,
    "humidity": 86,
    "rainfall": 12.5,
    "leaf_wetness": 78,
    "soil_moisture": 64,
    "pest_activity": 7,
}


def _setup_zone(client) -> int:
    farm = client.post(
        "/farms", json={"name": "Farm 01", "location": "Maharashtra"}
    ).json()
    return client.post(f"/farms/{farm['id']}/zones", json={"name": "Zone A"}).json()["id"]


def test_create_valid_sensor_reading(client):
    zone_id = _setup_zone(client)
    response = client.post(f"/zones/{zone_id}/sensor-readings", json=VALID_READING)
    assert response.status_code == 201
    data = response.json()
    assert data["zone_id"] == zone_id
    assert data["temperature"] == 29.4
    assert data["humidity"] == 86
    assert data["rainfall"] == 12.5
    assert data["leaf_wetness"] == 78
    assert data["soil_moisture"] == 64
    assert data["pest_activity"] == 7
    assert data["id"] == 1
    assert "created_at" in data


def test_create_reading_nonexistent_zone_returns_404(client):
    response = client.post("/zones/999/sensor-readings", json=VALID_READING)
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found"


def test_invalid_humidity_rejected(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/sensor-readings", json={**VALID_READING, "humidity": 101}
    )
    assert response.status_code == 422


def test_invalid_leaf_wetness_rejected(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/sensor-readings", json={**VALID_READING, "leaf_wetness": -5}
    )
    assert response.status_code == 422


def test_invalid_soil_moisture_rejected(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/sensor-readings", json={**VALID_READING, "soil_moisture": 110}
    )
    assert response.status_code == 422


def test_invalid_rainfall_rejected(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/sensor-readings", json={**VALID_READING, "rainfall": -1}
    )
    assert response.status_code == 422


def test_invalid_pest_activity_rejected(client):
    zone_id = _setup_zone(client)
    for bad in (-1, 101):
        response = client.post(
            f"/zones/{zone_id}/sensor-readings",
            json={**VALID_READING, "pest_activity": bad},
        )
        assert response.status_code == 422


def test_invalid_temperature_rejected(client):
    zone_id = _setup_zone(client)
    response = client.post(
        f"/zones/{zone_id}/sensor-readings", json={**VALID_READING, "temperature": 80}
    )
    assert response.status_code == 422


def test_missing_timestamp_rejected(client):
    zone_id = _setup_zone(client)
    payload = {k: v for k, v in VALID_READING.items() if k != "timestamp"}
    response = client.post(f"/zones/{zone_id}/sensor-readings", json=payload)
    assert response.status_code == 422


def test_list_sensor_readings_newest_first(client):
    zone_id = _setup_zone(client)
    old = {**VALID_READING, "timestamp": "2026-09-15T08:00:00+05:30"}
    new = {**VALID_READING, "timestamp": "2026-09-15T12:00:00+05:30"}
    client.post(f"/zones/{zone_id}/sensor-readings", json=old)
    client.post(f"/zones/{zone_id}/sensor-readings", json=new)
    response = client.get(f"/zones/{zone_id}/sensor-readings")
    assert response.status_code == 200
    timestamps = [r["timestamp"] for r in response.json()]
    assert len(timestamps) == 2
    assert timestamps[0] > timestamps[1]


def test_list_sensor_readings_limit(client):
    zone_id = _setup_zone(client)
    base = datetime(2026, 9, 15, 6, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    for i in range(5):
        reading = {
            **VALID_READING,
            "timestamp": (base + timedelta(hours=i)).isoformat(),
        }
        client.post(f"/zones/{zone_id}/sensor-readings", json=reading)
    response = client.get(f"/zones/{zone_id}/sensor-readings?limit=3")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_readings_nonexistent_zone_returns_404(client):
    response = client.get("/zones/999/sensor-readings")
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found"


def test_get_latest_sensor_reading(client):
    zone_id = _setup_zone(client)
    old = {**VALID_READING, "timestamp": "2026-09-15T08:00:00+05:30"}
    new = {**VALID_READING, "timestamp": "2026-09-15T12:00:00+05:30"}
    client.post(f"/zones/{zone_id}/sensor-readings", json=old)
    client.post(f"/zones/{zone_id}/sensor-readings", json=new)
    response = client.get(f"/zones/{zone_id}/sensor-readings/latest")
    assert response.status_code == 200
    assert response.json()["timestamp"].startswith("2026-09-15T12:00:00")


def test_get_latest_no_readings_returns_404(client):
    zone_id = _setup_zone(client)
    response = client.get(f"/zones/{zone_id}/sensor-readings/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "No sensor readings found for this zone"


def test_get_latest_nonexistent_zone_returns_404(client):
    response = client.get("/zones/999/sensor-readings/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found"
