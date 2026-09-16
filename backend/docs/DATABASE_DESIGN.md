# Database Design — Steps 1–6

PostgreSQL via SQLAlchemy 2.x. One engine in `app/database.py`; all models imported
from `app/models/__init__.py` so relationships resolve. Dev tables are created with
`Base.metadata.create_all` at startup; Alembic migrations are planned before deployment.

## Tables

### farms
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String | required |
| location | String | required |
| area_acres | Float | optional |
| created_at | DateTime | auto |

### zones
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| farm_id | FK → farms.id | required; a zone always belongs to a farm |
| name | String | required |
| created_at | DateTime | auto |

Relationships: `farm.zones`, `zone.farm`, `zone.crop` (1:1), `zone.sensor_readings`,
`zone.images`, `zone.risk_assessments`.

### crops
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| zone_id | FK → zones.id | one active crop record per zone (MVP) |
| crop_name | String | required |
| crop_stage | String | optional |
| sowing_date | Date | optional |
| created_at | DateTime | auto |

### sensor_readings
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| zone_id | FK → zones.id | required |
| timestamp | DateTime(tz) | when the observation occurred; required |
| temperature | Float | °C, −50…70 |
| humidity | Float | %, 0–100 |
| rainfall | Float | interval amount, ≥ 0 |
| leaf_wetness | Float | 0–100 (MVP normalized scale) |
| soil_moisture | Float | 0–100 |
| pest_activity | Float | 0–100 software-generated indicator |
| created_at | DateTime | auto |

All readings are software-generated in the MVP (Digital Farm Simulator target).

### risk_assessments
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| zone_id | FK → zones.id | |
| window | String | e.g. "1h" |
| risk_score | Float / null | null = insufficient data |
| risk_level | String | LOW / MEDIUM / HIGH / CRITICAL / INSUFFICIENT_DATA |
| camera_trigger | Boolean | software decision |
| created_at | DateTime | auto |

Exists so `risk_trend` is computed from **real stored history** — historical values
are never invented.

### image_metadata
| Column | Type | Notes |
|---|---|---|
| id | Integer PK | |
| zone_id | FK → zones.id, ON DELETE CASCADE | |
| filename | String | sanitized original name (metadata only) |
| stored_filename | String | generated UUID name actually on disk |
| content_type | String | validated |
| file_size | Integer | bytes |
| width / height | Integer | from real decode |
| image_hash | String | SHA-256 of content |
| source | String | uploaded / simulated_camera / replayed |
| storage_path | String | relative path under `storage/images/` |
| quality_status | String | READY_FOR_AI / LOW_QUALITY / REJECTED |
| blur_score | Float | Laplacian variance |
| brightness_score | Float | mean grayscale 0–255 |
| created_at | DateTime | auto |

**Raw image binaries are never stored in PostgreSQL** — only on the filesystem
(`storage/images/zone_<id>/<uuid>.<ext>`, git-ignored), referenced by `storage_path`
and verifiable via `image_hash`.

## Entity diagram

```text
farms ──1:N──> zones ──1:1──> crops
                 │ 1:N──> sensor_readings
                 │ 1:N──> risk_assessments
                 └ 1:N──> image_metadata ──(filesystem)──> storage/images/zone_N/*
```

## Rules

- Every observation is anchored to a zone; nothing floats without a location.
- FK violations are impossible through the API (existence checked before insert).
- Secrets/credentials live only in `.env` (git-ignored); `.env.example` holds placeholders.
- Future tables (AI predictions, expert reviews, assessments, advisories, alerts,
  follow-ups) will be added as separate entities — existing tables will not be repurposed.
