# Midori — Project Audit (Steps 1–6)

**Date:** 2026-09-16 · **Status:** Steps 1–6 complete and verified · **AI Vision: postponed**

## 1. Repository structure

```
Midori/backend/
├── app/
│   ├── main.py                 # FastAPI app, router wiring, DB init
│   ├── database.py             # SQLAlchemy engine, SessionLocal, Base, get_db()
│   ├── api/                    # HTTP layer (one router per resource)
│   │   ├── farms.py  zones.py  crops.py
│   │   ├── sensor_readings.py  features.py  risk.py
│   │   └── images.py
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── farm.py zone.py crop.py sensor_reading.py
│   │   ├── risk_assessment.py  image_metadata.py
│   │   └── __init__.py         # imports all models so relationships resolve
│   ├── schemas/                # Pydantic request/response schemas
│   ├── features/               # Feature Engine (calculations.py, service.py)
│   ├── risk/                   # Risk Engine (calculations.py, service.py)
│   └── images/                 # Image intake (quality.py, storage.py, service.py)
├── tests/                      # pytest suite (103 tests)
├── docs/                       # engineering documentation
├── scripts/                    # setup utilities
├── requirements.txt  .env.example  .gitignore  README.md
└── storage/images/             # runtime image storage (git-ignored)
```

## 2. Modules — WHAT / WHY / HOW / INPUT / OUTPUT / DEPENDENCIES / TESTS

### FastAPI foundation (`app/main.py`, `app/database.py`)
- **WHAT:** Application entrypoint and database layer.
- **WHY:** Single place to wire routers, create tables on startup, and expose one DB session dependency.
- **HOW:** Routers included under tags; `Base.metadata.create_all` on startup (dev-time table creation; Alembic planned for later migrations). `get_db()` yields a session per request.
- **INPUT:** Env vars `DATABASE_URL` (and `TEST_DATABASE_URL` for tests). **OUTPUT:** `app`, engine, session factory.
- **DEPENDENCIES:** FastAPI, SQLAlchemy, psycopg2, python-dotenv.
- **TESTS:** `tests/test_health.py` — `GET /` and `GET /health`.

### Farm / Zone / Crop (`app/api/farms.py`, `zones.py`, `crops.py`)
- **WHAT:** Spatial hierarchy management — a farm contains zones; a zone holds one crop record.
- **WHY:** Every observation (sensor reading, image, risk) belongs to a physical location; this is the root of all data.
- **HOW:** CRUD-style routers with FK validation — zones cannot be created under nonexistent farms; one crop per zone.
- **INPUT:** JSON bodies validated by Pydantic (`FarmCreate`, `ZoneCreate`, `CropCreate`). **OUTPUT:** Entities with generated IDs and `created_at`.
- **DEPENDENCIES:** SQLAlchemy models `farm.py`, `zone.py`, `crop.py` (relationships: Farm→zones, Zone→farm/crop).
- **TESTS:** `test_farms.py`, `test_zones.py`, `test_crops.py` (19 tests incl. 404s and validation errors).

### Sensor Data API (`app/api/sensor_readings.py`)
- **WHAT:** Receives environmental/pest observations per zone.
- **WHY:** The data inlet for the whole intelligence pipeline. In the MVP, readings are software-generated (Digital Farm Simulator sends them later).
- **HOW:** `POST /zones/{id}/sensor-readings` validates ranges (temp −50…70, humidity 0–100, rainfall ≥ 0, leaf wetness/soil moisture/pest 0–100) and stores timezone-aware timestamps; `GET` (limit 1–500, newest first) and `GET .../latest`.
- **INPUT:** `SensorReadingCreate`. **OUTPUT:** Stored `sensor_readings` rows.
- **DEPENDENCIES:** `sensor_reading.py` model; Zone relationship `zone.sensor_readings`.
- **TESTS:** `test_sensor_readings.py` (15 tests incl. all range violations, 404s, latest).

### Feature Engine (`app/features/`)
- **WHAT:** Converts raw readings into statistical + trend features for a time window (30m/1h/6h/24h).
- **WHY:** Risk scoring needs aggregated, comparable signals, not raw rows. It answers "What is happening?" — never "How risky?".
- **HOW:** `service.py` fetches zone+window-filtered readings from PostgreSQL (no full-table loads) and calls pure functions in `calculations.py`: current/avg/min/max per metric, rainfall total, leaf-wetness active duration (threshold-configurable), trend = earlier-half vs later-half average with tolerance, rate = (last−first)/elapsed hours.
- **INPUT:** zone_id, window. **OUTPUT:** `ZoneFeaturesResponse` (typed per-metric blocks; `null` where data is insufficient — never zero-filled).
- **DEPENDENCIES:** SensorReading model only. No risk logic.
- **TESTS:** `test_features.py` (14 tests with controlled timestamps/values).

