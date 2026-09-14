"""Pure calculation functions for the Feature Engine.

All functions are deterministic and side-effect free so they are easy to
test. They receive plain lists of (timestamp, value) pairs or numeric lists
and return Python floats/strings/None.

Trend method (documented for the API and README):
    1. Sort observations by timestamp.
    2. Split into an earlier half and a later half.
    3. Compare the average of each half.
    4. If later_avg - earlier_avg >= TREND_TOLERANCE -> "increasing"
       If earlier_avg - later_avg >= TREND_TOLERANCE -> "decreasing"
       Otherwise                                    -> "stable"
    5. Fewer than TREND_MIN_OBSERVATIONS observations -> "insufficient_data"

Rate-of-change method:
    change_rate_per_hour = (last_value - first_value) / elapsed_hours
    Returns None when elapsed time is zero or fewer than
    RATE_MIN_OBSERVATIONS observations exist.

Leaf-wetness duration method (conservative estimate):
    Sums the elapsed time between consecutive observations while BOTH
    consecutive values are at or above the active threshold. Assumes
    wetness persisted between two observations only when both readings
    were active (wetness between sparse samples is NOT extrapolated), so
    the estimate is conservative for sparse data.
"""

from datetime import datetime, timedelta
from statistics import fmean
from typing import Optional

# --- Configuration (overridable via environment variables) ---------------

import os

LEAF_WETNESS_ACTIVE_THRESHOLD = float(
    os.getenv("LEAF_WETNESS_ACTIVE_THRESHOLD", "60")
)
TREND_TOLERANCE = float(os.getenv("TREND_TOLERANCE", "2.0"))
TREND_MIN_OBSERVATIONS = 4
RATE_MIN_OBSERVATIONS = 2

TREND_INCREASING = "increasing"
TREND_DECREASING = "decreasing"
TREND_STABLE = "stable"
TREND_INSUFFICIENT = "insufficient_data"


def stats(values: list[float]) -> Optional[dict]:
    """Return current-context-free average/min/max, or None when empty."""
    if not values:
        return None
    return {"average": fmean(values), "minimum": min(values), "maximum": max(values)}


def trend(points: list[tuple[datetime, float]]) -> str:
    """Classify trend by comparing earlier-half vs later-half averages."""
    if len(points) < TREND_MIN_OBSERVATIONS:
        return TREND_INSUFFICIENT
    mid = len(points) // 2
    earlier_avg = fmean(v for _, v in points[:mid])
    later_avg = fmean(v for _, v in points[mid:])
    diff = later_avg - earlier_avg
    if diff >= TREND_TOLERANCE:
        return TREND_INCREASING
    if diff <= -TREND_TOLERANCE:
        return TREND_DECREASING
    return TREND_STABLE


def change_rate_per_hour(points: list[tuple[datetime, float]]) -> Optional[float]:
    """(last - first) / elapsed hours; None if elapsed time is zero."""
    if len(points) < RATE_MIN_OBSERVATIONS:
        return None
    (t0, v0), (_, v1) = points[0], points[-1]
    elapsed_hours = (points[-1][0] - t0).total_seconds() / 3600
    if elapsed_hours <= 0:
        return None
    return (v1 - v0) / elapsed_hours


def leaf_wetness_active_minutes(
    points: list[tuple[datetime, float]],
    threshold: float = LEAF_WETNESS_ACTIVE_THRESHOLD,
) -> int:
    """Estimated minutes leaf wetness stayed at/above threshold.

    Conservative: only intervals where both endpoints are active count.
    """
    if len(points) < 2:
        return 0
    minutes = 0.0
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if v0 >= threshold and v1 >= threshold:
            minutes += (t1 - t0).total_seconds() / 60
    return round(minutes)


def window_features(
    current: Optional[float],
    values: list[float],
    points: list[tuple[datetime, float]],
    include_trend: bool = True,
) -> dict:
    """Assemble stats/trend/rate for one metric."""
    if current is None:
        return {}
    base = {
        "current": current,
        "average": fmean(values),
        "minimum": min(values),
        "maximum": max(values),
    }
    if include_trend:
        base["trend"] = trend(points)
        base["change_rate_per_hour"] = change_rate_per_hour(points)
    return base
