# Sprint 00 — Start: Project Setup & Foundations

> Read [`RULES.md`](./RULES.md) first — it applies here and to every later sprint.

## Goal & Definition of Done

A `backend/` project exists that runs, lints, type-checks, and tests green with **zero domain logic in it yet**. Anyone can `docker compose up`, get a Postgres+PostGIS and Redis instance, run migrations (against an empty schema), start the API, and hit `/healthz` successfully. CI runs lint + type-check + test on every push.

## Preconditions

None — this is the first sprint. Only `PROJECT.md`, `README.md`, `problems.md`, and `workflows/` exist in the repo before this sprint starts.

## Architecture for this sprint

Create the full clean-architecture folder skeleton now, even though most folders start empty (with just an `__init__.py`), so later sprints never have to decide where something goes:

```
backend/
  pyproject.toml            # uv-managed, Python version pinned
  uv.lock
  .env.example
  .python-version
  docker-compose.yml         # postgres (postgis/postgis image), redis
  Dockerfile
  alembic.ini
  alembic/
    env.py
    versions/                # empty at this sprint
  app/
    __init__.py
    main.py                  # FastAPI app factory, mounts routers, /healthz
    core/
      __init__.py
      config.py               # pydantic-settings Settings, reads .env
      logging.py               # structured logging setup
      security.py               # placeholder for Sprint 05 auth
      exceptions.py               # app-wide exception types
    domain/
      __init__.py
    application/
      __init__.py
      ports/
        __init__.py
      use_cases/
        __init__.py
    infrastructure/
      __init__.py
      db/
        __init__.py
        session.py             # async SQLAlchemy engine/session factory
      call_e/
        __init__.py
      notifications/
        __init__.py
      cache/
        __init__.py
        redis.py                 # async Redis client factory
    api/
      __init__.py
      v1/
        __init__.py
        router.py                 # aggregates versioned routers (empty for now)
    workers/
      __init__.py
      celery_app.py               # Celery app instance, Redis broker/backend
  tests/
    __init__.py
    conftest.py
    test_healthz.py
  .github/
    workflows/
      ci.yml                       # (repo-root .github/workflows, not backend/)
```

Note: `.github/workflows/ci.yml` lives at the **repo root** `.github/`, not inside `backend/`, per GitHub Actions convention.

## Task checklist

- [ ] Initialize `backend/` as a `uv` project (`uv init`), pin a Python 3.12+ version in `.python-version`.
- [ ] Add core dependencies via `uv add`: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `sqlalchemy[asyncio]`, `asyncpg`, `geoalchemy2`, `alembic`, `celery[redis]`, `redis`, `httpx`.
- [ ] Add dev dependencies via `uv add --dev`: `pytest`, `pytest-asyncio`, `ruff`, `mypy`, `pre-commit`.
- [ ] Write `app/core/config.py` — a `Settings(BaseSettings)` class reading every env var this project will ever need across all sprints (database URL, Redis URL, `CALLE_API_KEY`, `CALL_E_MODE`, `SMS_MODE`, `TWILIO_*`, JWT secret, `MAX_RECIPIENTS_PER_TASK`, webhook token secret). It's fine for most to be unused until later sprints — declaring them here now means `.env.example` is complete from day one.
- [ ] Write `.env.example` mirroring every `Settings` field with a placeholder or safe default (`CALL_E_MODE=mock`, `SMS_MODE=mock`).
- [ ] Write `app/main.py` — FastAPI app factory, CORS middleware (permissive for now, revisit in Sprint 05), mounts `app/api/v1/router.py`, exposes `GET /healthz` returning `{"status": "ok"}`.
- [ ] Write `app/infrastructure/db/session.py` — async engine + `async_sessionmaker`, reading the DB URL from `Settings`.
- [ ] Write `app/infrastructure/cache/redis.py` — async Redis client factory reading the Redis URL from `Settings`.
- [ ] Write `app/workers/celery_app.py` — Celery app configured with Redis as both broker and result backend, reading from `Settings`.
- [ ] `alembic init` wired to the async engine and to `Settings` for the DB URL (no models to migrate yet — this sprint just proves migrations run against an empty schema).
- [ ] `docker-compose.yml`: `postgres` service using a PostGIS-enabled image (e.g. `postgis/postgis:16-3.4`), `redis` service, both with named volumes and healthchecks.
- [ ] `Dockerfile` for the backend, multi-stage, using `uv` for install.
- [ ] `ruff` config (lint + format) and `mypy` config in `pyproject.toml`.
- [ ] `.pre-commit-config.yaml` running ruff + mypy on commit.
- [ ] `tests/conftest.py` with an async test client fixture (`httpx.AsyncClient` against the FastAPI app); `tests/test_healthz.py` asserting `/healthz` returns 200.
- [ ] `.github/workflows/ci.yml` — on push/PR: `uv sync`, `ruff check`, `mypy`, `pytest`.
- [ ] Root `.gitignore` covering `.env`, `__pycache__/`, `.venv/`, `*.pyc`, `.mypy_cache/`, `.ruff_cache/`.

## API / data contract additions

- `GET /healthz` → `200 {"status": "ok"}`. No other endpoints yet.

## Rules specific to this sprint

- **DO NOT** add any table, model, or migration with real columns yet — that's Sprint 01. This sprint proves the migration *machinery* works, not the schema.
- **DO NOT** write any CALL-E, SMS, or geography code yet, even stubs beyond the empty `infrastructure/call_e/__init__.py` etc. — those are later sprints' folders to fill in.
- **DO** make `Settings` the single source of truth for configuration; nothing in later sprints should read `os.environ` directly.
- **DO** keep `docker-compose.yml` dev-oriented (bind-mounted code, hot reload via `uvicorn --reload`) — a separate production compose/deploy setup is Sprint 09's job.

## Testing requirements

- `pytest` passes (`test_healthz.py` green) against a running Postgres+Redis (via `docker compose up -d db redis` or CI service containers).
- `ruff check` and `mypy` pass with zero errors.
- `alembic upgrade head` runs cleanly against a fresh empty database (no-op, since there are no versions yet, but the command must not error).
- CI workflow passes on a clean clone.

## Explicitly deferred

- Domain entities, DB schema, repositories → Sprint 01.
- Any authentication → Sprint 05.
- Any CALL-E, SMS, or geography adapter code → Sprints 03, 04, 07.
