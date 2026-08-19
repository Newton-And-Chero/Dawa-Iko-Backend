# Sprint 04 — Sweep Orchestration Engine

> Preconditions: Sprint 02 (facility directory + geography data exist), Sprint 03 (`CallProviderPort` + webhook pipeline exist) complete.

## Goal & Definition of Done

Given a commodity + geography, the system can resolve a candidate facility list, dispatch it to CALL-E (chunked as needed) as one or more call tasks, track sweep progress through to completion, retry no-answers/failures within limits, and never call the same facility more than once per a configurable cooldown window. Both on-demand and scheduled (Celery Beat) triggers work. Still no HTTP routes exposed publicly (Sprint 05 wraps this in the public query endpoint) — this sprint proves the orchestration use cases work end-to-end against `MockCallEAdapter`.

## Preconditions

- `Facility`/`Commodity` repositories and seed data (Sprint 02).
- `CallProviderPort`, `MockCallEAdapter`, webhook pipeline (Sprint 03).
- `Sweep`/`Call` entities and repositories (Sprint 01).

## Architecture for this sprint

```
app/application/ports/
  geography_resolver_port.py   # GeographyResolverPort(ABC): resolve(geography_scope) -> list[Facility]

app/infrastructure/geo/
  postgis_geography_resolver.py # PostGISGeographyResolver(GeographyResolverPort)
                                  # county/sub_county/ward exact match; radius-from-point via
                                  # ST_DWithin; nearest-N via ST_Distance ORDER BY ... LIMIT N

app/domain/value_objects/
  geography_scope.py             # GeographyScope: county|sub_county|ward|radius|nearest_n variants
  call_list_policy.py              # pure functions: prioritize(facilities, intent) -> ordered list
                                     #                 chunk(facilities, max_per_task) -> list[list[Facility]]
                                     #                 is_cooldown_blocked(facility, now, window) -> bool

app/application/use_cases/
  run_on_demand_sweep.py          # commodity + geography -> resolve -> throttle-filter -> chunk ->
                                    # dispatch via CallProviderPort -> persist Sweep + Call rows -> return sweep_id
  run_scheduled_sweep.py            # same, triggered by Celery Beat for a watchlist commodity+geography pair
  retry_failed_calls.py               # scans Calls in no_answer/failed within retry window, re-dispatches
                                        # respecting attempt cap and time-of-day variation
  get_sweep_status.py                   # sweep_id -> progress (N called / N total, breakdown by status)
  request_manual_call.py                  # single facility, single commodity, immediate — "call this now"

app/workers/
  sweep_tasks.py                    # Celery tasks wrapping the use cases above
  beat_schedule.py                    # Celery Beat schedule: recurring watchlist sweeps

app/infrastructure/db/repositories/  (extended, not new files)
  call_repository.py                 # + get_last_call_for_facility(facility_id) -> Call | None
  sweep_repository.py                  # + update_status, get_progress_counts
```

## Task checklist

