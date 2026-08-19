# Sprint 09 — Testing, Hardening & Deployment

> Preconditions: Sprints 00-08 complete. This is the last workflow in the current (backend-only) roadmap — by the end of this sprint the backend is a fully working, demoable product per PROJECT.md's MVP scope (§4).

## Goal & Definition of Done

The full backend runs as a single `docker compose up`, seeded with enough pre-run sweep history that the time-series analytics from Sprint 08 have real data to show (PROJECT.md MVP item 7: "at least one repeated sweep pre-run before the demo"), every automated test still runs against `MockCallEAdapter`/`MockSMSAdapter` only, and a real-CALL-E smoke test exists but is explicitly opt-in and never runs unattended. Basic hardening (input validation edges, rate-limit abuse cases, webhook forgery attempts) is verified, not assumed.

## Preconditions

- Every prior sprint's automated tests pass individually. This sprint is integration across all of them, not new features.

## Architecture for this sprint

```
backend/
  docker-compose.yml          # extended: api service (uvicorn), celery-worker service, celery-beat service,
                                # postgres, redis — the full stack, one command
  docker-compose.prod.yml       # production-shaped overrides (no bind mounts, gunicorn+uvicorn workers,
                                 # restart policies) — additive override file, not a duplicate compose file
  scripts/
    seed_demo.py                 # seeds facilities/commodities (Sprint 02) + runs several historical
                                   # mock sweeps across past dates so Sprint 08's time series has data
    smoke_test_live_calle.py       # manual, flag-gated, calls the REAL CALL-E API once against a
                                     # test number the operator explicitly confirms — never run in CI
  tests/
    integration/
      test_full_sweep_flow.py       # end-to-end: query -> mock CALL-E -> webhook -> AvailabilityResult
                                      # -> WS event -> analytics reflects it
      test_webhook_forgery.py         # adversarial: wrong token, replayed event, spoofed call_id
      test_rate_limit_abuse.py          # hammer POST /sweeps/query past the limit
  .github/workflows/ci.yml (extended)  # add integration test stage with docker-compose services
```

## Task checklist

