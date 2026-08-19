# Sprint 06 — Real-Time Layer (WebSocket/SSE)

> Preconditions: Sprint 05 complete (REST contract exists); Sprint 03/04's webhook-driven writes exist.

## Goal & Definition of Done

Any client watching a sweep, or subscribed to a geography/commodity, receives live updates as `Call`/`AvailabilityResult` rows change — without polling — via WebSocket, with an SSE fallback for the simpler "stream this one sweep's results" case. The event contract is versioned and documented so a future frontend (out of scope for now, but explicitly the reason this sprint exists per the project's real-time requirement) can be built against it without backend changes.

## Preconditions

- Redis available (Sprint 00). Webhook handler (Sprint 03) and sweep status transitions (Sprint 04) exist as the events' source of truth.

## Architecture for this sprint

```
app/infrastructure/realtime/
  event_bus.py              # RealtimeEventBus: publish(channel, event) / subscribe(channel) over Redis pub/sub
  channels.py                 # channel naming: sweep:{sweep_id}, geo:{county}:{commodity_id}, alerts (Sprint 07 hooks in later)

app/api/v1/websocket/
  sweep_ws.py                 # WS  /ws/sweeps/{sweep_id}
  geography_ws.py               # WS  /ws/live?county=...&commodity_id=...
  connection_manager.py           # tracks active connections per channel, handles disconnect cleanup

app/api/v1/routers/
  sweeps_sse.py                 # GET /sweeps/{sweep_id}/stream  (SSE, text/event-stream)

docs/ (or workflows/ subsection)
  realtime-contract.md            # versioned message schema reference
```

Why Redis pub/sub and not an in-process broadcaster: the webhook that produces an event may be handled by any Celery worker or any API process (once this runs with more than one uvicorn worker), while the WS client is connected to one specific API process. Redis pub/sub is the one piece of shared infrastructure every process already has (per the Sprint 00 architecture decision), so it's the fan-out point — publish once, every subscribed process delivers to its own connected clients.

## Task checklist

- [ ] `RealtimeEventBus.publish(channel, event: dict)` — serializes to JSON, `PUBLISH`es to the Redis channel.
- [ ] `RealtimeEventBus.subscribe(channel)` — async generator yielding parsed events from a Redis `SUBSCRIBE`, one per WS/SSE connection's background listener task.
- [ ] Define the **event envelope** (versioned): `{"v": 1, "type": "call.status_changed" | "sweep.progress" | "sweep.completed" | "availability_result.created", "sweep_id": ..., "data": {...}, "ts": "<iso8601>"}`. Every event type's `data` shape is documented in `docs/realtime-contract.md`.
- [ ] Wire event publication into the places that already produce state changes — **don't duplicate logic**, just add a `bus.publish(...)` call at the end of: `handle_calle_webhook` (Sprint 03, on each `Call`/`AvailabilityResult` write), `run_on_demand_sweep`/sweep-status-flip logic (Sprint 04, on `Sweep.status` transitions).
- [ ] `connection_manager.py` — tracks which WS connections are subscribed to which channel(s); on webhook-sourced Redis message, pushes to every matching local connection; cleans up on disconnect (no leaked subscriptions).
- [ ] `WS /ws/sweeps/{sweep_id}` — on connect, subscribes to `sweep:{sweep_id}`; on disconnect, unsubscribes; sends a snapshot of current sweep progress immediately on connect (so a client joining mid-sweep isn't stuck waiting for the next event) followed by live events.
- [ ] `WS /ws/live?county=&commodity_id=` — subscribes to a geography/commodity channel for the live dashboard use case (PROJECT.md 2.7's "live availability map... updating in real time"); same connect-snapshot-then-stream pattern.
- [ ] `GET /sweeps/{sweep_id}/stream` (SSE) — same underlying event source as the sweep WS route, for clients that only need one-directional streaming (PROJECT.md 2.6 lists both WS and SSE as acceptable).
- [ ] Auth on WS/SSE routes: same JWT scheme as REST, passed as a query param or subprotocol header (WS can't send custom headers from a browser without a subprotocol trick — document which approach is used and why) for authenticated channels; the public sweep-progress stream for a `POST /sweeps/query`-triggered sweep can be unauthenticated (matching that endpoint's own public access) but only exposes that specific sweep's data, not the live geography feed.
- [ ] `docs/realtime-contract.md` — every event type, its `data` shape, and a note that `v` will increment on any breaking change (additive fields don't bump it).
- [ ] Integration tests using FastAPI's `TestClient` WS support: connect, trigger a mock CALL-E webhook that would produce an event, assert the event arrives on the WS connection with the correct shape; test disconnect cleanup (no error/leak when a client drops mid-sweep); test SSE endpoint delivers the same events in `text/event-stream` format.

## API / data contract additions

- `WS /ws/sweeps/{sweep_id}`, `WS /ws/live`, `GET /sweeps/{sweep_id}/stream` (SSE) — documented in `docs/realtime-contract.md` alongside the REST OpenAPI doc from Sprint 05.
- Event envelope schema as above — this is the actual contract a frontend will consume; keep it stable once sprints past this point start depending on it (Sprint 07's escalation alerts will add an `alert.created`/`alert.updated` event type here, additively).

## Rules specific to this sprint

- **DO** publish events from the existing use cases/handlers that already write the state change — this sprint adds a `bus.publish()` call at each existing write point, it does not invent a second parallel path that also writes `AvailabilityResult` rows.
- **DO NOT** let the WS/SSE layer query the database directly for anything beyond the initial connect-time snapshot — live updates flow through the event bus, not through the WS handler polling the DB in a loop.
- **DO** version the event envelope from day one (`"v": 1`) even though there's only one version right now — this is what lets Sprint 07 add alert events without breaking anything already built against this contract.
- **DO NOT** fan out every event to every connection — a connection only receives events for the channel(s) it explicitly subscribed to (`sweep:{id}` or `geo:{county}:{commodity}`), never a global firehose.

## Testing requirements

- WS connect → mock webhook → event received, correct envelope shape, matches the REST `GET /sweeps/{id}` state at the same point in time (no drift between the polled and pushed views).
- Disconnect mid-sweep does not error the server or leak the Redis subscription (assert subscriber count returns to baseline after disconnect).
- SSE endpoint test asserts correct `Content-Type: text/event-stream` and event framing.
- Load-shape sanity check (not a full load test — that's Sprint 09): N concurrent WS connections to the same `sweep_id` all receive the same event exactly once.

## Explicitly deferred

- Escalation/alert event types — Sprint 07 adds `alert.*` events to this same bus, additively.
- Any client/frontend implementation — out of scope for this backend-only roadmap.
- Horizontal-scaling load testing beyond the sanity check above — Sprint 09.