- [ ] `GeographyScope` value object with four variants matching PROJECT.md §2.2: `county`, `sub_county`, `ward`, `radius(lat, lng, radius_km)`, and `nearest_n(lat, lng, n)`. (Modeled as a tagged union / discriminated dataclass, not five separate loosely-related fields.)
- [ ] `PostGISGeographyResolver` — implements each variant as a query against `Facility.location` (GIST-indexed from Sprint 01): exact-match filters for county/sub_county/ward; `ST_DWithin` for radius; `ST_Distance` order-by + `LIMIT` for nearest-N.
- [ ] `call_list_policy.prioritize()` — pure function ordering candidates: by distance (when geography has a point reference), then public-before-private or vice versa per an `intent` parameter (PROJECT.md 2.2's "order by ... public facilities before private chemists, or vice versa per query intent").
- [ ] `call_list_policy.chunk()` — pure function splitting a candidate list into groups of at most `Settings.MAX_RECIPIENTS_PER_TASK`, preserving priority order across chunks.
- [ ] `call_list_policy.is_cooldown_blocked()` — pure function: given a facility's last call time and `Settings.FACILITY_CALL_COOLDOWN_HOURS`, returns whether it must be excluded from this sweep's candidate list.
- [ ] `run_on_demand_sweep.py`:
  1. Resolve candidates via `GeographyResolverPort`.
  2. Filter out cooldown-blocked facilities (via `call_repository.get_last_call_for_facility`).
  3. Prioritize + chunk.
  4. Create the `Sweep` row (`status=queued`, `trigger_type=on_demand`).
  5. For each chunk, call `CallProviderPort.place_call()` with `recipient_result_schema=STOCK_CHECK_RESULT_SCHEMA` (Sprint 03), `webhook_url` built from `webhook_security`, `Idempotency-Key = f"{sweep_id}:{chunk_index}"`, `metadata={"sweep_id": ...}`.
  6. Create one `Call` row per facility in the chunk (`status=queued`), linking `sweep_id`/`facility_id`/`attempt_number=1`.
  7. Set `Sweep.status=in_progress`; return `sweep_id` immediately — **the caller does not block on CALL-E finishing** (that's the whole point of the webhook-driven design; Sprint 05's public endpoint returns `sweep_id` for polling/streaming per PROJECT.md 2.6).
- [ ] `run_scheduled_sweep.py` — same core logic, `trigger_type=scheduled`, triggered by a Celery Beat entry per watchlist commodity × geography pair (configured in `beat_schedule.py`, e.g. weekly per PROJECT.md's "sweep carbetocin across Kirinyaga weekly" example).
- [ ] Extend `handle_calle_webhook` (Sprint 03) — when a `Call`'s terminal status lands, update `Sweep.status` to `completed` once every `Call` in that sweep is terminal (a Celery task or the webhook handler itself checks and flips sweep status).
- [ ] `retry_failed_calls.py` — a Celery Beat-scheduled task: finds `Call` rows in `no_answer`/`failed` whose `attempt_number < Settings.MAX_CALL_ATTEMPTS` and whose original attempt is older than a configurable retry delay; re-dispatches each as a **new** single-recipient (or re-batched) call task with `attempt_number += 1`, varying retry timing (e.g. don't retry at the same hour of day as the failed attempt) per PROJECT.md 2.2.
- [ ] `get_sweep_status.py` — returns counts by `Call.status` for a sweep, for polling (Sprint 05 exposes this over HTTP; Sprint 06 pushes it over WS).
- [ ] `request_manual_call.py` — single-facility immediate dispatch (e.g. reconfirm a hold), bypassing sweep grouping but still going through cooldown/idempotency rules — except an explicit manual call is allowed to bypass the cooldown window (a human deliberately asked for it), which must be a documented, explicit override, not a silent bypass.
- [ ] Unit tests for `call_list_policy.py` (pure, no DB): prioritization order, chunking boundary conditions (exact multiple, remainder, single item), cooldown blocking.
- [ ] Integration tests for `run_on_demand_sweep` against `MockCallEAdapter` + seeded facilities: verify chunking triggers correctly when candidate count exceeds `MAX_RECIPIENTS_PER_TASK`, verify cooldown exclusion, verify `Sweep`/`Call` rows are created correctly, verify sweep status transitions to `completed` once mock webhooks land.
- [ ] Integration test for `retry_failed_calls`: a mock `no_answer` result gets a second attempt; exceeding `MAX_CALL_ATTEMPTS` stops retrying and the `Call` stays `failed`.

## API / data contract additions

None exposed over HTTP yet (Sprint 05). Internal contract fixed this sprint: `GeographyScope`, `run_on_demand_sweep(commodity_id, geography, requester_id) -> sweep_id`, `get_sweep_status(sweep_id) -> SweepProgress` — these signatures are what Sprint 05's routers call directly.

## Rules specific to this sprint

- **DO** keep `call_list_policy.py` pure (no DB, no CALL-E) — prioritization, chunking, and cooldown-check logic must be unit-testable without a database.
- **DO NOT** block the on-demand use case on CALL-E completing — it dispatches and returns a `sweep_id`; completion is observed via the webhook pipeline from Sprint 03, exactly as PROJECT.md 2.6 specifies ("triggers a sweep, returns a `sweep_id` for polling/streaming").
- **DO** make `MAX_RECIPIENTS_PER_TASK`, `FACILITY_CALL_COOLDOWN_HOURS`, and `MAX_CALL_ATTEMPTS` `Settings`-driven, not hardcoded — these are exactly the kind of operational knobs that need tuning without a code change once real calling costs are observed.
- **DO NOT** let `request_manual_call`'s cooldown bypass become a general escape hatch — it's one specific use case (reconfirm before a patient travels) called deliberately by a human action, not something the sweep engine reaches for on its own.
- **DO NOT** implement any notification/escalation logic here even though "sweep completed with 0% in stock" is adjacent — that's Sprint 07's job; this sprint only tracks sweep/call status, it doesn't decide what to do about the results.

## Testing requirements

- All items in the checklist's test bullets pass.
- A test proves a sweep whose candidate count exceeds `MAX_RECIPIENTS_PER_TASK` produces multiple `place_call` invocations with distinct idempotency keys, and all resulting `Call` rows still belong to the same `Sweep`.
- A test proves calling `run_on_demand_sweep` twice in immediate succession for the same commodity+geography does not call a facility that's within its cooldown window on the second run.

## Explicitly deferred

- Stockout detection / alerting on sweep results → Sprint 07.
- Exposing any of this over REST/WebSocket → Sprints 05, 06.
- Commodity-specific question variants per facility type → stretch, not this sprint.
