# Developer Runbook — Steps 1–6

Everything a developer needs to set up, run, test and troubleshoot the Midori backend.

## 1. Prerequisites

- Python 3.11+ (Windows: `python` from python.org, checked "Add to PATH")
- PostgreSQL 16+ running locally
- Git

## 2. Setup

```bash
cd Midori/backend
python -m venv venv
venv\Scripts\activate            # Windows (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
```

## 3. PostgreSQL configuration

1. Ensure the service is running (`services.msc` → `postgresql-x64-16`).
2. Create the database (once):
   ```sql
   CREATE DATABASE midori;
   ```
3. Copy `.env.example` → `.env` and set your real password:
   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/midori
   ```
4. `.env` is git-ignored — never commit it. Tables are created automatically on first app start.

## 4. Run the server

```bash
uvicorn app.main:app --reload
```

Open:

- http://127.0.0.1:8000/health → `{"status":"ok"}`
- http://127.0.0.1:8000/docs → interactive Swagger UI (all endpoints)

LAN sharing for demos (optional):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
ipconfig   # share http://<your-ipv4>:8000/docs with teammates on the same Wi-Fi
```

## 5. Run tests

Tests use an isolated `midori_test` database — they never touch the dev database.

```bash
# One-time: create the test database
psql -U postgres -c "CREATE DATABASE midori_test;"

# Run the suite
TEST_DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@localhost:5432/midori_test" python -m pytest -q
```

Current expected result: **103 passed, 0 failed, 0 skipped** (see docs/TEST_REPORT.md).

## 6. Quick API walkthrough (demo script)

1. `POST /farms` → `{"name":"Farm 01","location":"Nashik","area_acres":3.5}`
2. `POST /farms/{id}/zones` → `{"name":"Zone A"}`
3. `POST /zones/{id}/crop` → `{"crop_name":"Tomato","crop_stage":"Vegetative"}`
4. `POST /zones/{id}/sensor-readings` a few times (raise humidity/pest over time)
5. `GET /zones/{id}/features?window=1h` → statistics + trends
6. `GET /zones/{id}/risk?window=1h` → score, level, reason codes, `camera_trigger`
7. `POST /zones/{id}/images` (multipart, any JPEG/PNG/WEBP) → quality verdict
8. `GET /zones/{id}/images` → metadata list

## 7. Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Dev PostgreSQL connection | required |
| `TEST_DATABASE_URL` | Isolated test DB | required for tests |
| `IMAGE_STORAGE_DIR` | Image storage root | `storage/images` |
| `IMAGE_MAX_FILE_SIZE` | Upload size limit | 10 MB |
| `IMAGE_MIN_WIDTH/HEIGHT` | Min resolution | 200 / 200 |
| `IMAGE_BLUR_THRESHOLD` | Laplacian variance floor | 60.0 |
| `IMAGE_BRIGHTNESS_DARK/BRIGHT` | Exposure bounds | 50 / 215 |
| `TREND_TOLERANCE` | Feature trend threshold | 2.0 |
| `LEAF_WETNESS_ACTIVE_THRESHOLD` | Wetness duration threshold | 60 |

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `connection refused` at startup | PostgreSQL service not running — start it. |
| `database "midori" does not exist` | Create it (step 3). |
| `password authentication failed` | Fix password in `.env`. |
| Tests fail with DB errors | `TEST_DATABASE_URL` unset or `midori_test` missing. |
| Image upload → 400 | Check format (JPEG/PNG/WEBP), size (≤ 10 MB), file not corrupted. |
| Port already in use | Another uvicorn is running; use `--port 8001`. |

## 9. Things that do NOT exist yet (by design)

- **AI Vision — intentionally postponed.** No model, no inference, no diagnosis.
  `READY_FOR_AI` only means the image passed intake + quality.
- Authentication/RBAC, Alembic migrations, expert validation, severity, advisory,
  alerts, follow-up, GIS endpoints, Digital Farm Simulator.
- Do not claim or demo AI analysis with this build.

## 10. Repository hygiene

- `venv/`, `.env`, `storage/`, `models/*.pt`, caches are git-ignored.
- Test images are generated in-memory; no fixtures to clean.
- If `storage/images/` grows during demos, it can be safely emptied while the server is stopped.
