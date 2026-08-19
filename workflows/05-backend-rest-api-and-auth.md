# Sprint 05 — Backend REST API & Auth

> Preconditions: Sprints 01-04 complete — every use case this sprint exposes over HTTP already exists and is tested.

## Goal & Definition of Done

Every use case built in Sprints 01-04 is reachable over a versioned REST API, protected by JWT auth with role-based access, with the public query endpoint rate-limited. This is the contract any future frontend (or `curl`/Postman demo) is built against — so response shapes must be stable, documented (OpenAPI, which FastAPI generates automatically from the Pydantic schemas here), and exercised by tests, not just "written."

## Preconditions

- Domain entities + repositories (01), facility/commodity management use cases (02), CALL-E + webhook pipeline (03), sweep orchestration use cases (04).

## Architecture for this sprint

```
app/api/v1/
  schemas/
    facility.py           # FacilityIn, FacilityOut, FacilityFilter (Pydantic, mirrors domain entity fields)
    commodity.py
    sweep.py                # SweepCreate (public query body), SweepOut, SweepProgressOut
    call.py
    availability_result.py
    escalation.py            # (schemas defined now, wired to real data in Sprint 07)
    subscriber.py
    user.py                    # UserOut, LoginIn, TokenOut
  routers/
    facilities.py
    commodities.py
    sweeps.py                  # includes POST /query (the public demo path)
    calls.py
    availability_results.py
    auth.py                       # /auth/login, /auth/me
    users.py                        # admin-only user management
  dependencies.py               # get_current_user, require_role(*roles), pagination params
  rate_limit.py                    # Redis token-bucket dependency for the public query endpoint

app/core/
  security.py                    # (filled in properly this sprint) JWT encode/decode, password hashing
```

## Task checklist

- [ ] `core/security.py` — JWT issuance (`create_access_token(user)`) and verification, password hashing (`passlib`/`argon2`), tied to the `User` entity + repository from Sprint 01.
- [ ] `POST /api/v1/auth/login` — email/password (or phone/password, per `User` entity fields) → `{access_token, token_type}`.
- [ ] `GET /api/v1/auth/me` — current user from JWT.
- [ ] `dependencies.get_current_user` — decodes JWT, loads `User` via repository, raises 401 if invalid/missing.
- [ ] `dependencies.require_role(*roles)` — 403 if `current_user.role` not in `roles`. Roles: `admin | analyst | viewer | public` per PROJECT.md §2.6. `public` means **no token required** for read-only aggregate endpoints — model this as "no auth dependency" on those specific routes, not a fake "public user" token.
- [ ] Facilities router: `GET /facilities` (filter: county/sub_county/ward/type/ownership/call-success-rate, paginated), `GET /facilities/{id}`, `POST /facilities` (admin/analyst), `PATCH /facilities/{id}` (admin/analyst), `POST /facilities/{id}/verify-phone` (admin/analyst) — all thin wrappers over Sprint 02's use cases.
- [ ] Commodities router: `GET /commodities` (filter: category/watchlist/search-by-alias), `GET /commodities/{id}`, `POST /commodities` (admin), `PATCH /commodities/{id}` (admin).
- [ ] Sweeps router:
  - **`POST /sweeps/query`** — the public demo path per PROJECT.md 2.6: body `{commodity, geography}` (commodity by id or name/alias lookup; geography as one of the `GeographyScope` variants) → calls `run_on_demand_sweep` → `202 {"sweep_id": ...}`. **No auth required** (public), but **rate-limited** (see below) since each call triggers real phone calls.
  - `GET /sweeps/{sweep_id}` — sweep detail + progress (`get_sweep_status`).
  - `GET /sweeps` — list/filter (commodity, geography, date range, status), paginated, analyst+.
  - `POST /sweeps/scheduled` — admin/analyst: register a recurring watchlist sweep (wires into Sprint 04's Beat schedule).
  - `POST /calls/{call_id}/retry` — analyst+: manual "call this facility now" (`request_manual_call`).
- [ ] Calls + AvailabilityResults routers: `GET /calls`, `GET /calls/{id}` (incl. transcript/recording URLs), `GET /availability-results` (filter: commodity/geography/date-range/stock-status, paginated) — this is the endpoint a "where can I get X" ranked list is built from (ranked by confidence/distance, in-stock first, per PROJECT.md 2.7's query view spec, even though rendering that ranking is a future frontend's job — the ordering/filtering happens here).
- [ ] `rate_limit.py` — Redis-backed token bucket (or fixed-window counter) keyed by client IP (and/or a lightweight per-request fingerprint), applied only to `POST /sweeps/query`, configurable via `Settings` (`PUBLIC_QUERY_RATE_LIMIT`, `PUBLIC_QUERY_RATE_WINDOW_SECONDS`). Returns `429` with a `Retry-After` header when exceeded.
- [ ] Pagination: a shared `PageParams` dependency (`limit`/`offset` or cursor-based — pick one, document the choice) applied consistently across every list endpoint; response envelope `{items: [...], total: int, limit: int, offset: int}`.
- [ ] Wire `api/v1/router.py` (Sprint 00's empty placeholder) to include every router above.
- [ ] Tighten CORS in `main.py` from Sprint 00's permissive default to an explicit allow-list read from `Settings` (still broad for dev, but no longer `*` unconditionally, since real auth now exists).
- [ ] Integration tests (via the `httpx.AsyncClient` fixture from Sprint 00) for every endpoint: happy path, auth-required-and-denied, role-denied, and — for `POST /sweeps/query` — rate-limit-exceeded.

## API / data contract additions

This sprint **is** the contract. Every endpoint above, with request/response Pydantic schemas, becomes part of FastAPI's auto-generated OpenAPI doc at `/docs` — treat that as the living API reference from this point forward. Response field names mirror the domain entities from Sprint 01 exactly (no silent renames between layers).

## Rules specific to this sprint

- **DO NOT** put any orchestration, DB query, or CALL-E logic inside a router function — every router method is `parse request → call one use case → serialize response`, per `RULES.md`'s core boundary.
- **DO** rate-limit `POST /sweeps/query` before anything else in this sprint touches it — it is the one endpoint that spends real money and rings real phones if abused, per PROJECT.md 2.6's explicit warning.
- **DO NOT** expose `Facility.phone_number` or a facility's raw call transcript on any `public`-role-accessible endpoint without deciding deliberately whether that's intended — default to requiring at least `viewer` role for anything containing a phone number or transcript, per common-sense data minimization, and flag this decision back to the user if PROJECT.md doesn't already resolve it explicitly.
- **DO** keep the `public` role's read surface to aggregate/ranked results (PROJECT.md 2.7's "simplified public-facing view") — full facility management, raw call data, and subscriber/user endpoints are never `public`.

## Testing requirements

- Every router has at least one integration test per role tier it distinguishes (denied, allowed).
- Rate-limit test proves the Nth+1 request within the window gets `429`, and a request after the window resets succeeds.
- `GET /docs` (OpenAPI JSON) renders without error and includes every router.
- Full test suite (Sprints 00-05) still green — this sprint must not regress anything below it.

## Explicitly deferred

- WebSocket/SSE real-time push — Sprint 06 (this sprint's endpoints are request/response and polling only).
- Escalation/subscriber endpoints returning real data — schemas exist here, real logic in Sprint 07.
- Analytics/export endpoints — Sprint 08.