### Risk Engine (`app/risk/`)
- **WHAT:** Deterministic, explainable environmental risk score (0–100) from Feature Engine output.
- **WHY:** Decides which zones deserve visual inspection (`camera_trigger`).
- **HOW:** `calculations.py` — weighted sum of configurable 0–100 factor scores; levels 0–24 LOW / 25–49 MEDIUM / 50–74 HIGH / 75–100 CRITICAL; reason codes (`HIGH_HUMIDITY`, `PROLONGED_LEAF_WETNESS`, `INCREASING_HUMIDITY`, `HIGH_PEST_ACTIVITY`, `RECENT_RAINFALL`, `LOW_SOIL_MOISTURE`, `ELEVATED_TEMPERATURE`, `MULTIPLE_FACTORS`, …) with controlled text. `service.py` persists each assessment in `risk_assessments` so `risk_trend` is computed from real stored history only (never invented). `should_trigger_camera()` returns a software decision only.
- **INPUT:** Feature Engine output. **OUTPUT:** score, level, trend, factors, camera_trigger.
- **DEPENDENCIES:** Feature service; RiskAssessment model. No AI, no diagnosis.
- **TESTS:** `test_risk.py` (25 tests: all levels, each factor, trend, camera, insufficient data).

### Image Intake + Quality (`app/images/`, `app/api/images.py`)
- **WHAT:** Receives crop images, validates them, stores files safely, runs quality checks.
- **WHY:** Prepares images for future AI analysis; blocks bad images from wasting inference.
- **HOW:** `POST /zones/{id}/images` (multipart) → MIME + real decode validation (JPEG/PNG/WEBP via Pillow) → SHA-256 hash → stored as `storage/images/zone_<id>/<uuid>.<ext>` (client filename never trusted; sanitized only for metadata) → quality checks in `quality.py`: resolution (min 200×200), blur (Laplacian variance), brightness (mean grayscale). Statuses: `READY_FOR_AI`, `LOW_QUALITY` (with reasons), `REJECTED` (HTTP 400). Metadata in `image_metadata` table; binaries on filesystem.
- **INPUT:** image bytes, source (`uploaded`/`simulated_camera`/`replayed`). **OUTPUT:** metadata response incl. quality metrics.
- **DEPENDENCIES:** Pillow, python-multipart; Zone FK.
- **TESTS:** `test_images.py` (26 tests: formats, corruption, traversal, oversize, determinism, storage isolation).

## 3. Database tables

| Table | Purpose | Key relations |
|---|---|---|
| farms | Farm registry | → zones (1:N) |
| zones | Zone inside a farm | → farm, crop (1:1), sensor_readings (1:N), images, risk_assessments |
| crops | Crop assigned to a zone | → zone |
| sensor_readings | Environmental observations | → zone |
| risk_assessments | Risk Engine history (drives real trend) | → zone |
| image_metadata | Image metadata + quality | → zone (CASCADE), file on disk |

## 4. Existing APIs (15 paths in OpenAPI)

`GET /` · `GET /health` · farms/zones/crops CRUD · sensor readings (create/list/latest) · `GET /zones/{id}/features` · `GET /zones/{id}/risk` · image upload/list/metadata.

## 5. Current working features (verified)

Full pipeline: Farm → Zone → Crop → Sensor readings → Features → Risk (with camera trigger) → Image upload → Quality → READY_FOR_AI. 103/103 tests pass; live smoke test of the whole chain succeeded.

## 6. Current incomplete / intentionally postponed features

| Feature | Status |
|---|---|
| **AI Vision (Step 7)** | **Intentionally postponed** — a work-in-progress `app/ai/` exists locally but is excluded from this verified release; no predictions are produced. |
| Expert validation, Severity, Final assessment, Advisory, Alerts, Follow-up, GIS backend | Not started (future steps, after AI Vision). |
| Authentication/RBAC | Not started (explicitly deferred from Step 1). |
| Alembic migrations | Deferred; `create_all` used for dev. |
| Digital Farm Simulator | Not started; the Sensor Data API is its future target. |
| Image file download endpoint | Not implemented (kept simple by design). |

## 7. Missing pieces for the final core workflow

1. AI Vision (model strategy, registry, inference) — next major stage.
2. Confidence handling → Expert validation workflow.
3. Severity engine (separate from risk and diagnosis).
4. Final assessment record joining risk + AI + expert review.
5. Advisory backend with structured content + language support (EN/TA/MR).
6. Alerts lifecycle + follow-up monitoring.
7. GIS backend endpoints for the frontend map.
8. Authentication and Alembic migrations before deployment.
