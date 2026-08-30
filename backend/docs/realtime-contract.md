# Real-Time Event Contract

Sprint 06's contract: every event a WS/SSE client can receive. This is the
API surface a future frontend builds against — treat changes to it the same
way as a REST breaking change.

## Transport

| Route | Protocol | Auth | Scope |
|---|---|---|---|
| `WS /ws/sweeps/{sweep_id}` | WebSocket | none (public) | one sweep |
| `GET /v1/sweeps/{sweep_id}/stream` | SSE (`text/event-stream`) | none (public) | one sweep |
| `WS /ws/live?county=&commodity_id=&token=` | WebSocket | JWT, `token` query param | one county+commodity pair |

The sweep WS/SSE routes are deliberately unauthenticated, mirroring
`POST /v1/sweeps/query`'s own public access: an anonymous caller triggers a
sweep and must be able to watch its own `sweep_id` without a token. Each
route only ever exposes the one `sweep_id` already in its URL — never the
full sweep list and never the geography feed.

`/ws/live` requires at least a `viewer` token (RULES.md's data-minimization
default) because it aggregates availability data across every commodity in a
county, not one caller's own query.

### Why a query param for `/ws/live`'s JWT, not a header or subprotocol

A browser's native `WebSocket` API cannot set custom headers on the
handshake request, so the REST routes' `Authorization: Bearer <token>`
header can't be reused as-is. The two documented workarounds are encoding
the token into `Sec-WebSocket-Protocol` (a subprotocol trick) or passing it
as a query parameter. This contract uses the query parameter: it needs no
subprotocol negotiation on either side and every WS client library supports
a plain query string, at the cost of the token appearing in server access
logs — acceptable here since it's a short-lived JWT, not a long-lived
credential.

## Versioning

Every message on every route — both pushed live events and connect-time
snapshots — uses the same envelope, and `v` is incremented only on a
breaking change to that envelope or to an existing event type's `data`
shape. Adding a new event type, or a new field to an existing `data` shape,
does not bump `v` — Sprint 07's `alert.*` events, and `SweepOut`'s new
`matches` field, were both added this way.

## Envelope

```json
{
  "v": 1,
  "type": "call.status_changed",
  "sweep_id": "3fae2b1e-...-000000000000",
  "data": { "...": "..." },
  "ts": "2026-08-23T12:00:00+00:00"
}
```

- `v` — envelope schema version, currently `1`.
- `type` — one of the event types below.
- `sweep_id` — the sweep the event originated from. `null` only for
  `geography.snapshot` (see below), which isn't scoped to one sweep.
- `data` — event-type-specific payload, documented per type below.
- `ts` — ISO 8601 UTC timestamp of when the event was published (not
  necessarily when the underlying state change was committed).

## Live event types

Published by `app/application/realtime_events.py`, called from the
use cases that already own the write: `HandleCalleWebhookUseCase` (on each
`Call`/`AvailabilityResult` write, and on each `StockoutAlert` it detects or
`AcknowledgeEscalationUseCase`/`ResolveEscalationUseCase` update) and every
sweep-status-flip site (`_sweep_dispatch.dispatch_sweep`,
`RetryFailedCallsUseCase`, `RequestManualCallUseCase`).

### `call.status_changed`

Published to `sweep:{sweep_id}` and `geo:{county}:{commodity_id}` (the
call's facility's county, the sweep's commodity) whenever a `Call` row is
updated from a CALL-E webhook.

```json
{
  "call_id": "...",
  "facility_id": "...",
  "status": "completed",
  "attempt_number": 1,
  "started_at": "2026-08-23T11:58:00+00:00",
  "ended_at": "2026-08-23T12:00:00+00:00"
}
```

`status` is one of `Call.status`'s values (`queued`, `in_progress`,
`completed`, `failed`, `canceled`, `no_answer`, `voicemail`).

### `availability_result.created`

Published to the same two channels whenever an `AvailabilityResult` row is
created or updated (a redelivered webhook updates the existing row rather
than creating a duplicate — the event still fires with the refreshed data).

```json
{
  "id": "...",
  "call_id": "...",
  "facility_id": "...",
  "commodity_id": "...",
  "in_stock": "yes",
  "quantity_band": "medium",
  "price_kes": "120.50",
  "last_restock_date": "2026-08-01",
  "can_hold": true,
  "hold_duration_hours": 24,
  "confidence": 0.87
}
```

Field semantics mirror `AvailabilityResult` (Sprint 01) exactly, except
`hold_reference_code` and `notes` are omitted here — this event exists for
the live map/query view, not the detail drill-down. `price_kes` is a
JSON string (not a number) to avoid float rounding on the wire; parse it as
a decimal.

### `sweep.progress`

Published to `sweep:{sweep_id}` only, whenever `Sweep.status` transitions to
anything other than `completed` (currently: `queued` -> `in_progress`).