- [ ] `docker-compose.yml` extended to run the **whole** stack: `api`, `celery-worker`, `celery-beat`, `postgres`, `redis`, each with healthchecks and correct `depends_on` ordering.
- [ ] `docker-compose.prod.yml` — an override file for a production-shaped run (no source bind-mounts, `uvicorn` behind `gunicorn` workers or equivalent, restart policies, resource limits) — used as `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`, not a second full copy of the file.
- [ ] `scripts/seed_demo.py` — runs Sprint 02's `seed_db.py` (facilities + commodities), then triggers several `run_on_demand_sweep`/`run_scheduled_sweep` calls (via `MockCallEAdapter`, backdating `Sweep.created_at`/`Call.started_at` where the domain model allows it, or running sweeps in a tight loop if backdating isn't modeled) so that Sprint 08's stockout-rate-over-time view has multiple weeks of real (mock-sourced) data before any demo.
- [ ] `scripts/smoke_test_live_calle.py` — a manual CLI script, **not part of any test suite or CI job**, requiring an explicit `--i-understand-this-costs-money-and-calls-a-real-phone` flag (or equivalent unambiguous confirmation) plus a real `CALLE_API_KEY` and a real target phone number passed by the operator, before it will place a single real `POST /v1/calls`. This is the only place in the whole codebase that's allowed to run `CALL_E_MODE=live`.
- [ ] `test_full_sweep_flow.py` — the single most important integration test in the project: `POST /sweeps/query` → mock CALL-E dispatch → mock webhook fires → `AvailabilityResult` rows persisted → WS event received by a connected test client → `GET /analytics/stockout-rate` reflects the new sweep. This exercises Sprints 03 through 08 as one path and is the automated proof the "fully working product" claim is true.
- [ ] `test_webhook_forgery.py` — adversarial cases from Sprint 03's rules, run together as a suite: wrong `webhook_token` path segment, `CALL-E-Event-Id` header not matching body `id`, a `call_id` never dispatched by us, a replayed already-processed event id. Every case must be rejected or safely no-op'd, never silently accepted as real.
- [ ] `test_rate_limit_abuse.py` — burst requests at `POST /sweeps/query` past `Settings.PUBLIC_QUERY_RATE_LIMIT`, confirm `429`s, confirm legitimate requests after the window resets still succeed, confirm the rate limiter itself doesn't leak memory/keys unboundedly in Redis (TTL on the limiter keys).
- [ ] Review every `Settings` field for a safe default in a non-production environment (`CALL_E_MODE=mock`, `SMS_MODE=mock`, permissive-but-not-wildcard CORS, a clearly-fake default JWT secret **that raises a startup error if still set when `ENV=production`** — add that specific guard now, it's cheap and prevents a real class of deploy mistake).
- [ ] `.github/workflows/ci.yml` — add an integration-test stage that brings up the `docker-compose.yml` service dependencies (postgres, redis) and runs the full test suite including `tests/integration/`, not just the unit tests from earlier sprints.
- [ ] A top-level `backend/README.md` (not the repo-root `README.md`, which is a separate, already-superseded product pitch document out of this sprint's scope) covering: local setup (`docker compose up`), running `seed_demo.py`, running the test suite, environment variables reference (pointing at `.env.example`), and a one-paragraph "how a demo query flows end-to-end" walkthrough referencing the sprint numbers where each piece was built.
- [ ] Final pass: run the full test suite (all sprints) once, clean, from a fresh clone + `docker compose up` + `uv sync`, to confirm there's no accumulated environment drift from building sprint-by-sprint.

## API / data contract additions

None new — this sprint hardens and proves the existing contract from Sprints 05-08, it doesn't add endpoints.

## Rules specific to this sprint

- **DO NOT** let `smoke_test_live_calle.py` be reachable from `pytest`, CI, or any Celery task — it is a human-operated CLI tool only, per `RULES.md`'s "never call a real external paid API from an automated test."
- **DO** treat `test_full_sweep_flow.py` as the sprint's real definition of done — if it doesn't pass, the backend is not a "fully working product" yet regardless of what any individual sprint's own tests say.
- **DO NOT** ship a default JWT secret, CORS wildcard, or `CALL_E_MODE`/`SMS_MODE` defaulting to `live` in anything committed to the repo — production values are supplied via the deployment environment's own secret store, never checked in, and the app should refuse to boot in `ENV=production` with an obviously-placeholder secret still set.
- **DO** keep `docker-compose.prod.yml` as an override, not a fork — drift between two full compose files is exactly the kind of duplication `RULES.md` warns against.

## Testing requirements

- `test_full_sweep_flow.py`, `test_webhook_forgery.py`, `test_rate_limit_abuse.py` all pass in CI.
- CI's integration stage passes against real (containerized) Postgres+PostGIS and Redis, not mocks of the infrastructure itself (only CALL-E/SMS are mocked — the DB and cache are real).
- A fresh-clone smoke run (`docker compose up`, `seed_demo.py`, hit `POST /sweeps/query`, watch it complete via WS, check `/analytics/stockout-rate`) is performed manually at least once and confirmed working before calling this sprint done.

## Explicitly deferred

- Frontend/dashboard implementation — out of scope for this roadmap per the current instruction; a future workflow document would pick this up against the now-stable Sprint 05/06 contracts.
- Multi-county/national scale-up, DHIS2 enrichment, KEMSA correlation, commodity-specific question variants, automatic language switching — all explicit PROJECT.md §5 stretch goals, intentionally not built in this roadmap.
- Production infrastructure choice (cloud provider, managed Postgres/Redis, secrets manager) — `docker-compose.prod.yml` is deployment-shaped but this roadmap does not pick or configure an actual hosting target.
