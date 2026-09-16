"""Risk Engine configuration and pure calculation functions.

All thresholds and weights live here in one place. Initial values are
simple MVP choices, documented and easy to tune after agricultural
validation — they are NOT scientifically validated.

Design notes
------------
- Every function is deterministic: the same Feature Engine input always
  produces the same risk output.
- Scores are contributions in [0, 100] per factor, combined as a weighted
  average so the total also stays in [0, 100].
- Missing feature values contribute 0 to the score but are reported via
  the returned factor metadata so callers stay explainable.
"""

import os
from typing import Any, Optional

# --- Configuration (env-overridable, one location) -----------------------

RISK_WEIGHTS: dict[str, float] = {
    "humidity": float(os.getenv("RISK_WEIGHT_HUMIDITY", "0.20")),
    "leaf_wetness": float(os.getenv("RISK_WEIGHT_LEAF_WETNESS", "0.20")),
    "leaf_wetness_duration": float(os.getenv("RISK_WEIGHT_LW_DURATION", "0.15")),
    "temperature": float(os.getenv("RISK_WEIGHT_TEMPERATURE", "0.10")),
    "rainfall": float(os.getenv("RISK_WEIGHT_RAINFALL", "0.10")),
    "soil_moisture": float(os.getenv("RISK_WEIGHT_SOIL_MOISTURE", "0.10")),
    "pest_activity": float(os.getenv("RISK_WEIGHT_PEST_ACTIVITY", "0.15")),
}

# Level cut-offs on the 0-100 score (inclusive upper bounds).
RISK_THRESHOLDS: dict[str, float] = {
    "low": float(os.getenv("RISK_THRESHOLD_LOW", "24")),
    "medium": float(os.getenv("RISK_THRESHOLD_MEDIUM", "49")),
    "high": float(os.getenv("RISK_THRESHOLD_HIGH", "74")),
}

# Per-factor sub-thresholds (MVP heuristics, 0-100 scales).
RISK_FACTOR_THRESHOLDS: dict[str, float] = {
    "humidity_high": 80.0,          # % RH
    "leaf_wetness_high": 70.0,      # 0-100 index
    "leaf_wetness_duration_minutes": 45.0,
    "temperature_optimum_low": 15.0,   # C
    "temperature_optimum_high": 35.0,  # C
    "rainfall_recent_mm": 5.0,         # mm total in window
    "soil_moisture_low": 30.0,         # 0-100
    "soil_moisture_high": 90.0,        # 0-100
    "pest_activity_high": 40.0,        # 0-100
}

# Camera trigger tuning.
CAMERA_TRIGGER_MIN_LEVEL = "HIGH"          # LOW|MEDIUM|HIGH|CRITICAL
CAMERA_TRIGGER_RATE_SPIKE = 15.0           # pp/h across humidity+pest rates
CAMERA_TRIGGER_MIN_FACTORS = 3             # significant increasing-risk factors

LEVELS = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


# --- Pure calculations ----------------------------------------------------


def calculate_risk_level(score: Optional[float]) -> str:
    """Map a 0-100 score to LOW/MEDIUM/HIGH/CRITICAL via RISK_THRESHOLDS."""
    if score is None:
        return "INSUFFICIENT_DATA"
    if score <= RISK_THRESHOLDS["low"]:
        return "LOW"
    if score <= RISK_THRESHOLDS["medium"]:
        return "MEDIUM"
    if score <= RISK_THRESHOLDS["high"]:
        return "HIGH"
    return "CRITICAL"


def _linear_band(value: float, low: float, high: float) -> float:
    """0 below `low`, 1 above `high`, linear in between (clamped)."""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def humidity_score(features: dict[str, Any]) -> Optional[float]:
    """Rises from threshold-10 to threshold+10; capped at 100."""
    current = (features.get("humidity") or {}).get("current")
    if current is None:
        return None
    t = RISK_FACTOR_THRESHOLDS["humidity_high"]
    return min(100.0, _linear_band(current, t - 10, t + 10) * 100.0)


def leaf_wetness_score(features: dict[str, Any]) -> Optional[float]:
    current = (features.get("leaf_wetness") or {}).get("current")
    if current is None:
        return None
    t = RISK_FACTOR_THRESHOLDS["leaf_wetness_high"]
    return min(100.0, _linear_band(current, t - 10, t + 10) * 100.0)


