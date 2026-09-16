"""Tests for the Risk Engine (Step 5).

Pure-calculation tests use controlled feature dicts (deterministic, no
random values). API tests seed controlled readings via the existing
Sensor Data API and call GET /zones/{id}/risk.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.risk import calculations as rc

BASE = datetime.now(timezone.utc)  # "now": last reading is seeded at BASE


def _features(**overrides):
    """Controlled high-risk feature set (all metrics elevated + increasing)."""
    base = {
        "temperature": {"current": 30.0, "average": 29.5, "minimum": 28.0,
                        "maximum": 31.0, "trend": "stable", "change_rate_per_hour": 1.0},
        "humidity": {"current": 88.0, "average": 84.5, "minimum": 80.0,
                     "maximum": 89.0, "trend": "increasing", "change_rate_per_hour": 18.0},
        "leaf_wetness": {"current": 85.0, "average": 77.5, "minimum": 70.0,
                         "maximum": 85.0, "trend": "increasing",
                         "change_rate_per_hour": 30.0, "active_duration_minutes": 60},
        "soil_moisture": {"current": 61.0, "average": 60.5, "minimum": 60.0,
                          "maximum": 63.0, "trend": "stable", "change_rate_per_hour": 1.0},
        "pest_activity": {"current": 55.0, "average": 35.0, "minimum": 20.0,
                          "maximum": 55.0, "trend": "increasing",
                          "change_rate_per_hour": 40.0},
        "rainfall": {"total": 8.0, "latest": 1.5, "observation_count": 4},
    }
    base.update(overrides)
    return base


# --- Pure calculation tests ------------------------------------------------


def test_low_risk_conditions():
    features = _features(
        humidity={"current": 40.0, "trend": "stable", "change_rate_per_hour": 0.0},
        leaf_wetness={"current": 20.0, "trend": "stable", "change_rate_per_hour": 0.0,
                      "active_duration_minutes": 0},
        temperature={"current": 25.0, "trend": "stable", "change_rate_per_hour": 0.0},
        soil_moisture={"current": 55.0, "trend": "stable", "change_rate_per_hour": 0.0},
        pest_activity={"current": 10.0, "trend": "stable", "change_rate_per_hour": 0.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
    )
    score = rc.calculate_risk_score(features)
    assert 0 <= score <= rc.RISK_THRESHOLDS["low"]
    assert rc.calculate_risk_level(score) == "LOW"


def test_medium_risk_conditions():
    features = _features(
        humidity={"current": 82.0, "trend": "stable", "change_rate_per_hour": 0.0},
        leaf_wetness={"current": 65.0, "trend": "stable", "change_rate_per_hour": 0.0,
                      "active_duration_minutes": 20},
        pest_activity={"current": 30.0, "trend": "stable", "change_rate_per_hour": 0.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
    )
    score = rc.calculate_risk_score(features)
    assert rc.RISK_THRESHOLDS["low"] < score <= rc.RISK_THRESHOLDS["medium"]
    assert rc.calculate_risk_level(score) == "MEDIUM"


def test_high_risk_conditions():
    features = _features(
        pest_activity={"current": 55.0, "trend": "stable", "change_rate_per_hour": 0.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
    )
    score = rc.calculate_risk_score(features)
    assert rc.RISK_THRESHOLDS["medium"] < score <= rc.RISK_THRESHOLDS["high"]
    assert rc.calculate_risk_level(score) == "HIGH"


def test_critical_risk_conditions():
    features = _features()
    score = rc.calculate_risk_score(features)
    assert score > rc.RISK_THRESHOLDS["high"]
    assert rc.calculate_risk_level(score) == "CRITICAL"


def test_score_always_within_0_100():
    extremes = [
        _features(),
        _features(
            humidity={"current": 0.0, "trend": "stable", "change_rate_per_hour": 0.0},
            leaf_wetness={"current": 0.0, "trend": "stable", "change_rate_per_hour": 0.0,
                          "active_duration_minutes": 0},
            pest_activity={"current": 0.0, "trend": "stable", "change_rate_per_hour": 0.0},
            rainfall={"total": 0.0, "latest": 0.0, "observation_count": 1},
            soil_moisture={"current": 0.0, "trend": "stable", "change_rate_per_hour": 0.0},
        ),
        {},  # nothing at all
    ]
    for features in extremes:
        score = rc.calculate_risk_score(features)
        assert score is None or 0.0 <= score <= 100.0


def test_high_humidity_increases_risk_and_factor():
    low = _features(humidity={"current": 40.0, "trend": "stable", "change_rate_per_hour": 0.0})
    high = _features(humidity={"current": 90.0, "trend": "stable", "change_rate_per_hour": 0.0})
    assert rc.calculate_risk_score(high) > rc.calculate_risk_score(low)
    codes = [f["code"] for f in rc.calculate_risk_factors(high)]
    assert "HIGH_HUMIDITY" in codes


def test_prolonged_leaf_wetness_factor():
    features = _features(
        humidity={"current": 40.0, "trend": "stable", "change_rate_per_hour": 0.0},
        pest_activity={"current": 10.0, "trend": "stable", "change_rate_per_hour": 0.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
    )
    codes = [f["code"] for f in rc.calculate_risk_factors(features)]
    assert "PROLONGED_LEAF_WETNESS" in codes  # 60 min >= 45 min threshold


def test_high_pest_activity_factor():
    features = _features()
    codes = [f["code"] for f in rc.calculate_risk_factors(features)]
    assert "HIGH_PEST_ACTIVITY" in codes
    assert "INCREASING_PEST_ACTIVITY" in codes


def test_recent_rainfall_factor():
    features = _features()
    codes = [f["code"] for f in rc.calculate_risk_factors(features)]
    assert "RECENT_RAINFALL" in codes


def test_low_soil_moisture_factor():
    features = _features(
        soil_moisture={"current": 10.0, "trend": "stable", "change_rate_per_hour": 0.0},
    )
    codes = [f["code"] for f in rc.calculate_risk_factors(features)]
    assert "LOW_SOIL_MOISTURE" in codes


def test_risk_factors_are_deterministic():
    features = _features()
    first = rc.calculate_risk_factors(features)
    second = rc.calculate_risk_factors(features)
    assert first == second
    score_again = rc.calculate_risk_score(features)
    assert score_again == rc.calculate_risk_score(features)


def test_missing_feature_values_are_safe():
    """Partial features still score in [0,100] and never crash."""
    features = {"humidity": {"current": 90.0, "trend": "increasing"}}
    score = rc.calculate_risk_score(features)
    assert 0 <= score <= 100
    factors = rc.calculate_risk_factors(features)
    assert all(f["code"] in rc.REASONS for f in factors)


# --- Camera trigger ---------------------------------------------------------


def test_camera_trigger_false_for_low_risk():
    features = _features(
        humidity={"current": 40.0, "trend": "stable", "change_rate_per_hour": 0.0},
        leaf_wetness={"current": 20.0, "trend": "stable", "change_rate_per_hour": 0.0,
                      "active_duration_minutes": 0},
        pest_activity={"current": 10.0, "trend": "stable", "change_rate_per_hour": 0.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
    )
    factors = rc.calculate_risk_factors(features)
    level = rc.calculate_risk_level(rc.calculate_risk_score(features))
    assert rc.should_trigger_camera(level, features, len(factors)) is False


def test_camera_trigger_true_for_high_level():
    assert rc.should_trigger_camera("HIGH", {}, 0) is True
    assert rc.should_trigger_camera("CRITICAL", {}, 0) is True


def test_camera_trigger_true_for_rate_spike():
    """MEDIUM level but humidity+pest rates sum >= spike threshold."""
    features = _features(
        humidity={"current": 82.0, "trend": "increasing", "change_rate_per_hour": 10.0},
        pest_activity={"current": 35.0, "trend": "increasing", "change_rate_per_hour": 10.0},
        rainfall={"total": 0.0, "latest": 0.0, "observation_count": 4},
        leaf_wetness={"current": 65.0, "trend": "stable", "change_rate_per_hour": 0.0,
                      "active_duration_minutes": 10},
    )
    factors = rc.calculate_risk_factors(features)
    score = rc.calculate_risk_score(features)
    level = rc.calculate_risk_level(score)
    assert level in ("MEDIUM", "HIGH")
    assert rc.should_trigger_camera(level, features, len(factors)) is True


# --- Risk trend (stored history) --------------------------------------------


def test_risk_trend_insufficient_without_history(db_session):
    from app.risk.service import calculate_risk_trend

    assert calculate_risk_trend(None, "HIGH") == "insufficient_data"


def test_risk_trend_directions(db_session):
    from app.risk.service import calculate_risk_trend

    assert calculate_risk_trend(0, "HIGH") == "increasing"      # LOW -> HIGH
    assert calculate_risk_trend(3, "LOW") == "decreasing"       # CRITICAL -> LOW
    assert calculate_risk_trend(1, "MEDIUM") == "stable"        # MEDIUM -> MEDIUM


# --- API tests ----------------------------------------------------------------


def _setup_zone(client) -> int:
    farm = client.post(
        "/farms", json={"name": "Farm 01", "location": "Maharashtra"}
    ).json()
    return client.post(f"/farms/{farm['id']}/zones", json={"name": "Zone A"}).json()["id"]


def _seed(client, zone_id: int, temps, humidity, pest, leaf, minutes_step=10):
    count = len(temps)
    for i in range(count):
        ts = BASE - timedelta(minutes=(count - 1 - i) * minutes_step)
        response = client.post(
            f"/zones/{zone_id}/sensor-readings",
            json={
                "timestamp": ts.isoformat(),
                "temperature": temps[i],
                "humidity": humidity[i],
                "rainfall": 1.0,
                "leaf_wetness": leaf[i],
                "soil_moisture": 55,
                "pest_activity": pest[i],
            },
        )
        assert response.status_code == 201


def test_api_risk_normal_conditions(client, db_session):
    zone_id = _setup_zone(client)
    _seed(client, zone_id,
          temps=[25, 25, 25, 25], humidity=[45, 45, 45, 45],
          pest=[5, 5, 5, 5], leaf=[10, 10, 10, 10])
    response = client.get(f"/zones/{zone_id}/risk")
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] == "LOW"
    assert body["camera_trigger"] is False
    assert body["risk_trend"] == "insufficient_data"  # first ever assessment
    assert 0 <= body["risk_score"] <= 100
    assert "generated_at" in body


def test_api_risk_high_conditions(client, db_session):
    zone_id = _setup_zone(client)
    # 15-minute steps -> 45 min of continuous wetness (meets the
    # PROLONGED_LEAF_WETNESS threshold of 45 minutes).
    _seed(client, zone_id,
          temps=[33, 34, 35, 36], humidity=[90, 92, 95, 96],
          pest=[60, 65, 70, 75], leaf=[90, 92, 95, 96], minutes_step=15)
    response = client.get(f"/zones/{zone_id}/risk")
    assert response.status_code == 200
    body = response.json()
    assert body["risk_level"] in ("HIGH", "CRITICAL")
    assert body["camera_trigger"] is True
    codes = [f["code"] for f in body["risk_factors"]]
    assert "HIGH_HUMIDITY" in codes
    assert "HIGH_PEST_ACTIVITY" in codes
    assert "PROLONGED_LEAF_WETNESS" in codes
    assert body["risk_score"] > 50


def test_api_risk_trend_increasing_between_calls(client, db_session):
    zone_id = _setup_zone(client)
    _seed(client, zone_id,
          temps=[25, 25, 25, 25], humidity=[45, 45, 45, 45],
          pest=[5, 5, 5, 5], leaf=[10, 10, 10, 10])
    first = client.get(f"/zones/{zone_id}/risk").json()
    assert first["risk_trend"] == "insufficient_data"

    # Add elevated readings now -> risk rises -> trend should be increasing.
    _seed(client, zone_id,
          temps=[35, 36, 36, 36], humidity=[94, 95, 96, 96],
          pest=[70, 75, 80, 85], leaf=[95, 96, 96, 96])
    second = client.get(f"/zones/{zone_id}/risk").json()
    assert second["risk_trend"] == "increasing"


def test_api_risk_trend_stable(client, db_session):
    zone_id = _setup_zone(client)
    _seed(client, zone_id,
          temps=[25, 25, 25, 25], humidity=[45, 45, 45, 45],
          pest=[5, 5, 5, 5], leaf=[10, 10, 10, 10])
    client.get(f"/zones/{zone_id}/risk")
    # Different timestamp, same conditions -> same level -> stable.
    _seed(client, zone_id,
          temps=[25, 25, 25, 25], humidity=[45, 45, 45, 45],
          pest=[5, 5, 5, 5], leaf=[10, 10, 10, 10], minutes_step=1)
    body = client.get(f"/zones/{zone_id}/risk").json()
    assert body["risk_trend"] == "stable"


def test_api_risk_nonexistent_zone(client):
    response = client.get("/zones/999/risk")
    assert response.status_code == 404
    assert response.json()["detail"] == "Zone not found"


def test_api_risk_no_data_insufficient(client, db_session):
    zone_id = _setup_zone(client)
    response = client.get(f"/zones/{zone_id}/risk")
    assert response.status_code == 200
    body = response.json()
    assert body["risk_score"] is None
    assert body["risk_level"] == "INSUFFICIENT_DATA"
    assert body["risk_trend"] == "insufficient_data"
    assert body["camera_trigger"] is False
    assert body["risk_factors"] == []


def test_api_risk_invalid_window_returns_400(client):
    response = client.get("/zones/1/risk?window=7d")
    assert response.status_code == 400


def test_api_risk_window_parameter(client, db_session):
    zone_id = _setup_zone(client)
    _seed(client, zone_id,
          temps=[30, 31, 32, 33], humidity=[85, 87, 89, 91],
          pest=[30, 40, 50, 60], leaf=[75, 80, 85, 90])
    for window in ("30m", "1h", "6h", "24h"):
        response = client.get(f"/zones/{zone_id}/risk?window={window}")
        assert response.status_code == 200
        assert response.json()["window"] == window
