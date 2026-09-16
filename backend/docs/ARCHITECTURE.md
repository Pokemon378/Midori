# Midori — Architecture (Steps 1–6)

## System pipeline

```text
Farm
 ↓
Zone
 ↓
Crop
 ↓
Sensor Data API  (POST /zones/{id}/sensor-readings)
 ↓
PostgreSQL  (sensor_readings)
 ↓
Feature Engine  (GET /zones/{id}/features?window=30m|1h|6h|24h)
 ↓  current/avg/min/max, trends, change rates, rainfall totals,
 ↓  leaf-wetness duration, data quality
Risk Engine  (GET /zones/{id}/risk)
 ↓  weighted explainable score 0–100 → LOW/MEDIUM/HIGH/CRITICAL
 ↓  deterministic reason codes, risk_trend from stored history
 ↓  camera_trigger decision
Image Intake  (POST /zones/{id}/images)
 ↓  MIME + decode validation, SHA-256, safe UUID storage
Image Quality  (resolution / blur / brightness — suitability only)
 ↓
READY_FOR_AI   ←———————————————— pipeline ends here
 ↓
[AI VISION — FUTURE STEP, INTENTIONALLY POSTPONED]
```

## Layering

| Layer | Location | Responsibility |
|---|---|---|
| API | `app/api/*` | HTTP parsing, validation, status codes, summaries for /docs. No business logic. |
| Schemas | `app/schemas/*` | Pydantic request/response contracts. |
| Services | `app/features/service.py`, `app/risk/service.py`, `app/images/service.py` | Orchestration: fetch, compute, persist. |
| Pure calculations | `app/features/calculations.py`, `app/risk/calculations.py`, `app/images/quality.py` | Deterministic, unit-testable functions. All thresholds/weights centralized here. |
| Models | `app/models/*` | SQLAlchemy ORM. All models imported in `models/__init__.py` so relationships resolve. |
| Database | `app/database.py` | Single engine, `SessionLocal`, `Base`, `get_db()` dependency. One connection only — no module duplicates it. |

## Data flow guarantees

- **Single source of truth:** Feature Engine reads `sensor_readings` directly with zone+window filtering at the database level (no full-table loads).
- **No duplication:** Risk Engine calls the Feature Engine service — it never re-computes sensor statistics.
- **Determinism:** same input → same features → same risk score → same quality verdict. Trend and rate calculations are pure functions.
- **No invention:** missing data yields `null` / `insufficient_data` / 404 — never fabricated values or fake history. Risk trend comes only from the real `risk_assessments` table.
- **Separation of concerns:** Feature Engine never scores risk; Risk Engine never diagnoses; Image Quality never judges disease. The AI boundary is explicit.

## Database schema

```text
farms ──1:N──> zones ──1:1──> crops
                 │ 1:N──> sensor_readings
                 │ 1:N──> risk_assessments   (risk history → risk_trend)
                 └ 1:N──> image_metadata     (file bytes on filesystem)
```

`image_metadata.zone_id` is `ON DELETE CASCADE`; image binaries live under
`storage/images/zone_<id>/<uuid>.<ext>` (git-ignored), referenced by `storage_path`
plus a SHA-256 `image_hash` for integrity.

## Configuration points (env vars, no magic numbers scattered)

- `DATABASE_URL` / `TEST_DATABASE_URL`
- `TREND_TOLERANCE`, `LEAF_WETNESS_ACTIVE_THRESHOLD` (Feature Engine)
- Risk factor weights/thresholds (single config block in `app/risk/calculations.py`)
- `IMAGE_MIN_WIDTH/HEIGHT`, `IMAGE_BLUR_THRESHOLD`, `IMAGE_BRIGHTNESS_DARK/BRIGHT`, `IMAGE_MAX_FILE_SIZE`, `IMAGE_STORAGE_DIR`

## Error handling conventions

- Nonexistent resource → `404 {"detail": "Zone not found"}` style
- Invalid input → FastAPI 422 validation, or 400 for semantic rules (bad window, bad source, oversized file)
- Insufficient data → 404 (features) or `INSUFFICIENT_DATA` level with `risk_score: null` (risk)
- Raw SQLAlchemy/PostgreSQL errors are never exposed to clients

## AI boundary

Everything above ends at `READY_FOR_AI`. `READY_FOR_AI` means "passed intake and
quality" — **not** "has been analyzed". No diagnosis, confidence, or severity exists
in the current system. See [AI_BOUNDARY.md](AI_BOUNDARY.md).