def leaf_wetness_duration_score(features: dict[str, Any]) -> Optional[float]:
    minutes = (features.get("leaf_wetness") or {}).get("active_duration_minutes")
    if minutes is None:
        return None
    t = RISK_FACTOR_THRESHOLDS["leaf_wetness_duration_minutes"]
    return min(100.0, (minutes / t) * 100.0)


def temperature_score(features: dict[str, Any]) -> Optional[float]:
    """Warmth stress: peaks (100) at the optimum-high bound; cold contributes 0.

    MVP heuristic: risk grows with warmth inside/beyond the optimum band.
    """
    current = (features.get("temperature") or {}).get("current")
    if current is None:
        return None
    lo = RISK_FACTOR_THRESHOLDS["temperature_optimum_low"]
    hi = RISK_FACTOR_THRESHOLDS["temperature_optimum_high"]
    if current < lo:
        return 0.0
    # Linear ramp from optimum-high to hi+10 reaching 100, capped beyond.
    return min(100.0, _linear_band(current, hi, hi + 10) * 100.0)


def rainfall_score(features: dict[str, Any]) -> Optional[float]:
    total = (features.get("rainfall") or {}).get("total")
    if total is None:
        return None
    t = RISK_FACTOR_THRESHOLDS["rainfall_recent_mm"]
    return min(100.0, (total / t) * 100.0)


def soil_moisture_score(features: dict[str, Any]) -> Optional[float]:
    """Risk when moisture leaves the healthy band (too dry or too wet)."""
    current = (features.get("soil_moisture") or {}).get("current")
    if current is None:
        return None
    lo = RISK_FACTOR_THRESHOLDS["soil_moisture_low"]
    hi = RISK_FACTOR_THRESHOLDS["soil_moisture_high"]
    dry = _linear_band(lo - current, 0, 20) if current < lo else 0.0
    wet = _linear_band(current - hi, 0, 10) if current > hi else 0.0
    return min(100.0, max(dry, wet) * 100.0)


def pest_activity_score(features: dict[str, Any]) -> Optional[float]:
    current = (features.get("pest_activity") or {}).get("current")
    if current is None:
        return None
    t = RISK_FACTOR_THRESHOLDS["pest_activity_high"]
    return min(100.0, (current / t) * 100.0 if current <= t else 100.0)


FACTOR_SCORERS = {
    "humidity": humidity_score,
    "leaf_wetness": leaf_wetness_score,
    "leaf_wetness_duration": leaf_wetness_duration_score,
    "temperature": temperature_score,
    "rainfall": rainfall_score,
    "soil_moisture": soil_moisture_score,
    "pest_activity": pest_activity_score,
}


def calculate_risk_score(features: dict[str, Any]) -> Optional[float]:
    """Weighted average of per-factor scores -> 0-100 (or None if no data).

    Missing factors are skipped and their weight is redistributed, so a
    partially-available feature set still yields a score in [0, 100].
    """
    if not features:
        return None
    weighted_sum = 0.0
    used_weight = 0.0
    for name, scorer in FACTOR_SCORERS.items():
        value = scorer(features)
        if value is None:
            continue
        weighted_sum += value * RISK_WEIGHTS[name]
        used_weight += RISK_WEIGHTS[name]
    if used_weight == 0.0:
        return None
    return round(min(100.0, max(0.0, weighted_sum / used_weight)), 1)


# --- Deterministic risk factors (reason codes) ----------------------------

REASONS: dict[str, str] = {
    "HIGH_HUMIDITY": "High humidity can create favorable conditions for some crop diseases.",
    "PROLONGED_LEAF_WETNESS": "Leaf wetness has remained elevated for a prolonged period.",
    "INCREASING_HUMIDITY": "Humidity is increasing during the selected window.",
    "HIGH_PEST_ACTIVITY": "Pest activity is elevated for this zone.",
    "INCREASING_PEST_ACTIVITY": "Pest activity is increasing during the selected window.",
    "RECENT_RAINFALL": "Recent rainfall within the selected window.",
    "LOW_SOIL_MOISTURE": "Soil moisture is below the healthy range.",
    "HIGH_SOIL_MOISTURE": "Soil moisture is above the healthy range.",
    "ELEVATED_LEAF_WETNESS": "Leaf wetness is elevated.",
    "ELEVATED_TEMPERATURE": "Temperature is above the optimum range for the crop.",
    "MULTIPLE_FACTORS": "Multiple environmental risk factors are present at the same time.",
}


