"""Feature Engine service: raw sensor readings -> contextual features.

The Feature Engine answers "what is happening in this zone?" only.
It does NOT score risk, diagnose disease, or trigger cameras — those
belong to future modules (Risk Engine, AI Vision, etc.).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.features import calculations as calc
from app.models.sensor_reading import SensorReading

# Supported windows: label -> timedelta
SUPPORTED_WINDOWS: dict[str, timedelta] = {
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
}


def get_window_delta(window: str) -> Optional[timedelta]:
    """Return the timedelta for a supported window label, else None."""
    return SUPPORTED_WINDOWS.get(window)


def fetch_window_readings(
    db: Session, zone_id: int, window: str, *, now: Optional[datetime] = None
) -> list[SensorReading]:
    """Readings for a zone inside the window ending at `now`.

    Filters at the database level (zone_id + timestamp) so the whole
    sensor_readings table is never loaded. Ordered oldest -> newest.
    `now` defaults to the current UTC time; tests inject fixed times.
    """
    delta = get_window_delta(window)
    if delta is None:
        raise ValueError(f"Unsupported window: {window}")
    end = now or datetime.now(timezone.utc)
    start = end - delta
    return (
        db.query(SensorReading)
        .filter(
            SensorReading.zone_id == zone_id,
            SensorReading.timestamp >= start,
            SensorReading.timestamp <= end,
        )
        .order_by(SensorReading.timestamp.asc())
        .all()
    )


def _points(readings: list[SensorReading], attr: str) -> list[tuple[datetime, float]]:
    return [(r.timestamp, getattr(r, attr)) for r in readings]


def compute_features(readings: list[SensorReading]) -> dict:
    """Compute all feature blocks from in-window readings (oldest first)."""
    if not readings:
        return {}

    latest = readings[-1]
    features: dict = {}

    for name in ("temperature", "humidity", "soil_moisture", "pest_activity"):
        features[name] = calc.window_features(
            current=getattr(latest, name),
            values=[getattr(r, name) for r in readings],
            points=_points(readings, name),
        )

    features["leaf_wetness"] = {
        **calc.window_features(
            current=latest.leaf_wetness,
            values=[r.leaf_wetness for r in readings],
            points=_points(readings, "leaf_wetness"),
        ),
        "active_duration_minutes": calc.leaf_wetness_active_minutes(
            _points(readings, "leaf_wetness")
        ),
    }

    features["rainfall"] = {
        "total": sum(r.rainfall for r in readings),
        "latest": latest.rainfall,
        "observation_count": len(readings),
    }
    return features
