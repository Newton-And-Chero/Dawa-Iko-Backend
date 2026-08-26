# CALL-E Medicine & Commodity Availability Agent — Backend

Python/FastAPI backend for the project described in [PROJECT.md](../PROJECT.md):
call facility pharmacies and private chemists in parallel via CALL-E, turn
their answers into structured availability data, and surface it through a
REST/WS API. Built sprint-by-sprint per [workflows/](../workflows/); this
sprint (09) is the last in the current backend-only roadmap — see
[workflows/09-testing-hardening-deployment.md](../workflows/09-testing-hardening-deployment.md)
for its definition of done.

> The repo-root [README.md](../README.md) is a separate, already-superseded
> product pitch document (Community Health Follow-Up Agent) — out of date,
> out of scope for this file.

**Building the frontend against this API?** Start with
[`docs/api.md`](docs/api.md) — every REST endpoint, request/response shape,
auth/role rules, and error case. Real-time WS/SSE payloads are in
[`docs/realtime-contract.md`](docs/realtime-contract.md). The live
Swagger UI (`GET /docs` once the API is running) is the always-current
schema reference for anything `docs/api.md` doesn't cover in enough detail.

## Local setup

Requires Docker and Docker Compose.

```sh
cd backend
cp .env.example .env   # edit if you need non-default values — see below
docker compose up
```

This brings up the whole stack: `api` (FastAPI on `:8000`), `worker` and
`beat` (Celery, sharing the sweep-orchestration and analytics tasks),
`db` (Postgres+PostGIS on host port `5433`), and `redis` (`:6379`). Every
service has a healthcheck and `worker`/`beat`/`api` wait on `db`/`redis`
being healthy before starting. Migrations aren't run automatically — apply
them once the `db` service is healthy:

```sh
docker compose exec api uv run alembic upgrade head
```

For a production-shaped run (no source bind-mounts, gunicorn-managed
uvicorn workers, restart policies), layer the override file rather than
running a second compose file:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

### Seeding demo data

```sh
docker compose exec api uv run python -m scripts.seed_demo
```

Seeds the facility directory (Kirinyaga + Nairobi + manually-added private
chemists, Sprint 02), the KEML commodity catalog, a fixed set of test login
accounts (one per role) and alert subscribers, then backfills 8 weeks of
historical sweeps for each priority-watchlist commodity in
`app/workers/beat_schedule.py`'s `WATCHLIST_SWEEPS` — all against
`MockCallEAdapter`, never a real call — so the Sprint 08 time-series view
(`GET /v1/analytics/stockout-rate`) has real data to show before any demo,
per PROJECT.md's MVP scope (§4, item 7). Safe to re-run; facility/commodity/
user/subscriber seeding is idempotent, and re-running just adds more sweep
history. `scripts/seed_db.py` (facilities/commodities/users/subscribers,
no sweep history) runs standalone too, and is what the demo script wraps.

**Test login accounts** (password for all three: `testpass123` —
`scripts/seed_db.py`'s `TEST_USERS`):

| Role | Phone number |
|---|---|
| `admin` | `+254700000001` |
| `analyst` | `+254700000002` |
| `viewer` | `+254700000003` |

Log in against `POST /v1/auth/login` with one of these — see
[`docs/api.md`](docs/api.md#auth). Dev-only credentials, fixed rather than
random on purpose so they're reproducible; never used outside a `mock`-mode
local deployment.

## Running the test suite

```sh
uv sync
uv run pytest
```

Every automated test runs against `MockCallEAdapter`/`MockSMSAdapter` —
nothing in `tests/` ever places a real call or sends a real SMS (see
`workflows/RULES.md`). `tests/integration/` holds the cross-sprint suite
added in Sprint 09:

- `test_full_sweep_flow.py` — the project's real end-to-end proof: a public
  query dispatches mock calls, a mock webhook lands on the real route, an
  `AvailabilityResult` is persisted, a connected WS client sees the sweep
  complete live, and the analytics endpoint reflects it.
- `test_webhook_forgery.py` — adversarial cases against the webhook
  receiver (wrong token, mismatched event id, unknown call, forged replay).
- `test_rate_limit_abuse.py` — burst/hammer traffic against the public
  query endpoint's rate limiter, including a check that its Redis keys
  carry a TTL and don't accumulate unboundedly.

`tests/` needs a real Postgres+PostGIS and Redis reachable at
`DATABASE_URL`/`REDIS_URL` (the `docker compose up` instance works — point
at `localhost:5433`/`localhost:6379` if running pytest from the host rather
than inside a container). CI runs the same suite against the same image
versions as `docker-compose.yml`'s `db`/`redis` services.

There is exactly one script allowed to touch the real CALL-E API:
`scripts/smoke_test_live_calle.py`. It is a manual, human-operated CLI tool
— never run in CI, never importable from `pytest` or a Celery task — that
requires an explicit `--i-understand-this-costs-money-and-calls-a-real-phone`
flag and a real `CALLE_API_KEY` before it will place one real, billed call.

## Environment variables

See [.env.example](.env.example) for the full list with placeholder values
and inline comments. Highlights:

- `CALL_E_MODE` / `SMS_MODE` — `mock` (default everywhere except a real
  production deploy) or `live`. Never commit these as `live`.
- `DATABASE_URL` / `REDIS_URL` — service hostnames (`db`/`redis`) resolve
  inside the Compose network; use `localhost:5433`/`localhost:6379` from
  the host.
- `JWT_SECRET` — the app refuses to boot if this is still a placeholder
  (`change-me`/`changeme`/empty) and `ENV=production`.
- `PUBLIC_QUERY_RATE_LIMIT` / `PUBLIC_QUERY_RATE_WINDOW_SECONDS` — the
  fixed-window limit on `POST /v1/sweeps/query`, the one endpoint that
  spends real money per request.

Real secrets (a live `CALLE_API_KEY`, a real `JWT_SECRET`, etc.) are never
checked in — they come from the deployment environment's own secret store.

## How a demo query flows end-to-end

A client calls `POST /v1/sweeps/query` with a commodity and a geography
(Sprint 05); the router resolves the candidate facility list (Sprint 04's
geography resolver + PostGIS, Sprint 02's seeded directory) and dispatches
one CALL-E call task per chunk (Sprint 03's adapter, `MockCallEAdapter` in
mock mode), returning a `sweep_id` immediately. As CALL-E's webhook
delivers each call's structured result, `HandleCalleWebhookUseCase`
persists `AvailabilityResult` rows, flips the `Call`/`Sweep` status, runs
stockout detection and escalation dispatch when a sweep completes at or
below the scarcity threshold (Sprint 07), and publishes events over Redis
pub/sub that a connected WS client on `/ws/sweeps/{sweep_id}` receives live
(Sprint 06). Once the sweep is complete, `GET /v1/sweeps/{sweep_id}`
returns the ranked in-stock matches, and `GET /v1/analytics/stockout-rate`
(Sprint 08) folds the new sweep into that commodity/geography's historical
stockout-rate time series. `tests/integration/test_full_sweep_flow.py`
exercises this exact path end to end.
