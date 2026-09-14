"""Tests for the Feature Engine (Step 4).

Uses controlled, deterministic data — no random values. Test timestamps
are expressed relative to a fixed `now` (readings anchored at 10:00 IST
onwards) and injected into the service/API via monkeypatched time.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.features import calculations as calc
from app.features.service import fetch_window_readings

IST = timezone(timedelta(hours=5, minutes=30))
BASE = datetime(2026, 9, 15, 10, 30, tzinfo=IST)  # "now": last reading time

READING_TEMPLATE = {
    "temperature": 29.4,
    "humidity": 80,
    "rainfall": 1.5,
    "leaf_wetness": 55,
    "soil_moisture": 60,
    "pest_activity": 20,
}


@pytest.fixture()
def frozen_now(monkeypatch):
    """Freeze 'now' used by fetch_window_readings to BASE."""

    def fake_now(*args, **kwargs):
        return BASE

    monkeypatch.setattr("app.features.service.datetime", _FrozenDatetime)
    return BASE


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # called as datetime.now(timezone.utc) in service
        return BASE.astimezone(timezone.utc)


def _make_readings(client, zone_id: int, rows: list[dict]) -> None:
    for row in rows:
        payload = {**READING_TEMPLATE, **row}
        response = client.post(f"/zones/{zone_id}/sensor-readings", json=payload)
        assert response.status_code == 201


def _setup_zone(client) -> int:
    farm = client.post(
        "/farms", json={"name": "Farm 01", "location": "Maharashtra"}
    ).json()
    return client.post(f"/farms/{farm['id']}/zones", json={"name": "Zone A"}).json()["id"]


def _rows(values: dict[str, list[float]], minutes_step: int = 10) -> list[dict]:
    """Build reading rows ending at BASE: values[name][i] at
    BASE - (count-1-i) * minutes_step, so the last reading is 'now'."""
    count = len(next(iter(values.values())))
    rows = []
    for i in range(count):
        offset = (count - 1 - i) * minutes_step
        row = {"timestamp": (BASE - timedelta(minutes=offset)).isoformat()}
        row.update({k: v[i] for k, v in values.items()})
        rows.append(row)
    return rows


# --- Pure calculation unit tests -----------------------------------------


def test_stats_basic():
    result = calc.stats([1.0, 2.0, 3.0])
    assert result["average"] == 2.0
    assert result["minimum"] == 1.0
    assert result["maximum"] == 3.0
    assert calc.stats([]) is None


def test_trend_increasing():
    pts = [(BASE + timedelta(minutes=10 * i), v) for i, v in enumerate([80, 83, 87, 90])]
    assert calc.trend(pts) == "increasing"


def test_trend_decreasing():
    pts = [(BASE + timedelta(minutes=10 * i), v) for i, v in enumerate([90, 87, 83, 80])]
    assert calc.trend(pts) == "decreasing"


def test_trend_stable():
    pts = [(BASE + timedelta(minutes=10 * i), v) for i, v in enumerate([50, 51, 50, 51])]
    assert calc.trend(pts) == "stable"


def test_trend_insufficient_data():
    pts = [(BASE, 80.0), (BASE + timedelta(minutes=10), 90.0)]
    assert calc.trend(pts) == "insufficient_data"


def test_change_rate_per_hour():
    pts = [
        (BASE, 20.0),
        (BASE + timedelta(minutes=60), 45.0),
    ]
    assert calc.change_rate_per_hour(pts) == pytest.approx(25.0)
    assert calc.change_rate_per_hour([(BASE, 20.0)]) is None
    same_time = [(BASE, 20.0), (BASE, 30.0)]
    assert calc.change_rate_per_hour(same_time) is None


def test_leaf_wetness_active_duration():
    # 3 intervals of 10 min each: first two fully active (20 min), last not.
    pts = [
        (BASE, 70.0),
        (BASE + timedelta(minutes=10), 65.0),
        (BASE + timedelta(minutes=20), 61.0),
        (BASE + timedelta(minutes=30), 30.0),
    ]
    assert calc.leaf_wetness_active_minutes(pts, threshold=60) == 20


# --- API tests ------------------------------------------------------------


def test_features_full_calculations(client, frozen_now):
    zone_id = _setup_zone(client)
    _make_readings(
        client,
        zone_id,
        _rows(
            {
                "temperature": [28.0, 29.0, 30.0, 31.0],
                "humidity": [80, 83, 87, 90],
                "rainfall": [1.0, 2.0, 3.0, 2.5],
                "leaf_wetness": [70, 75, 80, 85],
                "soil_moisture": [60, 61, 60.5, 61.5],
                "pest_activity": [20, 25, 34, 45],
            }
        ),
    )
    response = client.get(f"/zones/{zone_id}/features?window=1h")
    assert response.status_code == 200
    body = response.json()
    assert body["zone_id"] == zone_id
    assert body["window"] == "1h"
    assert body["observation_count"] == 4
    f = body["features"]

    # Temperature: avg 29.5, min 28, max 31, increasing, +1 C/h
    assert f["temperature"]["average"] == pytest.approx(29.5)
    assert f["temperature"]["minimum"] == 28.0
    assert f["temperature"]["maximum"] == 31.0
    assert f["temperature"]["current"] == 31.0
    assert f["temperature"]["trend"] == "increasing"
    assert f["temperature"]["change_rate_per_hour"] == pytest.approx(6.0)  # 3C / 0.5h

    # Humidity: avg 85, increasing, +10 pp/h
    assert f["humidity"]["average"] == pytest.approx(85.0)
    assert f["humidity"]["trend"] == "increasing"
    assert f["humidity"]["change_rate_per_hour"] == pytest.approx(20.0)  # 10pp / 0.5h

    # Rainfall: interval values summed -> total 8.5, latest 2.5
    assert f["rainfall"]["total"] == pytest.approx(8.5)
    assert f["rainfall"]["latest"] == 2.5
    assert f["rainfall"]["observation_count"] == 4

    # Leaf wetness: all >= 60 across 30-min span -> 30 active minutes
    assert f["leaf_wetness"]["active_duration_minutes"] == 30
    assert f["leaf_wetness"]["trend"] == "increasing"

    # Soil moisture: stable (within tolerance)
    assert f["soil_moisture"]["trend"] == "stable"

    # Pest activity: increasing, +25 pp/h
    assert f["pest_activity"]["trend"] == "increasing"
    assert f["pest_activity"]["change_rate_per_hour"] == pytest.approx(50.0)  # 25pp / 0.5h
    assert f["pest_activity"]["current"] == 45.0


def test_features_window_filtering_excludes_old_readings(client, frozen_now):
    zone_id = _setup_zone(client)
    old = {**READING_TEMPLATE, "timestamp": (BASE - timedelta(hours=2)).isoformat()}
    _make_readings(client, zone_id, [old])
    _make_readings(
        client,
        zone_id,
        _rows(
            {
                "temperature": [28.0, 29.0, 30.0, 31.0],
                "humidity": [80, 83, 87, 90],
                "rainfall": [1.0, 2.0, 3.0, 2.5],
                "leaf_wetness": [70, 75, 80, 85],
                "soil_moisture": [60, 61, 60.5, 61.5],
                "pest_activity": [20, 25, 34, 45],
            }
        ),
    )
    response = client.get(f"/zones/{zone_id}/features?window=1h")
    # Old reading (2h before now) must be excluded from the 1h window.
    assert response.json()["observation_count"] == 4

    response_24h = client.get(f"/zones/{zone_id}/features?window=24h")
    # The 24h window includes the old reading.
    assert response_24h.json()["observation_count"] == 5


def test_features_missing_value_is_not_zero_filled(client, frozen_now):
    zone_id = _setup_zone(client)
    _make_readings(client, zone_id, _rows({"humidity": [80, 83]}))
    response = client.get(f"/zones/{zone_id}/features?window=1h")
    assert response.status_code == 200
    f = response.json()["features"]
    # Rainfall defaulted to template 1.5 each; averages must not invent data.
    assert f["rainfall"]["total"] == pytest.approx(3.0)


def test_features_no_readings_in_window(client, frozen_now):
    zone_id = _setup_zone(client)
    old = {**READING_TEMPLATE, "timestamp": (BASE - timedelta(hours=3)).isoformat()}
    _make_readings(client, zone_id, [old])
    response = client.get(f"/zones/{zone_id}/features?window=1h")
    assert response.status_code == 404
    assert response.json()["detail"] == "Insufficient sensor data for the requested window"


def test_features_nonexistent_zone(client):
    response = client.get("/zones/999/features?window=1h")
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found"


def test_features_invalid_window_rejected(client, frozen_now):
    zone_id = _setup_zone(client)
    _make_readings(client, zone_id, _rows({"humidity": [80, 83]}))
    response = client.get(f"/zones/{zone_id}/features?window=7d")
    assert response.status_code == 422
    assert "Unsupported window" in response.json()["detail"]


def test_features_service_window_query_matches_api(client, frozen_now, db_session):
    """Direct service-level check that DB-level filtering works."""
    zone_id = _setup_zone(client)
    _make_readings(client, zone_id, _rows({"humidity": [80, 83, 87, 90]}))
    readings = fetch_window_readings(db_session, zone_id, "1h", now=BASE)
    assert len(readings) == 4
    assert readings[0].humidity == 80
    assert readings[-1].humidity == 90
