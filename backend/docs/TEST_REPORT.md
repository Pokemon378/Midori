# Test Report — Steps 1–6 (2026-09-16)

## Result

| Metric | Value |
|---|---|
| Total tests | 103 |
| Passed | 103 |
| Failed | 0 |
| Skipped | 0 |

Command:

```bash
TEST_DATABASE_URL="postgresql://postgres:...@localhost:5432/midori_test" python -m pytest -q
```

Tests run against an isolated `midori_test` PostgreSQL database (conftest override) —
the development database is never touched or destroyed by tests.

## Breakdown by module

| Suite | Tests | Covers |
|---|---|---|
| `test_health.py` | 2 | Step 1 root + health endpoints |
| `test_farms.py` | 7 | Step 2 farm CRUD, 404, validation |
| `test_zones.py` | 7 | Step 2 zones under farms, 404s |
| `test_crops.py` | 5 | Step 2 crop assignment, 404s |
| `test_sensor_readings.py` | 15 | Step 3 create/list/latest + every range violation |
| `test_features.py` | 14 | Step 4 statistics, trends, rates, wetness duration, windows, 404s |
| `test_risk.py` | 25 | Step 5 levels, factor codes, trend history, camera trigger, insufficient data |
| `test_images.py` | 26 | Step 6 formats, corruption, quality classes, security, metadata |
| **Total** | **103** | |

## Test design principles

- **Deterministic:** no random data; controlled timestamps/values; feature tests anchor timestamps relative to "now" so window filtering never goes stale.
- **Isolated:** every test gets a clean transaction-scoped session against `midori_test`.
- **No network:** nothing downloads; all test images are generated in-memory with Pillow.
- **Regression-safe:** each step's suite was preserved untouched as later steps were added.

## Notable verified behaviours

- Validation rejects impossible sensor values (humidity 101, rainfall −1, etc.) with 422.
- Nonexistent zones/farms/images → clean 404; no server crashes.
- Risk Engine returns `risk_score: null` + `INSUFFICIENT_DATA` + `camera_trigger: false` when there is no data — never a fabricated score.
- Risk trend uses only real `risk_assessments` history (`insufficient_data` on first assessment).
- Image intake rejects empty/corrupted/misnamed/oversized files with 400; path-traversal filenames are neutralized; storage names are UUIDs (no overwrites); blur/brightness verdicts are deterministic across repeated runs.

## Live verification (2026-09-16)

Beyond pytest, a live end-to-end run against the real `midori` database:

1. `GET /health` → ok
2. Farm → Zone → Crop created
3. 4 sensor readings over 30 minutes (rising humidity/pest)
4. `GET /features?window=1h` → observation_count 4, humidity & pest trends `increasing`
5. `GET /risk?window=1h` → score 56.0, HIGH, `camera_trigger: true`, factors `[HIGH_HUMIDITY, ELEVATED_LEAF_WETNESS, HIGH_PEST_ACTIVITY, MULTIPLE_FACTORS]`
6. Image upload (simulated flat test image) → correctly judged `LOW_QUALITY` (zero Laplacian variance), metadata persisted and retrievable
7. OpenAPI exposes 15 paths in `/docs`

**Step 7 — AI Vision: intentionally postponed; no AI tests, models or predictions exist in this verified build.**