```json
{
  "status": "in_progress",
  "total_calls": 12,
  "counts_by_status": { "queued": 8, "in_progress": 0, "completed": 4 }
}
```

`counts_by_status` only includes statuses with at least one `Call` — a
status with zero calls is simply absent, not `0`.

### `sweep.completed`

Same shape as `sweep.progress`, published to `sweep:{sweep_id}` when
`Sweep.status` transitions to `completed`. `status` is always `"completed"`.
This is the terminal event for a sweep — no further events publish to its
channel afterward.

> **Call engine off / empty sweep.** When the global call-engine switch is
> off (see `api.md` → "Call engine"), or when every candidate facility is
> filtered out by cooldown, a sweep goes straight from `queued` to
> `completed` without ever dispatching a call. On its channel you get the
> `sweep.snapshot` then a single `sweep.completed` with `total_calls: 0`,
> `counts_by_status: {}`, and (in the snapshot) `matches: []` — **no**
> `sweep.progress`, `call.status_changed`, or `availability_result.created`
> events. Treat `sweep.completed` as terminal regardless of whether any call
> events preceded it.

### `alert.created`

Published to the `alerts` channel (see below) whenever `DetectStockoutUseCase`
creates a new `StockoutAlert`. `sweep_id` is `null` — an alert outlives the
one sweep that triggered it and is identified by its own `id`.

```json
{
  "id": "...",
  "commodity_id": "...",
  "geography": { "kind": "county", "county": "Kirinyaga" },
  "severity": "high",
  "facilities_checked_count": 10,
  "facilities_with_stock_count": 0,
  "status": "open",
  "triggered_at": "2026-08-23T12:00:00+00:00"
}
```

`geography` is a `GeographyScope` dict (Sprint 01), copied verbatim from the
sweep that triggered the alert. `severity` is one of `EscalationSeverity`'s
values (`low`, `medium`, `high`, `critical`); `status` one of
`EscalationStatus`'s (`open`, `acknowledged`, `resolved`).

### `alert.updated`

Same shape as `alert.created`, published to the `alerts` channel whenever
`AcknowledgeEscalationUseCase`/`ResolveEscalationUseCase` transitions a
`StockoutAlert`'s status.

## Connect-time snapshots

Sent once, immediately after a WS connection is accepted (or as the first
SSE frame), so a client joining mid-sweep isn't stuck waiting for the next
live event. Not part of the live event stream above, but framed in the same
envelope for a single client-side parser.

### `sweep.snapshot`

Sent on `WS /ws/sweeps/{sweep_id}` connect and as the first SSE frame on
`GET /v1/sweeps/{sweep_id}/stream`. `data` is the same shape as the REST
`GET /v1/sweeps/{sweep_id}` response (`SweepOut`, Sprint 05):

```json
{
  "sweep_id": "...",
  "status": "in_progress",
  "total_calls": 12,
  "commodity_id": "...",
  "geography_scope": { "kind": "county", "county": "Kirinyaga" },
  "trigger_type": "on_demand",
  "created_at": "2026-08-23T11:55:00+00:00",
  "requester_id": null,
  "counts_by_status": { "queued": 8, "completed": 4 },
  "matches": [
    {
      "facility_id": "...",
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

`matches` (Sprint 07) is the sweep's in-stock `AvailabilityResult`s ranked by
distance then confidence (`build_patient_match_response`, PROJECT.md 2.5/2.7)
— empty until at least one facility reports stock. `distance_meters` is
`null` for a county/sub_county/ward-scoped sweep, which has no single
reference point to measure from.

### `geography.snapshot`

Sent on `WS /ws/live` connect. `sweep_id` is `null` — this snapshot
aggregates results across every sweep that has touched the county+commodity
pair, not one sweep. `data`:

```json
{
  "county": "Kirinyaga",
  "commodity_id": "...",
  "results": [ /* AvailabilityResultOut items, Sprint 05 shape, ranked
                 in-stock-first / most-confident-first */ ]
}
```

## Channels (internal — not part of the client-facing contract)

`app/infrastructure/realtime/channels.py`:

- `sweep:{sweep_id}` — every event about one sweep.
- `geo:{county}:{commodity_id}` — `call.status_changed` and
  `availability_result.created` events fanned out from whichever sweep(s)
  touched that county+commodity pair.
- `alerts` — `alert.created`/`alert.updated` events (Sprint 07). Not scoped
  to a county/commodity/sweep — every subscriber-facing consumer of alerts
  reads this one channel and filters client-side.

## Explicitly deferred

- A dedicated `WS`/`SSE` route for streaming `alerts` live (Sprint 07 only
  adds the channel and event types; no route subscribes to it yet — see
  workflows/07's checklist, which scopes this sprint to detection/dispatch,
  not a new transport).
- Any client/frontend implementation.
