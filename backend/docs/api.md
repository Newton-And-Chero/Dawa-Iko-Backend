# CALL-E Backend API Reference

Everything the frontend needs to integrate with the backend: every REST
endpoint, every WebSocket/SSE stream, request/response shapes, auth rules,
and every documented error case (success **and** failure).

This is a hand-written companion to the live, auto-generated OpenAPI docs at
`GET /docs` (Swagger UI) / `GET /openapi.json` — those are always the source
of truth for the exact schema; this file adds the narrative context (roles,
failure modes, flows) the raw schema doesn't carry.

> Real-time event payloads are documented in full in
> [`realtime-contract.md`](./realtime-contract.md). This file summarizes the
> WS/SSE routes and links there for per-event-type detail so it isn't
> duplicated in two places.

---

## Table of contents

1. [Base URL & versioning](#base-url--versioning)
2. [Authentication](#authentication)
3. [Roles & access control](#roles--access-control)
4. [Common conventions](#common-conventions)
5. [Error reference](#error-reference)
6. [Rate limiting](#rate-limiting)
7. [Endpoints](#endpoints)
   - [Auth](#auth)
   - [Facilities](#facilities)
   - [Commodities](#commodities)
   - [Sweeps](#sweeps)
   - [Calls](#calls)
   - [Call engine (on/off switch)](#call-engine-onoff-switch)
   - [Availability Results](#availability-results)
   - [Escalations](#escalations)
   - [Subscribers](#subscribers)
   - [Users (admin)](#users-admin)
   - [Analytics](#analytics)
   - [Health check](#health-check)
8. [Real-time (WebSocket / SSE)](#real-time-websocket--sse)
9. [Enums reference](#enums-reference)
10. [End-to-end example: the public query flow](#end-to-end-example-the-public-query-flow)

---

## Base URL & versioning

| Environment | Base URL |
|---|---|
| Local (docker compose) | `http://localhost:8000` |

Every REST endpoint below is prefixed with **`/v1`** (e.g. `POST /v1/sweeps/query`),
except:

- `POST /webhooks/calle/{webhook_token}` — inbound CALL-E webhook receiver.
  **Not part of the frontend-facing API** — documented here only so you know
  it exists; don't call it from a client.
- `GET /healthz` — unversioned health check.
- `WS /ws/sweeps/{sweep_id}` and `WS /ws/live` — WebSocket routes are mounted
  without the `/v1` prefix (see [Real-time](#real-time-websocket--sse)).

There is currently only one API version (`v1`); no deprecation policy exists
yet because nothing has been deprecated.

---

## Authentication

Auth is JWT bearer-token based. There is **no email field anywhere** — users
authenticate with `phone_number` + `password`.

```
POST /v1/auth/login
Authorization: (none)
Content-Type: application/json

{ "phone_number": "+254712345678", "password": "correct-horse-battery" }
```

```json
200 OK
{ "access_token": "eyJhbGciOi...", "token_type": "bearer" }
```

Send the token on every subsequent authenticated request:

```
Authorization: Bearer eyJhbGciOi...
```

- Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default **60
  minutes**). There is no refresh-token endpoint — re-login when a token
  expires (a `401` on any call is your signal to do this).
- The JWT payload carries only `sub` (user id) and `role` — the backend
  re-loads the full `User` row from the database on every request, so a
  role change or account deletion takes effect immediately, not just after
  the token expires.
- A logged-in user's own profile: `GET /v1/auth/me`.

### Local dev test accounts

Running against a `docker compose up` instance seeded via
`uv run python -m scripts.seed_db` (or `scripts.seed_demo`, which wraps it)?
One fixed login per role is seeded for you — password `testpass123` for all
three:

| Role | Phone number |
|---|---|
| `admin` | `+254700000001` |
| `analyst` | `+254700000002` |
| `viewer` | `+254700000003` |

Dev-only, fixed rather than random on purpose, never used outside a
`mock`-mode local deployment — see `backend/README.md`'s seeding section.

---

## Roles & access control

Four roles, in `app.domain.enums.UserRole`:

| Role | Meaning |
|---|---|
| `admin` | Full access — user management, subscriber management, all writes. |
| `analyst` | Operational staff — can manage facilities/commodities, trigger sweeps, retry calls, acknowledge/resolve escalations. |
| `viewer` | Read-only access to everything **except** admin-only resources (users, subscribers). |
| `public` | **Not a token** — it means "no `Authorization` header at all." A small set of routes require no auth whatsoever (see below). |

**Every route not explicitly listed as public below requires a valid bearer
token at minimum (`viewer` or higher).** This is a deliberate
data-minimization default: anything that could expose a facility's phone
number or a call transcript requires login.

### Routes that require no token (`public`)

| Route | Notes |
|---|---|
| `POST /v1/sweeps/query` | The public demo path. Rate-limited (see below) since it dials real phones. |
| `GET /v1/sweeps/{sweep_id}` | An anonymous caller must be able to poll the sweep it just started. |
| `GET /v1/sweeps/{sweep_id}/stream` (SSE) | Same reasoning — public, but scoped to one `sweep_id`. |
| `WS /ws/sweeps/{sweep_id}` | Same. |
| `GET /v1/availability-results` | The aggregate/ranked "where can I get X" read surface — never carries a phone number or transcript. |

Every other endpoint requires `Authorization: Bearer <token>`. Where a route
requires more than "any logged-in user," it's called out per-endpoint below
as `analyst+` (admin or analyst) or `admin only`.

### What each failure looks like

| Situation | Status | Body |
|---|---|---|
| No `Authorization` header on a protected route | `401` | `{"detail": "missing bearer token"}` |
| Token malformed, wrong signature, or expired | `401` | `{"detail": "invalid or expired token"}` |
| Token valid but the user account no longer exists (deleted) | `401` | `{"detail": "user no longer exists"}` |
| Token valid, but role isn't allowed for this route | `403` | `{"detail": "insufficient role"}` |

---

## Common conventions

### Pagination

Every list endpoint (`GET /v1/facilities`, `GET /v1/commodities`, etc.) uses
the same **offset/limit** pagination — no cursor-based pagination anywhere.

Query params:

| Param | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | `20` | `1 <= limit <= 100` |
| `offset` | int | `0` | `>= 0` |

Response envelope (identical shape on every list endpoint):

```json
{
  "items": [ /* ... */ ],
  "total": 137,
  "limit": 20,
  "offset": 0
}
```

`total` is the count of matching rows **after filters, before the
limit/offset window** — use it to compute total pages
(`ceil(total / limit)`).

Passing `limit`/`offset` outside their constraints returns a standard `422`
validation error (see [Error reference](#error-reference)).

### IDs

All entity IDs are UUIDv4 strings, e.g. `"3fae2b1e-9c1a-4b2e-8b1a-000000000000"`.
Every path parameter shown as `{id}` below expects one of these.

### Dates & times

- Timestamps (`created_at`, `started_at`, etc.) are ISO 8601 with UTC offset,
  e.g. `"2026-08-23T12:00:00+00:00"`.
- A few fields are plain dates (no time), e.g. `last_restock_date`:
  `"2026-08-01"`.
- `Decimal` fields (`price_kes`) are serialized as **JSON strings**, not
  numbers (e.g. `"120.50"`), to avoid float rounding — parse them as a
  decimal type on the frontend, don't assume `parseFloat` precision is
  sufficient for money.

### Enums on the wire

Every enum field serializes as its lowercase string value (e.g.
`"status": "in_progress"`, not an integer or capitalized label). The full
list of every enum and its values is in the [Enums reference](#enums-reference).

### CORS

`CORSMiddleware` allows the origins listed in `Settings.CORS_ALLOW_ORIGINS`
(defaults to `http://localhost:3000` and `http://localhost:5173` in dev),
with credentials, all methods, and all headers allowed for those origins.
If your frontend dev server runs on a different port, ask a backend dev to
add it to `CORS_ALLOW_ORIGINS`.

---

## Error reference

The API does not use a custom error envelope — it's plain FastAPI/Starlette
behavior, in two shapes:

**1. A raised `HTTPException` (business-logic errors — not found, bad
credentials, role denied, rate limited, etc.)** — `detail` is a **string**:

```json
{ "detail": "facility 3fae2b1e-... not found" }
```

**2. A Pydantic request-validation failure (malformed body/query params —
FastAPI's default handler)** — `detail` is an **array** of field-level
errors:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "name"],
      "msg": "Field required",
      "input": { "type": "public" }
    }
  ]
}
```

**Always check whether `detail` is a string or an array before rendering
it** — a naive `error.detail` render will break on one of the two shapes.

### Status codes used across the API

| Status | Meaning | Where it shows up |
|---|---|---|
| `200` | Success (read, or a write that doesn't create a resource) | Most `GET`/`PATCH` |
| `201` | Resource created | `POST /facilities`, `POST /commodities`, `POST /users`, `POST /subscribers` |
| `202` | Accepted — async work queued, poll for the result | `POST /sweeps/query`, `POST /sweeps/scheduled`, `POST /calls/{id}/retry` |
| `400` | Malformed request the framework can't even parse (e.g. bad JSON body on the webhook route) | Rare on the `/v1` surface; mostly the webhook receiver |
| `401` | Missing/invalid/expired token, or the user behind it no longer exists | Any protected route |
| `403` | Valid token, insufficient role | Any role-gated route |
| `404` | Resource doesn't exist | Any `{id}` lookup, or `POST /sweeps/query` with an unresolvable commodity name |
| `422` | Validation failure — either a malformed request body/query (framework-level) or a domain rule violation (e.g. editing a facility with bad data) | Any `POST`/`PATCH`, plus `GET /analytics/export` missing a required param for the chosen report |
| `429` | Rate limit exceeded | `POST /sweeps/query` only |

---

## Rate limiting

**`POST /v1/sweeps/query`** — and only this endpoint — is rate-limited,
because every call to it dials real phones and costs real money.

- Fixed-window counter, keyed by client IP.
- Default: **10 requests per 60-second window** (`PUBLIC_QUERY_RATE_LIMIT` /
  `PUBLIC_QUERY_RATE_WINDOW_SECONDS` — confirm current values with backend,
  these are configurable per environment).
- On the 11th request within the window:

```
429 Too Many Requests
Retry-After: 43

{ "detail": "rate limit exceeded — try again later" }
```

`Retry-After` is the number of seconds until the window resets — use it to
drive a countdown/backoff in the UI rather than retrying immediately.

The rate limit is independent of the [call engine](#call-engine-onoff-switch)
switch: with the engine **off**, `POST /v1/sweeps/query` is still counted and
can still `429`, it just never places a call when it does get through.

---

## Endpoints

Every response schema below lists field name, type, and nullability exactly
as the backend serializes it (Pydantic `Optional`/`| None` fields are marked
nullable). Every request body's optional fields are marked as such.

### Auth

#### `POST /v1/auth/login`

Public (no token required — this *is* how you get one).

**Body**

| Field | Type | Required |
|---|---|---|
| `phone_number` | string | yes |
| `password` | string | yes |

**200 OK**

```json
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```

**Failure**

| Status | Cause | Body |
|---|---|---|
| `401` | Phone number not found, or password doesn't match | `{"detail": "invalid phone number or password"}` |
| `422` | Missing/malformed body | field-error array |

#### `GET /v1/auth/me`

Any authenticated role.

**200 OK**

```json
{
  "id": "3fae2b1e-...",
  "name": "Jane Analyst",
  "role": "analyst",
  "org": "MOH Kirinyaga",
  "phone_number": "+254712345678"
}
```

`org` and `phone_number` are nullable. `role` is one of `admin` / `analyst` /
`viewer` / `public` (a real user row is never actually `public` — that role
exists on the enum only to name "no token" conceptually).

**Failure:** standard `401` cases from the [Roles & access control](#roles--access-control)
table.

---

### Facilities

Every route requires at least `viewer` — `Facility.phone_number` is always
in the response, so nothing here is public.

#### `GET /v1/facilities`

**Query params** (all optional, combine with AND)

| Param | Type | Notes |
|---|---|---|
| `county` | string | exact match |
| `sub_county` | string | exact match |
| `ward` | string | exact match |
| `type` | enum `FacilityType` | `public` \| `dispensary` \| `private_chemist` \| `faith_based` |
| `source` | enum `FacilitySource` | `kmhfl` \| `manual` \| `crowd` |
| `limit`, `offset` | int | pagination, see [Common conventions](#pagination) |

**200 OK** — `Page<FacilityOut>`

```json
{
  "items": [
    {
      "id": "3fae2b1e-...",
      "name": "Wamumu Dispensary",
      "type": "dispensary",
      "county": "Kirinyaga",
      "sub_county": "Mwea",
      "ward": "Wamumu",
      "gps_lat": -0.6829,
      "gps_lng": 37.3644,
      "phone_number": "+254712345678",
      "source": "kmhfl",
      "kmhfl_code": "12345",
      "operational_status": true,
      "last_verified_at": "2026-07-01T09:00:00+00:00",
      "reliability_score": 0.92,
      "phone_verification_status": "verified"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`kmhfl_code`, `last_verified_at`, `reliability_score` are nullable.
`phone_verification_status` is one of `unverified` / `verified` / `bounced`.

#### `GET /v1/facilities/{facility_id}`

**200 OK** — single `FacilityOut` (same shape as above).

**Failure:** `404 {"detail": "facility <id> not found"}`.

#### `POST /v1/facilities` — `analyst+`

**Body** (`FacilityIn`)

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `type` | enum `FacilityType` | yes |
| `county` | string | yes |
| `sub_county` | string | yes |
| `ward` | string | yes |
| `gps_lat` | float | yes |
| `gps_lng` | float | yes |
| `phone_number` | string | yes |
| `kmhfl_code` | string \| null | no |

**201 Created** — `FacilityOut`.

**Failure**

| Status | Cause |
|---|---|
| `403` | Caller is `viewer` (or unauthenticated) |
| `422` | Domain validation failure (e.g. invalid phone format) — `{"detail": "<message>"}`, or malformed body — field-error array |

#### `PATCH /v1/facilities/{facility_id}` — `analyst+`

**Body** (`FacilityEditIn`) — every field optional, only supplied fields
change:

`name`, `type`, `county`, `sub_county`, `ward`, `gps_lat`, `gps_lng`,
`phone_number`, `kmhfl_code`, `operational_status` (bool).

**200 OK** — updated `FacilityOut`.

**Failure:** `404` if the facility doesn't exist, `422` on a domain
validation failure, `403` if not `analyst+`.

#### `POST /v1/facilities/{facility_id}/verify-phone` — `analyst+`

Marks a facility's phone as verified/unverified/bounced after a manual check
call.

**Body**

```json
{ "status": "verified" }
```

`status` is one of `unverified` / `verified` / `bounced`.

**200 OK** — updated `FacilityOut` (`phone_verification_status` reflects the
new value).

**Failure:** `404` if facility doesn't exist, `403` if not `analyst+`.

---

### Commodities

Every route requires at least `viewer`.

#### `GET /v1/commodities`

**Query params** (all optional)

| Param | Type | Notes |
|---|---|---|
| `category` | enum `CommodityCategory` | `essential_medicine` \| `vaccine` \| `supply` |
| `is_priority_watchlist` | bool | filter to/exclude watchlist commodities |
| `search` | string | **fuzzy match against name or any alias** — e.g. `search=PPH drug` can match a commodity aliased to "carbetocin" |
| `limit`, `offset` | int | pagination |

**200 OK** — `Page<CommodityOut>`

```json
{
  "items": [
    {
      "id": "8b1a2b1e-...",
      "name": "Carbetocin",
      "category": "essential_medicine",
      "keml_code": "KEML-0231",
      "aliases": ["PPH drug", "Pabal"],
      "is_priority_watchlist": true
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### `GET /v1/commodities/{commodity_id}`

**200 OK** — single `CommodityOut`. **Failure:** `404`.

#### `POST /v1/commodities` — `admin only`

**Body** (`CommodityIn`)

| Field | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes | — |
| `category` | enum | yes | — |
| `keml_code` | string \| null | no | `null` |
| `aliases` | string[] | no | `[]` |
| `is_priority_watchlist` | bool | no | `false` |

**201 Created** — `CommodityOut`. **Failure:** `403` if not `admin`.

#### `PATCH /v1/commodities/{commodity_id}` — `admin only`

**Body** (`CommodityEditIn`) — all optional: `name`, `category`,
`keml_code`, `aliases`.

**200 OK** — updated `CommodityOut`. **Failure:** `404`, `403`.

#### `PATCH /v1/commodities/{commodity_id}/watchlist` — `admin only`

**Body**

```json
{ "is_priority_watchlist": true }
```

**200 OK** — updated `CommodityOut`. **Failure:** `404`, `403`.

---

### Sweeps

A "sweep" is one round of parallel calls to a set of facilities for one
commodity in one geography. This is the core of the product.

#### `POST /v1/sweeps/query` — **public, rate-limited**

The public on-demand query path — "is Commodity X available in Geography
Y?" Triggers real (or, in `mock` mode, simulated) outbound calls.

**Body** (`SweepQueryIn`)

```json
{
  "commodity": "carbetocin",
  "geography": { "kind": "county", "county": "Kirinyaga" }
}
```

- `commodity` (string, required) — **either a commodity UUID, or a
  name/alias to fuzzy-match** (e.g. `"PPH drug"`). The backend tries to
  parse it as a UUID first; if that fails, it searches by name/alias and
  uses the first match.
- `geography` (object, required) — a **discriminated union** on the `kind`
  field. Exactly one of the following five shapes:

| `kind` | Extra fields | Meaning |
|---|---|---|
| `"county"` | `county: string` | every facility in a county |
| `"sub_county"` | `sub_county: string` | every facility in a sub-county |
| `"ward"` | `ward: string` | every facility in a ward |
| `"radius"` | `lat: float, lng: float, radius_km: float` | every facility within N km of a point |
| `"nearest_n"` | `lat: float, lng: float, n: int` | the N nearest facilities to a point |

**202 Accepted**

```json
{ "sweep_id": "3fae2b1e-9c1a-4b2e-8b1a-000000000000" }
```

Poll `GET /v1/sweeps/{sweep_id}` with this id, or connect to
`WS /ws/sweeps/{sweep_id}` / `GET /v1/sweeps/{sweep_id}/stream` for live
updates instead of polling — see [Real-time](#real-time-websocket--sse).

If the [call engine](#call-engine-onoff-switch) is **off**, you still get a
`202` and a real `sweep_id`, but that sweep is already `completed` on the
first read: `status: "completed"`, `total_calls: 0`, `matches: []`. The UI
should surface this ("calling is paused") rather than spinning forever.

**Failure**

| Status | Cause | Body |
|---|---|---|
| `404` | `commodity` doesn't match any id, name, or alias | `{"detail": "no commodity matching 'xyz'"}` |
| `422` | Malformed `geography` (unknown `kind`, missing field for that kind) or malformed body | field-error array |
| `429` | Rate limit exceeded (see [Rate limiting](#rate-limiting)) | `{"detail": "rate limit exceeded — try again later"}`, `Retry-After` header |

#### `GET /v1/sweeps/{sweep_id}` — public

Sweep detail + live progress + ranked in-stock matches. This is the
endpoint the public query flow polls (or use the WS/SSE stream instead).

**200 OK** — `SweepOut`

```json
{
  "sweep_id": "3fae2b1e-...",
  "status": "in_progress",
  "total_calls": 12,
  "commodity_id": "8b1a2b1e-...",
  "geography_scope": { "kind": "county", "county": "Kirinyaga" },
  "trigger_type": "on_demand",
  "created_at": "2026-08-23T11:55:00+00:00",
  "requester_id": null,
  "counts_by_status": { "queued": 8, "in_progress": 0, "completed": 4 },
  "matches": [
    {
      "facility_id": "9c1a2b1e-...",
      "facility_name": "Wamumu Dispensary",
      "distance_meters": 1240.5,
      "price_kes": "90.00",
      "can_hold": true,
      "hold_reference_code": null,
      "confidence": 0.87
    }
  ]
}
```

- `status` — `queued` \| `in_progress` \| `completed`.
- `counts_by_status` — only includes `CallStatus` values with at least one
  call; a status with zero calls is **absent from the object**, not present
  with value `0`.
- `matches` — the sweep's **in-stock** results, ranked by distance then
  confidence (PROJECT.md's "where can I get X" ranking). Empty until at
  least one facility has reported stock. `distance_meters` is `null` for a
  `county`/`sub_county`/`ward`-scoped sweep (no single reference point to
  measure from) — only populated for `radius`/`nearest_n` scopes.
- `price_kes` is a **string**, not a number (see [Common conventions](#dates--times)).
- Poll this endpoint until `status` is `"completed"`, or use the WS/SSE
  stream to avoid polling.

**Failure:** `404 {"detail": "sweep <id> not found"}`.

#### `GET /v1/sweeps` — `analyst+`

The full sweep history (not part of the public surface — `GET /v1/sweeps/{id}`
above is what an anonymous caller gets).

**Query params** (all optional)

| Param | Type | Notes |
|---|---|---|
| `commodity_id` | UUID | exact match |
| `geography` | string | **substring match** against the sweep's `geography_scope` JSON (e.g. a county/ward name) — not scope-kind aware |
| `status` | enum `SweepStatus` | `queued` \| `in_progress` \| `completed` |
| `date_from`, `date_to` | ISO datetime | inclusive range on `created_at` |
| `limit`, `offset` | int | pagination |

**200 OK** — `Page<SweepSummaryOut>` (note: **no `matches` or
`counts_by_status`** on the list view — those are only computed on the
single-sweep detail endpoint, to avoid an expensive per-row query on every
list call):

```json
{
  "items": [
    {
      "id": "3fae2b1e-...",
      "commodity_id": "8b1a2b1e-...",
      "geography_scope": { "kind": "county", "county": "Kirinyaga" },
      "trigger_type": "on_demand",
      "status": "completed",
      "requester_id": null,
      "created_at": "2026-08-23T11:55:00+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

**Failure:** `403` if not `analyst+`.

#### `POST /v1/sweeps/scheduled` — `analyst+`

Registers/runs a recurring watchlist sweep (same body shape as
`POST /sweeps/query`). Not rate-limited (it's not public), still
role-gated.

**Body:** identical to `POST /sweeps/query`'s `SweepQueryIn`.

**202 Accepted:** `{"sweep_id": "..."}`. Same [call-engine](#call-engine-onoff-switch)
behavior as `POST /sweeps/query` when calling is off (sweep created already
`completed`, no calls placed).

**Failure:** same `404`/`422` cases as `POST /sweeps/query`, plus `403` if
not `analyst+`. (No `429` — this route has no rate limit.)

---

### Calls

Every route requires at least `viewer` — responses include transcript and
recording URLs.

#### `GET /v1/calls`

**Query params:** `limit`, `offset` only (no filtering by sweep/facility on
this endpoint currently — filter client-side by `sweep_id`/`facility_id` if
needed, or use `GET /v1/sweeps/{sweep_id}` which already groups calls by
sweep via `counts_by_status`).

**200 OK** — `Page<CallOut>`

```json
{
  "items": [
    {
      "id": "1a2b3c4d-...",
      "sweep_id": "3fae2b1e-...",
      "facility_id": "9c1a2b1e-...",
      "status": "completed",
      "attempt_number": 1,
      "started_at": "2026-08-23T11:58:00+00:00",
      "ended_at": "2026-08-23T12:00:00+00:00",
      "transcript_url": "https://...",
      "recording_url": "https://..."
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`status` is one of `queued` \| `in_progress` \| `completed` \| `failed` \|
`canceled` \| `no_answer` \| `voicemail`. `started_at`, `ended_at`,
`transcript_url`, `recording_url` are all nullable (null until the call
actually starts/ends/is transcribed).

#### `GET /v1/calls/{call_id}`

**200 OK** — single `CallOut`. **Failure:** `404`.

#### `POST /v1/calls/{call_id}/retry` — `analyst+`

Manual "call this facility now" — e.g. reconfirming a hold before a patient
travels there. **Important:** this creates a **new, single-facility sweep**
(not a retry of the original call in place) — the response's `sweep_id` is
a different id than the original call's `sweep_id`. This is also the one
documented bypass of the facility call-cooldown window — a human explicitly
asked for it.

**202 Accepted**

```json
{ "sweep_id": "7d8e9f0a-..." }
```

Poll/subscribe to this new `sweep_id` the same way as any other sweep.

**Failure:** `404` if `call_id` (or the facility/commodity it references)
doesn't exist, `403` if not `analyst+`.

When the [call engine](#call-engine-onoff-switch) is **off**, this still
returns `202` with a `sweep_id`, but the new sweep is created already
`completed` with `total_calls: 0` — no call is placed.

---

### Call engine (on/off switch)

A single global kill switch for **all** outbound calling. When it's **off**,
nothing dials — `POST /v1/sweeps/query`, `POST /v1/sweeps/scheduled`,
`POST /v1/calls/{id}/retry`, and the scheduled/retry background jobs all still
run and create their `Sweep` row, but that sweep is created already
`completed` with `total_calls: 0`, `counts_by_status: {}`, and `matches: []`.
No CALL-E request is made and no call credits are spent.

Use it to keep the system idle between demos and only turn calling on for a
controlled window (ideally with a TTL so it can't be left on by accident).

- The state is **global** (not per-sweep), shared by the API and the
  background workers, and held in Redis so it survives a restart.
- The boot default is `CALLS_ENABLED_DEFAULT` (ships **off**); once any
  enable/disable call is made, that explicit state wins until changed.
- Reading the state requires any authenticated role; changing it is
  `analyst+`.

**`CallEngineState` shape** (returned by all three endpoints):

```json
{
  "enabled": false,
  "expires_at": "2026-08-30T12:20:00+00:00",
  "default_enabled": false
}
```

- `enabled` — whether calls are currently allowed.
- `expires_at` — ISO timestamp when an enable-with-TTL will auto-revert to
  disabled, or `null` (disabled, or enabled with no TTL).
- `default_enabled` — the `CALLS_ENABLED_DEFAULT` boot fallback, for display.

#### `GET /v1/call-engine`

Any authenticated role. **200 OK** — `CallEngineState`.

#### `POST /v1/call-engine/enable` — `analyst+`

**Body** (optional — omit for "on until explicitly disabled")

```json
{ "ttl_seconds": 1200 }
```

`ttl_seconds` (int, `1..86400`) auto-disables the engine after that many
seconds. Out of range → `422`.

**200 OK** — `CallEngineState` (`enabled: true`).

#### `POST /v1/call-engine/disable` — `analyst+`

No body. **200 OK** — `CallEngineState` (`enabled: false`).

**Failure (enable/disable):** `401` no token, `403` if not `analyst+`.

---

### Availability Results

**Public** — the ranked "where can I get X" read surface. Never includes a
facility phone number or call transcript.

#### `GET /v1/availability-results`

**Query params** (all optional)

| Param | Type | Notes |
|---|---|---|
| `commodity_id` | UUID | exact match |
| `county` | string | exact match |
| `date_from`, `date_to` | ISO datetime | inclusive range on `created_at` |
| `in_stock` | enum `StockStatus` | `yes` \| `no` \| `unknown` |
| `limit`, `offset` | int | pagination |

**200 OK** — `Page<AvailabilityResultOut>`

```json
{
  "items": [
    {
      "id": "5e6f7a8b-...",
      "call_id": "1a2b3c4d-...",
      "facility_id": "9c1a2b1e-...",
      "commodity_id": "8b1a2b1e-...",
      "in_stock": "yes",
      "quantity_band": "medium",
      "price_kes": "120.50",
      "last_restock_date": "2026-08-01",
      "can_hold": true,
      "hold_duration_hours": 24,
      "hold_reference_code": "HOLD-4471",
      "confidence": 0.87,
      "notes": "Confirmed 2 boxes in stock, expiring 2027-01.",
      "created_at": "2026-08-23T12:00:00+00:00"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

All of `quantity_band`, `price_kes`, `last_restock_date`, `can_hold`,
`hold_duration_hours`, `hold_reference_code`, `confidence`, `notes` are
nullable — a call that produced a low-confidence or partial answer won't
populate all of them.

---

### Escalations

Stockout alerts raised when a sweep completes with in-stock coverage at or
below the scarcity threshold. Every route requires at least `viewer`;
acknowledge/resolve are `analyst+` (a `Subscriber` has no login of its own —
a logged-in analyst relays the action on their behalf).

#### `GET /v1/escalations`

**Query params** (all optional)

| Param | Type | Notes |
|---|---|---|
| `commodity_id` | UUID | exact match |
| `status` | enum `EscalationStatus` | `open` \| `acknowledged` \| `resolved` |
| `severity` | enum `EscalationSeverity` | `low` \| `medium` \| `high` \| `critical` |
| `geography` | string | substring match |
| `limit`, `offset` | int | pagination |

**200 OK** — `Page<StockoutAlertOut>`

```json
{
  "items": [
    {
      "id": "2b3c4d5e-...",
      "commodity_id": "8b1a2b1e-...",
      "geography": { "kind": "county", "county": "Kirinyaga" },
      "severity": "high",
      "facilities_checked_count": 10,
      "facilities_with_stock_count": 0,
      "triggered_at": "2026-08-23T12:00:00+00:00",
      "status": "open",
      "acknowledgment_note": null
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### `POST /v1/escalations/{escalation_id}/acknowledge` — `analyst+`

**Body** (optional — omit entirely for no note)

```json
{ "note": "Dispatching a supply run to Kirinyaga today." }
```

**200 OK** — updated `StockoutAlertOut` (`status` becomes `"acknowledged"`,
`acknowledgment_note` set if provided).

**Failure:** `404`, `403`.

#### `POST /v1/escalations/{escalation_id}/resolve` — `analyst+`

Same body shape as acknowledge. **200 OK** — updated `StockoutAlertOut`
(`status` becomes `"resolved"`).

**Failure:** `404`, `403`.

---

### Subscribers

Admin-managed contacts who receive stockout alerts (SMS/email/webhook) — a
`Subscriber` is distinct from a `User`: a subscriber receives alerts, a user
logs in. Read requires `viewer`+; writes require `admin`.

#### `GET /v1/subscribers`

**200 OK** — `Page<SubscriberOut>`

```json
{
  "items": [
    {
      "id": "6f7a8b9c-...",
      "name": "Kirinyaga County Pharmacist",
      "org": "MOH Kirinyaga",
      "phone": "+254712345678",
      "email": null,
      "webhook_url": null,
      "watchlist_commodities": ["8b1a2b1e-..."],
      "watchlist_geography": { "kind": "county", "county": "Kirinyaga" },
      "notification_channel": "sms"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

`notification_channel` is one of `sms` \| `email` \| `webhook` — determines
which of `phone`/`email`/`webhook_url` is expected to be populated (not
enforced by the schema itself, so validate on the frontend form before
submit).

#### `GET /v1/subscribers/{subscriber_id}`

**200 OK** — single `SubscriberOut`. **Failure:** `404`.

#### `POST /v1/subscribers` — `admin only`

**Body** (`SubscriberIn`)

| Field | Type | Required | Default |
|---|---|---|---|
| `name` | string | yes | — |
| `notification_channel` | enum | yes | — |
| `org` | string \| null | no | `null` |
| `phone` | string \| null | no | `null` |
| `email` | string \| null | no | `null` |
| `webhook_url` | string \| null | no | `null` |
| `watchlist_commodities` | UUID[] | no | `[]` |
| `watchlist_geography` | object | no | `{}` |

**201 Created** — `SubscriberOut`. **Failure:** `403` if not `admin`.

#### `PATCH /v1/subscribers/{subscriber_id}` — `admin only`

**Body** (`SubscriberEditIn`) — all fields from `SubscriberIn`, all
optional.

**200 OK** — updated `SubscriberOut`. **Failure:** `404`, `403`.

---

### Users (admin)

Every route here is **`admin only`** — this manages login accounts.

#### `GET /v1/users`

**200 OK** — `Page<UserOut>` (see the shape under [`GET /v1/auth/me`](#get-v1authme)
— never includes `password_hash`).

#### `POST /v1/users` — `admin only`

**Body** (`UserCreateIn`)

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `role` | enum `UserRole` | yes |
| `phone_number` | string | yes |
| `password` | string | yes |
| `org` | string \| null | no (default `null`) |

**201 Created** — `UserOut`.

**Failure:** `403` if caller isn't `admin`, `422` on malformed body.

#### `GET /v1/users/{user_id}`

**200 OK** — `UserOut`. **Failure:** `404`, `403`.

#### `PATCH /v1/users/{user_id}` — `admin only`

**Body** (`UserEditIn`) — all optional: `name`, `role`, `org`,
`phone_number`, `password` (sending `password` sets a new one; it's never
returned in any response).

**200 OK** — updated `UserOut`. **Failure:** `404`, `403`.

---

### Analytics

Read-only, derived from `Sweep`/`Call`/`AvailabilityResult` data — nothing
here mutates state. Gated to `viewer`+ (aggregate data, not raw
operational data with a phone number/transcript).

#### `GET /v1/analytics/stockout-rate`

Time-series stockout rate for one commodity, optionally scoped to a
geography, bucketed by period.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `commodity_id` | UUID | **yes** | — |
| `geography` | string | no | substring match, same semantics as elsewhere |
| `date_from`, `date_to` | ISO datetime | no | range filter |
| `granularity` | enum | no, default `"week"` | `"week"` \| `"month"` (see `BucketGranularity`) |

**200 OK** — `StockoutAnalyticsOut`

```json
{
  "commodity_id": "8b1a2b1e-...",
  "commodity_name": "Carbetocin",
  "geography": "Kirinyaga",
  "granularity": "week",
  "buckets": [
    {
      "period_start": "2026-08-03",
      "sweep_count": 4,
      "stockout_sweep_count": 1,
      "stockout_rate": 0.25
    }
  ],
  "current_streak": 2,
  "longest_streak": 5,
  "summary": "Stockout rate has improved over the last 4 weeks."
}
```

`current_streak`/`longest_streak` count consecutive stockout-buckets
(business meaning: how many periods in a row this commodity has been
scarce in this geography).

**Failure:** `404` if `commodity_id` doesn't exist, `422` if `commodity_id`
is missing, `403` if unauthenticated/insufficient role.

#### `GET /v1/analytics/facility-reliability`

**Query params:** `facility_id` (UUID, optional — omit to get every
facility's reliability score).

**200 OK** — `list[FacilityReliabilityOut]` (**not paginated** — a plain
JSON array, not the `Page<T>` envelope):

```json
[
  {
    "facility_id": "9c1a2b1e-...",
    "total_calls": 42,
    "completed_calls": 38,
    "answer_rate": 0.905,
    "avg_result_confidence": 0.81,
    "reliability_score": 0.87
  }
]
```

`avg_result_confidence` is nullable (no completed calls with a confidence
score yet).

#### `GET /v1/analytics/watchlist-trends`

Compares watchlist-commodity stockout trends across multiple counties.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `county` | string, repeatable | **yes, at least one** | e.g. `?county=Kirinyaga&county=Nairobi` |

**200 OK** — `WatchlistTrendsOut`

```json
{
  "rows": [
    {
      "commodity_id": "8b1a2b1e-...",
      "commodity_name": "Carbetocin",
      "county": "Kirinyaga",
      "sweep_count": 12,
      "stockout_sweep_count": 3,
      "stockout_rate": 0.25
    }
  ],
  "ranked_commodity_ids": ["8b1a2b1e-..."]
}
```

`ranked_commodity_ids` is every distinct commodity in `rows`, ordered
worst-stockout-rate-first — use it to drive a sorted commodity picker
without re-sorting `rows` client-side.

**Failure:** `422` if `county` is omitted entirely.

#### `GET /v1/analytics/export`

Exports one of the three analytics reports above as a downloadable file.

**Query params**

| Param | Type | Required | Notes |
|---|---|---|---|
| `report` | enum | **yes** | `"stockout-rate"` \| `"facility-reliability"` \| `"watchlist-trends"` |
| `format` | enum | no, default `"csv"` | `"csv"` \| `"pdf"` |
| `commodity_id` | UUID | **required if `report=stockout-rate`** | — |
| `geography`, `date_from`, `date_to`, `granularity` | — | no | same as `stockout-rate` above, only used when `report=stockout-rate` |
| `facility_id` | UUID | no | only used when `report=facility-reliability`; omit for "all facilities" |
| `county` | string, repeatable | **required if `report=watchlist-trends`** | same as `watchlist-trends` above |

**200 OK** — raw file bytes.

- `Content-Type`: `text/csv` or `application/pdf` depending on `format`.
- `Content-Disposition: attachment; filename="<report>.<ext>"` — the
  browser/`fetch` client should respect this for a "download" UX rather
  than rendering the response inline.

This is **not** JSON — don't try to `response.json()` it; use
`response.blob()` (or equivalent) and trigger a file save.

**Failure**

| Status | Cause |
|---|---|
| `404` | `commodity_id` given but doesn't exist |
| `422` | Missing the report-specific required param (e.g. `report=stockout-rate` with no `commodity_id`, or `report=watchlist-trends` with no `county`) — `{"detail": "commodity_id is required to export the stockout-rate report"}` |

---

### Health check

#### `GET /healthz`

No auth, no `/v1` prefix.

**200 OK**

```json
{ "status": "ok" }
```

Use for uptime checks / "is the API reachable" probes — not a dependency
health check (it doesn't verify DB/Redis connectivity).

---

## Real-time (WebSocket / SSE)

Three routes, **mounted without the `/v1` prefix**. Full per-event-type
payload documentation lives in [`realtime-contract.md`](./realtime-contract.md)
— this is the summary you need to decide which route to use.

| Route | Protocol | Auth | Scope |
|---|---|---|---|
| `WS /ws/sweeps/{sweep_id}` | WebSocket | none (public) | one sweep |
| `GET /v1/sweeps/{sweep_id}/stream` | SSE (`text/event-stream`) | none (public) | one sweep |
| `WS /ws/live?county=&commodity_id=&token=` | WebSocket | JWT via `token` query param (browsers can't set custom headers on a WS handshake) | one county+commodity pair |

**Use the sweep stream (WS or SSE, your choice) instead of polling
`GET /v1/sweeps/{sweep_id}`** once you have a `sweep_id` — it's the same
data pushed live, with no polling-interval tradeoff.

### Envelope

Every message on every route — snapshots and live events alike — shares one
envelope:

```json
{
  "v": 1,
  "type": "call.status_changed",
  "sweep_id": "3fae2b1e-...",
  "data": { "...": "..." },
  "ts": "2026-08-23T12:00:00+00:00"
}
```

`sweep_id` is `null` only for `geography.snapshot` (not scoped to one
sweep). `v` only increments on a breaking change — new event types and new
`data` fields are added without a version bump, so don't fail hard on an
unrecognized `type` or an unrecognized field inside `data`.

### Event types quick reference

| `type` | Fired when | Channel(s) |
|---|---|---|
| `sweep.snapshot` | Once, on connect (WS `/ws/sweeps/{id}`) or as the first SSE frame | — |
| `call.status_changed` | A `Call` row is updated | `sweep:{id}`, `geo:{county}:{commodity_id}` |
| `availability_result.created` | An `AvailabilityResult` row is created/updated | same two |
| `sweep.progress` | `Sweep.status` transitions to anything but `completed` | `sweep:{id}` |
| `sweep.completed` | `Sweep.status` transitions to `completed` — terminal event, nothing more follows on that channel | `sweep:{id}` |
| `geography.snapshot` | Once, on connect to `/ws/live` | — |
| `alert.created` / `alert.updated` | A stockout alert is created/status-changed | `alerts` (no dedicated client route subscribes to this yet — see `realtime-contract.md`'s deferred section) |

For exact `data` payload shapes per event type, see
[`realtime-contract.md`](./realtime-contract.md#live-event-types).

### Connection failure behavior

- `WS /ws/sweeps/{sweep_id}` closes with code `4404` if `sweep_id` doesn't
  exist.
- `WS /ws/live` closes with code `4401` if the `token` query param is
  missing/invalid/expired, or `4403` if the token is valid but the user's
  role isn't `viewer`+.
- The SSE route (`GET /v1/sweeps/{sweep_id}/stream`) returns a normal `404`
  (not a stream) if `sweep_id` doesn't exist, since the failure happens
  before the stream opens.
- Neither WS route auto-reconnects — that's the client's responsibility on
  disconnect. On reconnect, you'll get a fresh snapshot as the first
  message, so no special "resume" logic is needed — just re-render from the
  new snapshot and keep consuming live events.

---

## Enums reference

Every enum in the API, exactly as it serializes on the wire (lowercase
string).

| Enum | Values |
|---|---|
| `UserRole` | `admin`, `analyst`, `viewer`, `public` |
| `FacilityType` | `public`, `dispensary`, `private_chemist`, `faith_based` |
| `FacilitySource` | `kmhfl`, `manual`, `crowd` |
| `PhoneVerificationStatus` | `unverified`, `verified`, `bounced` |
| `CommodityCategory` | `essential_medicine`, `vaccine`, `supply` |
| `SweepTrigger` | `on_demand`, `scheduled` |
| `SweepStatus` | `queued`, `in_progress`, `completed` |
| `CallStatus` | `queued`, `in_progress`, `completed`, `failed`, `canceled`, `no_answer`, `voicemail` |
| `StockStatus` | `yes`, `no`, `unknown` |
| `EscalationSeverity` | `low`, `medium`, `high`, `critical` |
| `EscalationStatus` | `open`, `acknowledged`, `resolved` |
| `NotificationChannel` | `sms`, `email`, `webhook` |
| Geography scope `kind` | `county`, `sub_county`, `ward`, `radius`, `nearest_n` |
| Analytics `granularity` | `week`, `month` |
| Export `report` | `stockout-rate`, `facility-reliability`, `watchlist-trends` |
| Export `format` | `csv`, `pdf` |

---

## End-to-end example: the public query flow

This is the flow the public-facing "where can I get X" screen is built on
— no login required.

1. **Kick off a query.**

   ```
   POST /v1/sweeps/query
   { "commodity": "carbetocin", "geography": { "kind": "county", "county": "Kirinyaga" } }
   ```

   → `202 { "sweep_id": "3fae2b1e-..." }`. Watch for `429` here and surface
   the `Retry-After` value if the user is hammering the button.

2. **Open a live connection immediately** (don't wait for the first poll):

   ```
   new EventSource(`/v1/sweeps/3fae2b1e-.../stream`)
   ```

   or

   ```
   new WebSocket(`ws://localhost:8000/ws/sweeps/3fae2b1e-...`)
   ```

3. **Render the first message** (`type: "sweep.snapshot"`) immediately —
   it's the same shape as `GET /v1/sweeps/{sweep_id}`, so you can reuse one
   render function for both the initial snapshot and any later REST
   fallback fetch.

4. **Update the UI on each subsequent event**:
   - `call.status_changed` → tick a per-facility "calling.../answered/no
     answer" indicator.
   - `availability_result.created` → append/update a row in the ranked
     results list as each facility's answer comes in, live.
   - `sweep.progress` → update an overall progress bar
     (`counts_by_status` / `total_calls`).
   - `sweep.completed` → stop showing a spinner; this is the last event on
     the channel — close the connection.

5. **If the connection drops** (network blip, tab backgrounded), reconnect
   to the same stream URL — you'll get a fresh `sweep.snapshot` reflecting
   current state, so there's no gap to reconcile manually.

6. **Fallback / no-WebSocket path:** poll `GET /v1/sweeps/{sweep_id}` on an
   interval (a few seconds) until `status === "completed"`, reading
   `matches` for the ranked in-stock results — this returns the exact same
   data the stream pushes, just pulled instead of pushed.
