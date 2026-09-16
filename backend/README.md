# Midori — Crop Health Intelligence Platform

SIH 2026 project for problem statement **SIH26131 — Early detection and management of crop diseases and pest infestations**.

A completely software-based prototype: sensor data is generated through a Digital Farm Simulator, and camera events/images are simulated or replayed. No physical IoT hardware is required for the MVP.

**Current stage:** Step 6 — Camera/Image Intake + Image Quality (images prepared and validated for future AI analysis; no diagnosis yet).

## Tech Stack

- Python 3, FastAPI, Uvicorn, Pydantic
- PostgreSQL + SQLAlchemy + psycopg2
- python-dotenv for configuration
- Pytest (testing)

## PostgreSQL Setup

1. Install PostgreSQL (https://www.postgresql.org/download/).
2. Create the database (e.g. via pgAdmin or psql):

   ```sql
   CREATE DATABASE midori;
   ```

   Optionally create a separate test database too:

   ```sql
   CREATE DATABASE midori_test;
   ```

3. Copy `.env.example` to `.env` and configure it:

   ```env
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/midori
   # Optional, used by tests; falls back to in-memory SQLite if unset:
   TEST_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/midori_test
   ```

   `.env` is git-ignored. Never commit real credentials.

4. Activate the virtual environment:

   ```bash
   python -m venv venv        # first time only
   venv\Scripts\activate      # Windows   (source venv/bin/activate on Linux/macOS)
   ```

5. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Run the application (tables are created automatically on startup):

   ```bash
   uvicorn app.main:app --reload
   ```

7. Open the Swagger docs: http://127.0.0.1:8000/docs

## Tests

Tests run against an isolated database (`TEST_DATABASE_URL`, or in-memory SQLite by default) — your real database is never touched.

```bash
pytest
```

## Data Model: Farm → Zone → Crop

```
Farm (farms)
 └── Zone (zones)      — a farm has many zones
      └── Crop (crops) — one active crop record per zone
```

- **Farm**: `id`, `name` (required), `location` (required), `area_acres` (optional), `created_at`
- **Zone**: `id`, `farm_id` (FK → farms, cascade delete), `name` (required), `created_at`
- **Crop**: `id`, `zone_id` (FK → zones, unique, cascade delete), `crop_name` (required), `crop_stage` (optional), `sowing_date` (optional), `created_at`

## API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Backend running message |
| GET | `/health` | Health check |
| POST | `/farms` | Create a farm |
| GET | `/farms` | List all farms |
| GET | `/farms/{farm_id}` | Get one farm (404 if missing) |
| POST | `/farms/{farm_id}/zones` | Create a zone in a farm |
| GET | `/farms/{farm_id}/zones` | List zones of a farm |
| GET | `/zones/{zone_id}` | Get one zone (404 if missing) |
| POST | `/zones/{zone_id}/crop` | Assign crop to a zone (400 if one exists) |
| GET | `/zones/{zone_id}/crop` | Get the zone's crop (404 if none) |
| POST | `/zones/{zone_id}/sensor-readings` | Record a sensor observation for a zone |
| GET | `/zones/{zone_id}/sensor-readings` | List a zone's readings, newest first (`?limit=1..500`, default 50) |
| GET | `/zones/{zone_id}/sensor-readings/latest` | Most recent reading for a zone |
| GET | `/zones/{zone_id}/features?window=1h` | Monitoring features for a zone over a time window |

Example flow:

```bash
curl -X POST http://127.0.0.1:8000/farms -H "Content-Type: application/json" \
  -d '{"name": "Farm 01", "location": "Maharashtra", "area_acres": 5.0}'

curl -X POST http://127.0.0.1:8000/farms/1/zones -H "Content-Type: application/json" \
  -d '{"name": "Zone A"}'

curl -X POST http://127.0.0.1:8000/zones/1/crop -H "Content-Type: application/json" \
  -d '{"crop_name": "Tomato", "crop_stage": "Vegetative", "sowing_date": "2026-08-01"}'

curl http://127.0.0.1:8000/zones/1/crop
```

## Step 3 — Sensor Data API (simulated)

Sensor data is currently **simulated**: there are no physical sensors in this
software-only SIH MVP. A Digital Farm Simulator (later step) will POST
observations to the API:

```
Digital Farm Simulator
        ↓
POST /zones/{zone_id}/sensor-readings
        ↓
Validation → PostgreSQL
```

Example request:

```json
{
    "timestamp": "2026-09-15T10:00:00+05:30",
    "temperature": 29.4,
    "humidity": 86,
    "rainfall": 12.5,
    "leaf_wetness": 78,
    "soil_moisture": 64,
    "pest_activity": 7
}
```

Example response (HTTP 201):

```json
{
    "id": 1,
    "zone_id": 1,
    "timestamp": "2026-09-15T10:00:00+05:30",
    "temperature": 29.4,
    "humidity": 86.0,
    "rainfall": 12.5,
    "leaf_wetness": 78.0,
    "soil_moisture": 64.0,
    "pest_activity": 7.0,
    "created_at": "2026-09-15T04:28:27.431390+05:30"
}
```

Field reference (all values are **software-generated observations**, not hardware readings):

| Field | Unit / scale | Valid range |
| --- | --- | --- |
| `timestamp` | ISO 8601 datetime (timezone-aware, e.g. `+05:30`) | required |
| `temperature` | Celsius | -50 to 70 |
| `humidity` | Relative humidity % | 0 to 100 |
| `rainfall` | mm for the observation period | ≥ 0 |
| `leaf_wetness` | MVP normalized scale | 0 to 100 |
| `soil_moisture` | MVP normalized scale | 0 to 100 |
| `pest_activity` | MVP pest activity index | 0 to 100 |

Invalid values return HTTP 422 validation errors; nonexistent zones return 404.

## Step 4 — Feature Engine

```
Raw sensor readings
      ↓
Feature Engine (app/features/)
      ↓
Derived crop-health context features
      ↓
Future Risk Engine
```

**The Feature Engine does not diagnose diseases or calculate risk. It prepares contextual features for the Risk Engine.**

### Endpoint

`GET /zones/{zone_id}/features?window=1h` — supported windows: `30m`, `1h`, `6h`, `24h`.

- Zone missing → 404 `Zone not found`
- No readings inside the window → 404 `Insufficient sensor data for the requested window`
- Unsupported window → 422 with the list of supported windows

### Calculated features

Per metric (temperature, humidity, leaf_wetness, soil_moisture, pest_activity):
`current` (latest reading **inside the window**), `average`, `minimum`, `maximum`, `trend`, `change_rate_per_hour`.

- **Rainfall**: `total` (interval rainfall summed over the window), `latest`, `observation_count`.
- **Leaf wetness extra**: `active_duration_minutes` — estimated minutes at/above
  `LEAF_WETNESS_ACTIVE_THRESHOLD` (env var, default 60). Conservative estimate:
  only intervals where **both** consecutive readings are active count; no
  extrapolation between sparse samples, so estimates are approximate for sparse data.

### Trend methodology (deterministic)

1. Sort in-window observations by timestamp.
2. Split into earlier half and later half; compare the averages.
3. `later - earlier >= TREND_TOLERANCE` (env var, default 2.0) → `increasing`;
   `<= -TREND_TOLERANCE` → `decreasing`; otherwise `stable`.
4. Fewer than 4 observations → `insufficient_data`.

### Rate-of-change methodology

`(last_value - first_value) / elapsed_hours` over the window. Returns `null`
when elapsed time is zero or fewer than 2 observations exist.

### Example response (abbreviated)

```json
{
  "zone_id": 1, "window": "1h", "observation_count": 4,
  "features": {
    "temperature": {"current": 31.0, "average": 29.5, "minimum": 28.0, "maximum": 31.0,
                     "trend": "increasing", "change_rate_per_hour": 6.0},
    "humidity":    {"current": 89.0, "average": 84.5, "minimum": 80.0, "maximum": 89.0,
                     "trend": "increasing", "change_rate_per_hour": 18.0},
    "leaf_wetness": {"...": "...", "active_duration_minutes": 30},
    "rainfall": {"total": 6.0, "latest": 1.5, "observation_count": 4}
  }
}
```

## Step 5 — Risk Engine

The Feature Engine answers **"what is happening?"** in a zone. The Risk Engine answers **"how risky are the current conditions?"** by consuming the Feature Engine output — it never touches raw sensor readings and never diagnoses disease.

> **Scientific limitation:** This MVP risk score is an explainable environmental risk indicator and is **not a disease diagnosis or scientifically validated disease probability**. Weights and thresholds are initial values intended to be tuned after agricultural validation.

### Endpoint

```
GET /zones/{zone_id}/risk?window=1h     # window: 30m | 1h (default) | 6h | 24h
```

The pipeline:

```
Sensor Readings → Feature Engine → Risk Engine → risk score / level / factors / camera_trigger
```

### Risk score

A deterministic **environmental crop-health risk score (0–100)** computed from configurable factor scores (`RISK_FACTOR_THRESHOLDS` in `app/risk/calculations.py`) and weights (`RISK_WEIGHTS`): humidity, leaf wetness (value + active duration), temperature, recent rainfall, soil moisture, pest activity (value + trend), and a combination bonus when many factors coincide.

### Risk levels (configurable)

| Score | Level |
|-------|-------|
| 0–24 | LOW |
| 25–49 | MEDIUM |
| 50–74 | HIGH |
| 75–100 | CRITICAL |

### Explainable factors

Each assessment returns deterministic reason codes with fixed explanation text: `HIGH_HUMIDITY`, `INCREASING_HUMIDITY`, `ELEVATED_LEAF_WETNESS`, `PROLONGED_LEAF_WETNESS`, `HIGH_PEST_ACTIVITY`, `INCREASING_PEST_ACTIVITY`, `RECENT_RAINFALL`, `LOW_SOIL_MOISTURE`, `ELEVATED_TEMPERATURE`, `MULTIPLE_FACTORS`.

### Risk trend

Every assessment is stored in the `risk_assessments` table. The trend compares the current level with the previous stored assessment for the same zone/window: `increasing`, `decreasing`, `stable`, or `insufficient_data` (first-ever assessment).

### Camera trigger

`camera_trigger: true` (a software decision only — no image is captured) when:
- risk level is HIGH or CRITICAL, **or**
- humidity + pest-activity rates of change spike (sum ≥ configurable threshold), **or**
- many significant factors coincide.

The future Camera/Image Intake module will consume this decision.

### Insufficient data

If the zone has no sensor data in the window, the API returns HTTP 200 with `risk_score: null`, `risk_level: "INSUFFICIENT_DATA"`, `camera_trigger: false` — no fake score is invented. Nonexistent zone → 404; invalid window → 400.

### Example response (verified live)

```json
{
  "zone_id": 2,
  "window": "1h",
  "risk_score": 76.0,
  "risk_level": "CRITICAL",
  "risk_trend": "insufficient_data",
  "camera_trigger": true,
  "risk_factors": [
    {"code": "HIGH_HUMIDITY", "observation": "96%", "effect": "increases_risk",
     "reason": "High humidity can create favorable conditions for some crop diseases."},
    {"code": "PROLONGED_LEAF_WETNESS", "observation": "45 minutes", "effect": "increases_risk",
     "reason": "Leaf wetness has remained elevated for a prolonged period."},
    {"code": "MULTIPLE_FACTORS", "observation": "7 factors", "effect": "increases_risk",
     "reason": "Multiple environmental risk factors are present at the same time."}
  ],
  "generated_at": "2026-09-15T05:47:35.280266Z"
}
```\n
## Step 6 — Camera/Image Intake + Image Quality

**Step 6 prepares and validates images for future AI analysis. It does not perform disease or pest diagnosis.**

The Risk Engine's `camera_trigger` decision (Step 5) flows here: when visual inspection is warranted, an image is received, quality-checked and marked ready for the future AI Vision step.

```
Risk Engine (camera_trigger=true)
      ↓
POST /zones/{zone_id}/images
      ↓
validation + quality checks
      ↓
READY_FOR_AI  →  [Step 7 — AI Vision]
```

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/zones/{zone_id}/images` | Upload an image (multipart/form-data) |
| GET | `/zones/{zone_id}/images?limit=50` | List image metadata for a zone (1–500) |
| GET | `/images/{image_id}` | Get metadata for one image |

### Supported formats & limits (configurable)

- Formats: JPEG/JPG, PNG, WEBP — actual decoding is verified with Pillow, not just the file extension
- Max file size: 10 MB (`IMAGE_MAX_FILE_SIZE`)
- Minimum resolution: 200×200 (`IMAGE_MIN_WIDTH` / `IMAGE_MIN_HEIGHT`)
- Source field: `uploaded` (default), `simulated_camera`, `replayed`

### Storage

Files are stored on the local filesystem (metadata in PostgreSQL):

```
storage/images/zone_1/<uuid>.jpg
storage/images/zone_2/<uuid>.png
```

Storage names are generated UUIDs — the client filename is never trusted (path-traversal safe, no overwrites).

### Quality checks (`app/images/quality.py`)

- **Resolution** — below minimum → LOW_QUALITY with reason
- **Blur** — Laplacian variance of the grayscale image (higher = sharper); threshold `IMAGE_BLUR_THRESHOLD` (default 60)
- **Brightness** — mean grayscale intensity 0–255; too dark < 50, too bright > 215 (configurable)

### Quality statuses

| Status | Meaning |
|---|---|
| `READY_FOR_AI` | Accepted — suitable for later AI analysis |
| `LOW_QUALITY` | Valid image but poor resolution/blur/exposure |
| `REJECTED` | Invalid/corrupted/unsupported/oversized (HTTP 400) |

Quality assessment is about image suitability only — it never labels an image "diseased" or "healthy".

### Example response (verified live)

```json
{
  "id": 1,
  "zone_id": 2,
  "filename": "live_test_crop.jpg",
  "content_type": "image/jpeg",
  "file_size": 183075,
  "width": 640,
  "height": 480,
  "quality_status": "READY_FOR_AI",
  "source": "simulated_camera",
  "quality": {
    "blur_score": 134805.27,
    "blur_status": "acceptable",
    "brightness_score": 127.35,
    "brightness_status": "acceptable"
  },
  "reasons": [],
  "created_at": "..."
}
```

### Security

- MIME type validated and image actually decoded before acceptance
- Corrupted/undecodable files rejected (HTTP 400)
- Client filenames sanitized; storage names are UUIDs
- Path traversal prevented; arbitrary filesystem paths never exposed
- Max file size enforced

## Project Structure (Step 6)

```
backend/
├── app/
│   ├── api/         # FastAPI routers (farms, zones, crops, sensor_readings, features, risk)
│   ├── models/      # SQLAlchemy ORM models (incl. risk_assessment)
│   ├── schemas/     # Pydantic request/response schemas (incl. risk)
│   ├── features/    # Feature Engine (calculations + service)
│   ├── risk/        # Risk Engine (calculations + service)
│   ├── images/      # Image intake (quality + storage + service)
│   ├── database.py  # Engine, SessionLocal, Base, get_db dependency
│   └── main.py      # FastAPI application
├── tests/
├── .env.example
└── requirements.txt
```

## AI Vision — Future Step (intentionally postponed)

Step 7 (AI Vision) is **intentionally not implemented** in this development cycle.
The Image Intake module prepares images and marks passing images `READY_FOR_AI` —
which means *ready for future AI analysis*, **not** analyzed. No disease diagnosis,
AI confidence, or severity is produced by the current system. See
[docs/AI_BOUNDARY.md](docs/AI_BOUNDARY.md).

## Documentation

Full engineering documentation lives in [`docs/`](docs/):

- [PROJECT_AUDIT.md](docs/PROJECT_AUDIT.md) — module-by-module audit of what exists
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — system pipeline, layering, data-flow guarantees
- [COMPLETED_FEATURES.md](docs/COMPLETED_FEATURES.md) — what/why/how per step (1–6)
- [DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md) — tables, relationships, rules
- [API_REFERENCE.md](docs/API_REFERENCE.md) — every endpoint with inputs/errors/examples
- [TEST_REPORT.md](docs/TEST_REPORT.md) — 103/103 passing + live verification
- [SECURITY.md](docs/SECURITY.md) — secrets, upload hardening, known gaps
- [DEVELOPER_RUNBOOK.md](docs/DEVELOPER_RUNBOOK.md) — setup, run, test, troubleshoot
- [AI_BOUNDARY.md](docs/AI_BOUNDARY.md) — the AI boundary and design commitments

## Roadmap

Future modules (not yet implemented): Digital Farm Simulator → Data Gateway → Validation → Targeted Camera Event → AI Vision (next major stage) → Confidence Gate → Expert Validation → Advisory → Alerts → Follow-up → GIS / Frontend.
