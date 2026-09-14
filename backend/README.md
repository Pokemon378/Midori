# Midori — Crop Health Intelligence Platform

SIH 2026 project for problem statement **SIH26131 — Early detection and management of crop diseases and pest infestations**.

A completely software-based prototype: sensor data is generated through a Digital Farm Simulator, and camera events/images are simulated or replayed. No physical IoT hardware is required for the MVP.

**Current stage:** Step 4 — Feature Engine (contextual monitoring features per zone; no risk scoring yet).

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

## Project Structure (Step 4)

```
backend/
├── app/
│   ├── api/         # FastAPI routers (farms, zones, crops)
│   ├── models/      # SQLAlchemy ORM models
│   ├── schemas/     # Pydantic request/response schemas
│   ├── database.py  # Engine, SessionLocal, Base, get_db dependency
│   └── main.py      # FastAPI application
├── tests/
├── .env.example
└── requirements.txt
```

## Roadmap

Future modules (not yet implemented): Digital Farm Simulator → Data Gateway → Validation → Feature Engine → Risk Engine → Targeted Camera Event → Image Intake → AI Vision → Confidence Gate → Expert Validation → Advisory → Alerts → Follow-up → GIS / Frontend.
