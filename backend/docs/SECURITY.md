# Security Review — Steps 1–6

## Secrets management

- All credentials come from environment variables (`DATABASE_URL`, optionally `TEST_DATABASE_URL`); nothing hard-coded in source.
- `.env` is git-ignored; `.env.example` contains placeholders only (`YOUR_PASSWORD`).
- `storage/` (runtime uploads) and `models/` are git-ignored.
- No API keys/tokens exist yet (no authentication module — see Known gaps).

## Image upload hardening (Step 6)

| Threat | Mitigation | Verified by tests |
|---|---|---|
| Path traversal (`../../etc/passwd`, `..\..\x.jpg`) | Client filenames are sanitized (separators stripped) and used **only** for metadata; storage name is always a generated UUID under `storage/images/zone_<id>/` | ✅ traversal payloads neutralized |
| Overwrite collisions | UUID storage names; repeated uploads never collide | ✅ |
| Fake extension / wrong MIME | Content-type checked **and** actual Pillow decode performed | ✅ non-image renamed `.jpg` → 400 |
| Corrupted files | Decode failure → 400, nothing stored | ✅ |
| Oversized uploads | 10 MB limit enforced before processing (env-configurable) | ✅ |
| Unbounded listing | `limit` clamped 1–500 on all list endpoints | ✅ |
| Filesystem exposure | No endpoint returns raw bytes or internal paths | ✅ |
| Executable uploads | Files stored inert; never executed or served as code | by design |

## Input validation

- Sensor readings: strict Pydantic ranges (−50…70 °C; 0–100 scales; rainfall ≥ 0) + timezone-aware timestamps required.
- All IDs typed as integers (404 on unknown, no injection surface); SQLAlchemy ORM parameterizes all queries — no raw SQL anywhere.
- Invalid enum values (window, image source) → explicit 400.

## Error handling

- Clean `{"detail": ...}` responses; raw SQLAlchemy/PostgreSQL errors never reach clients.
- No stack traces leaked in API responses.

## AI-specific commitments (for future Step 7)

- Users will never specify model paths — only registry-registered models load.
- Model downloads never happen during a request; setup is an explicit script.
- Uploaded images are treated strictly as data.

## Known gaps (documented, intentional)

1. **No authentication/authorization** — explicitly deferred since Step 1. Any client on the network can call all endpoints. Fine for LAN demos; must be added before any public deployment.
2. **No HTTPS** — plain HTTP on localhost/LAN.
3. **No rate limiting** on uploads or queries.
4. Local filesystem storage (no object storage / virus scanning).

These are known MVP boundaries and are tracked for the deployment-readiness phase.
