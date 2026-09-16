# API Reference — Steps 1–6

Base URL (local dev): `http://127.0.0.1:8000` · Interactive docs: `/docs` (Swagger), `/redoc`.

Conventions: all errors return `{"detail": "..."}`; validation errors use FastAPI 422;
raw database errors are never exposed.

## System

| Method | Path | Purpose | Errors |
|---|---|---|---|
| GET | `/` | Confirm backend is running | — |
| GET | `/health` | Health check (`{"status":"ok"}`) | — |

## Farms

| Method | Path | Purpose | Input | Errors |
|---|---|---|---|---|
| POST | `/farms` | Create a farm | `{name, location, area_acres?}` | 422 invalid |
| GET | `/farms` | List farms | — | — |
| GET | `/farms/{farm_id}` | Get one farm | — | 404 |

## Zones

| Method | Path | Purpose | Input | Errors |
|---|---|---|---|---|
| POST | `/farms/{farm_id}/zones` | Create zone in a farm | `{name}` | 404 farm, 422 |
| GET | `/farms/{farm_id}/zones` | List zones of a farm | — | 404 farm |
| GET | `/zones/{zone_id}` | Get one zone | — | 404 |

## Crop

| Method | Path | Purpose | Input | Errors |
|---|---|---|---|---|
| POST | `/zones/{zone_id}/crop` | Assign crop to zone | `{crop_name, crop_stage?, sowing_date?}` | 404 zone, 422 |
| GET | `/zones/{zone_id}/crop` | Get zone's crop | — | 404 zone / no crop |

## Sensor readings (simulated data — no hardware)

| Method | Path | Purpose | Input | Errors |
|---|---|---|---|---|
| POST | `/zones/{zone_id}/sensor-readings` | Store one observation | `{timestamp (ISO, tz-aware), temperature (-50..70), humidity (0..100), rainfall (>=0), leaf_wetness (0..100), soil_moisture (0..100), pest_activity (0..100)}` | 404 zone, 422 range |
| GET | `/zones/{zone_id}/sensor-readings?limit=50` | List readings, newest first (limit 1–500) | — | 404 zone |
| GET | `/zones/{zone_id}/sensor-readings/latest` | Most recent reading | — | 404 zone / no readings |

### Example

```json
POST /zones/1/sensor-readings
{"timestamp":"2026-09-15T10:00:00+05:30","temperature":29.4,"humidity":86,
 "rainfall":12.5,"leaf_wetness":78,"soil_moisture":64,"pest_activity":7}
```

## Feature Engine

| Method | Path | Purpose | Errors |
|---|---|---|---|
| GET | `/zones/{zone_id}/features?window=1h` | Statistical + trend features for a window | 404 zone; 404 "Insufficient sensor data for the requested window"; 400 invalid window |

Windows: `30m`, `1h`, `6h`, `24h`.

Response (abbreviated): per-metric `current/average/minimum/maximum/trend/change_rate_per_hour`
(trend: `increasing|decreasing|stable|insufficient_data`), `rainfall.total/latest/observation_count`,
`leaf_wetness.active_duration_minutes`. Missing data → `null`, never zero-filled.

## Risk Engine

| Method | Path | Purpose | Errors |
|---|---|---|---|
| GET | `/zones/{zone_id}/risk?window=1h` | Explainable environmental risk assessment | 404 zone; 400 invalid window |

Response fields: `zone_id`, `window`, `risk_score` (0–100 or `null`),
`risk_level` (`LOW|MEDIUM|HIGH|CRITICAL|INSUFFICIENT_DATA`), `risk_trend`
(`increasing|decreasing|stable|insufficient_data`), `camera_trigger` (bool),
`risk_factors[]` (`{code, observation, effect, reason}`), `generated_at`.

Reason codes: `HIGH_HUMIDITY`, `INCREASING_HUMIDITY`, `ELEVATED_LEAF_WETNESS`,
`PROLONGED_LEAF_WETNESS`, `HIGH_PEST_ACTIVITY`, `INCREASING_PEST_ACTIVITY`,
`RECENT_RAINFALL`, `LOW_SOIL_MOISTURE`, `ELEVATED_TEMPERATURE`, `MULTIPLE_FACTORS`.

**This score is an environmental crop-health indicator, not a disease diagnosis or
scientifically validated disease probability.**

## Images (intake + quality)

| Method | Path | Purpose | Input | Errors |
|---|---|---|---|---|
| POST | `/zones/{zone_id}/images` | Upload, validate, store, quality-check | multipart `file` + optional `source` form field (`uploaded`\|`simulated_camera`\|`replayed`) | 404 zone; 400 invalid type/empty/corrupted/oversized/invalid source |
| GET | `/zones/{zone_id}/images?limit=50` | List zone image metadata, newest first | — | 404 zone |
| GET | `/images/{image_id}` | Get one image's metadata | — | 404 |

Response: `id, zone_id, filename, stored_filename, content_type, file_size, width,
height, image_hash, source, quality_status, blur_score, brightness_score, quality
{blur_score, blur_status, brightness_score, brightness_status}, reasons[], created_at`.

`quality_status`: `READY_FOR_AI` (accepted) · `LOW_QUALITY` (valid but blurry /
dark / bright / low-resolution, with reasons) · `REJECTED`. Limits: JPEG/JPG/PNG/WEBP,
max 10 MB, min 200×200 — all env-configurable.

**Quality checks judge suitability for AI analysis only — never disease or health.**
No endpoint returns raw image bytes or filesystem paths.

## Verified smoke test (2026-09-16)

Full chain executed live: create farm → zone → crop → 4 sensor readings →
`/features` (obs 4, humidity/pest trends increasing) → `/risk` (HIGH,
`camera_trigger: true`, 4 reason codes) → image upload → metadata + list →
correct statuses. See [TEST_REPORT.md](TEST_REPORT.md).