def _factor(code: str, observation: str) -> dict[str, str]:
    return {
        "code": code,
        "observation": observation,
        "effect": "increases_risk",
        "reason": REASONS[code],
    }


def calculate_risk_factors(features: dict[str, Any]) -> list[dict[str, str]]:
    """Deterministic list of increasing-risk factor explanations."""
    factors: list[dict[str, str]] = []

    humidity = features.get("humidity") or {}
    if humidity.get("current") is not None and humidity["current"] >= RISK_FACTOR_THRESHOLDS["humidity_high"]:
        factors.append(_factor("HIGH_HUMIDITY", f"{humidity['current']:g}%"))
    if humidity.get("trend") == "increasing":
        factors.append(_factor("INCREASING_HUMIDITY", "Increasing"))

    leaf = features.get("leaf_wetness") or {}
    if leaf.get("current") is not None and leaf["current"] >= RISK_FACTOR_THRESHOLDS["leaf_wetness_high"]:
        factors.append(_factor("ELEVATED_LEAF_WETNESS", f"{leaf['current']:g}"))
    minutes = leaf.get("active_duration_minutes")
    if minutes is not None and minutes >= RISK_FACTOR_THRESHOLDS["leaf_wetness_duration_minutes"]:
        factors.append(_factor("PROLONGED_LEAF_WETNESS", f"{minutes} minutes"))

    pest = features.get("pest_activity") or {}
    if pest.get("current") is not None and pest["current"] >= RISK_FACTOR_THRESHOLDS["pest_activity_high"]:
        factors.append(_factor("HIGH_PEST_ACTIVITY", f"{pest['current']:g}"))
    if pest.get("trend") == "increasing":
        factors.append(_factor("INCREASING_PEST_ACTIVITY", "Increasing"))

    rainfall_total = (features.get("rainfall") or {}).get("total")
    if rainfall_total is not None and rainfall_total >= RISK_FACTOR_THRESHOLDS["rainfall_recent_mm"]:
        factors.append(_factor("RECENT_RAINFALL", f"{rainfall_total:g} mm"))

    soil = features.get("soil_moisture") or {}
    if soil.get("current") is not None:
        if soil["current"] < RISK_FACTOR_THRESHOLDS["soil_moisture_low"]:
            factors.append(_factor("LOW_SOIL_MOISTURE", f"{soil['current']:g}%"))
        elif soil["current"] > RISK_FACTOR_THRESHOLDS["soil_moisture_high"]:
            factors.append(_factor("HIGH_SOIL_MOISTURE", f"{soil['current']:g}%"))

    temperature = features.get("temperature") or {}
    if temperature.get("current") is not None and temperature["current"] > RISK_FACTOR_THRESHOLDS["temperature_optimum_high"]:
        factors.append(_factor("ELEVATED_TEMPERATURE", f"{temperature['current']:g}C"))

    if len(factors) >= CAMERA_TRIGGER_MIN_FACTORS:
        factors.append(_factor("MULTIPLE_FACTORS", f"{len(factors)} factors"))

    return factors


# --- Camera trigger decision ---------------------------------------------


def should_trigger_camera(
    risk_level: str,
    features: dict[str, Any],
    factor_count: int,
) -> bool:
    """Software-only decision for the future Camera/Image Intake module.

    True when any of:
    - risk level HIGH or CRITICAL
    - humidity+pest rates spike (sum >= CAMERA_TRIGGER_RATE_SPIKE pp/h)
    - significant risk factors >= CAMERA_TRIGGER_MIN_FACTORS
    """
    if risk_level in ("HIGH", "CRITICAL"):
        return True

    humidity_rate = (features.get("humidity") or {}).get("change_rate_per_hour") or 0.0
    pest_rate = (features.get("pest_activity") or {}).get("change_rate_per_hour") or 0.0
    if humidity_rate + pest_rate >= CAMERA_TRIGGER_RATE_SPIKE:
        return True

    return factor_count >= CAMERA_TRIGGER_MIN_FACTORS
