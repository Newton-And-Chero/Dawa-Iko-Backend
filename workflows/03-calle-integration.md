# Sprint 03 — CALL-E Voice Integration Layer

> Preconditions: Sprint 01 complete (`Call`, `AvailabilityResult` entities/repositories exist).

## Goal & Definition of Done

A `CallProviderPort` exists with two adapters — `CallEAdapter` (real, talks to the actual CALL-E API) and `MockCallEAdapter` (simulates realistic responses, zero network calls) — selected by `CALL_E_MODE`. A webhook receiver endpoint accepts CALL-E's terminal call events, validates them defensively (CALL-E signs nothing), and turns them into persisted `Call`/`AvailabilityResult` rows. Nothing in this sprint decides *which* facilities to call or *when* (that's Sprint 04's sweep engine) — this sprint is the reusable "place a batch call and receive its structured result" capability on its own.

## Reference: what CALL-E's API actually looks like

(Confirmed by fetching `docs.heycall-e.com` and its OpenAPI spec directly — re-verify against those live docs before implementation if any detail below seems off, don't guess.)

- **`POST /v1/calls`** — creates one asynchronous call *task*. Body:
  - `task` (string, required) — natural-language instruction for the whole call.
  - `recipients` (array, required for our use) — each `{phones: [E.164 string], region: "KE", locale: "en-US"}`. **One call task can carry many recipients — this is how a sweep's "parallel calls to N facilities" is expressed as a single API call, not N separate ones.**
  - `result_schema` (JSON Schema, optional) — task-level structured extraction.
  - `recipient_result_schema` (JSON Schema, optional) — **per-recipient** structured extraction. This is what maps directly onto `AvailabilityResult`'s fields.
  - `webhook_url` (URI, optional) — where CALL-E POSTs the terminal event for this call task.
  - `metadata` (object, optional) — our own correlation data (e.g. `{"sweep_id": "..."}`).
  - Header: `Idempotency-Key` (1-255 chars, optional but **we always send one**).
- **Response / `GET /v1/calls/{call_id}`** — a `CallTask`: `id` (`call_...`), `status` (`queued|in_progress|completed|failed|canceled`), `structured_result`, `task_completed`, `completion_confidence{score,label}`, `recipients[]` (each with its own `id`, `phones`, `status`, `structured_result`, `summary`, `attempts[]` with transcript turns), `created_at`, `completed_at`.
- **Webhook**: `POST` to our `webhook_url` with header `CALL-E-Event-Id: evt_...` and body `{id, type, created_at, data: <CallTask>}`. `type` ∈ `call.completed | call.failed | call.result_validation_failed`. Fired once, when the whole call task reaches a terminal state (i.e. once **all** recipients are done, not per-recipient).
- **No webhook signature exists.** CALL-E's own docs state there is no HMAC secret and no `CALL-E-Signature` header. The only built-in check is `CALL-E-Event-Id` matching the body's `id`.
- **Auth**: `Authorization: Bearer <CALLE_API_KEY>`.
- **Python SDK**: `calle-ai` (`pip install calle-ai` → `uv add calle-ai`), `CalleClient(api_key=...)`.
- **Region/language**: Kenya (`KE`) is supported for outbound calling; **English only**, no Swahili. Set `locale="en-US"` (or CALL-E's documented Kenya-English locale code — confirm exact string against current docs) for every Kenyan recipient. Do not build any Swahili branch.
- **No documented max on `recipients` per task.** Treat this as unknown and unbounded-at-our-peril: chunk defensively (Sprint 04 owns the chunking policy; this sprint's adapter just accepts however many recipients it's given in one call to `place_call`).
- Error codes worth handling explicitly: `unsupported_region`, `unsupported_language`, `invalid_phone`, `no_recipients`, `result_schema_invalid`, `recipient_result_schema_invalid`, `rate_limit_exceeded`, `idempotency_conflict`, `provider_unavailable`.

## Architecture for this sprint

```
app/application/ports/
  call_provider_port.py       # CallProviderPort(ABC):
                                #   async def place_call(task, recipients, result_schema,
                                #                          recipient_result_schema, webhook_url,
                                #                          idempotency_key, metadata) -> CallTaskRef
                                #   async def get_call(call_id) -> CallTaskRef
                                #   async def list_call_events(call_id) -> list[CallEventRef]

app/domain/
  call_schemas.py               # the fixed recipient_result_schema as a Python dict/JSON Schema,
                                  # STOCK_CHECK_RESULT_SCHEMA, and the task prompt template
  value_objects/call_task_ref.py # CallTaskRef, CallEventRef — framework-free mirrors of CALL-E's shapes

app/infrastructure/call_e/
  calle_adapter.py              # CallEAdapter(CallProviderPort) — wraps calle-ai SDK
  mock_calle_adapter.py          # MockCallEAdapter(CallProviderPort) — simulates responses in-process

app/api/v1/routers/
  webhooks.py                    # POST /webhooks/calle/{webhook_token}

app/application/use_cases/
  handle_calle_webhook.py         # validates event, upserts Call + AvailabilityResult rows

app/core/
  webhook_security.py              # generates/validates the per-deployment webhook_token
```

## Task checklist

- [ ] `domain/call_schemas.py` — define `STOCK_CHECK_RESULT_SCHEMA` as JSON Schema matching PROJECT.md §2.4's fixed question set → `AvailabilityResult` fields: `in_stock` (enum `yes|no|unknown`), `quantity_band` (enum, nullable), `price_kes` (number, nullable), `last_restock_date` (string date, nullable), `can_hold` (boolean, nullable), `hold_duration_hours` (number, nullable), `notes` (string, nullable). Include an `unknown`/nullable path for every field per CALL-E's own best-practice guidance ("use enums with an `unknown` value for unclear outcomes") — an uncertain answer must be extractable as `unknown`, never guessed.
- [ ] Also define the **task prompt template** (the `task` string sent to CALL-E) implementing PROJECT.md §2.4's opening + branching: identify as an independent availability-monitoring service (not MOH/KEMSA), state purpose in one sentence, ask the fixed question set, branch on in-stock/out-of-stock/uncertain. This is a single well-crafted prompt (CALL-E's agent handles the live conversational branching itself — we are not building our own decision-tree/DTMF engine, we are instructing CALL-E's agent what to do and what to extract).
- [ ] `CallProviderPort` — three async methods as above, operating on `CallTaskRef`/`CallEventRef` domain value objects (not raw CALL-E SDK types — keep the SDK's shapes out of `application/`).
- [ ] `CallEAdapter` — implements the port using the `calle-ai` SDK (or raw `httpx` + bearer auth if the SDK proves inconvenient for async/webhook-driven flows — decide and note the reason in the adapter's module docstring). Maps CALL-E error codes to typed exceptions in `core/exceptions.py` (e.g. `UnsupportedRegionError`, `RateLimitExceededError`).
- [ ] `MockCallEAdapter` — on `place_call`, synchronously (or after a short simulated delay via `asyncio.sleep`) generates a plausible `CallTaskRef` with randomized-but-weighted per-recipient results (mostly `in_stock=yes/no`, a smaller share `unknown`/no-answer), stores it in-memory keyed by a generated `call_...` id, and — critically — **also fires the same webhook POST our own receiver would get from real CALL-E**, so the mock exercises the exact same webhook code path as production. This is what makes the whole pipeline demoable without spending money.
- [ ] `core/webhook_security.py` — generate a per-deployment random token at startup (or read from `Settings.WEBHOOK_TOKEN`, generated once and stored in `.env`), used to build `webhook_url = f"{PUBLIC_BASE_URL}/webhooks/calle/{token}"` on every `place_call`, and to validate inbound requests carry the matching path segment.
- [ ] `api/v1/routers/webhooks.py` — `POST /webhooks/calle/{webhook_token}`:
  1. Reject (404, to avoid confirming the endpoint exists to a guesser) if `webhook_token` doesn't match `Settings.WEBHOOK_TOKEN`.
  2. Reject (400) if `CALL-E-Event-Id` header is missing or doesn't equal `body.id`.
  3. Reject (409, and log) if `body.data.id` (the `call_id`) isn't a `call_id` we have persisted in `queued`/`in_progress` state — never blindly trust an unknown call id.
  4. Deduplicate on event id (store processed event ids; a re-delivery is a no-op 200, not reprocessed).
  5. Delegate to `handle_calle_webhook` use case; return `200 {"ok": true}`.
- [ ] `use_cases/handle_calle_webhook.py` — given a validated `CallTask` snapshot: update the `Call` row's status; for each recipient, upsert an `AvailabilityResult` row (mapping `structured_result` fields, `unknown`/null → `StockStatus.unknown`, attaching `completion_confidence.score` as `confidence`); store `transcript_url`/`recording_url` if present; for `call.result_validation_failed`, mark the affected result `confidence=0`, `notes` flagged for human review, rather than silently dropping it.
- [ ] Unit tests for `MockCallEAdapter` (covers the full place→webhook round trip in-process), `handle_calle_webhook` (covers all three event types, including the validation-failure path), and `webhooks.py`'s rejection cases (bad token, mismatched event id, unknown call id, duplicate event).

## API / data contract additions

- `POST /webhooks/calle/{webhook_token}` — inbound only, not part of the public API surface, undocumented in any future OpenAPI spec exposed to consumers.
- No outward-facing endpoints yet (sweep-triggering endpoints are Sprint 05).

## Rules specific to this sprint

- **DO** keep the fixed question set as data (`STOCK_CHECK_RESULT_SCHEMA` + the prompt template), not scattered string literals — Sprint 04 will need to select commodity-specific variants later (PROJECT.md's stretch cold-chain/expiry questions) by extending this same structure, not duplicating it.
- **DO NOT** let `CallEAdapter` leak `calle-ai` SDK types or raw HTTP response dicts past its own module — everything above it works with `CallTaskRef`/`CallEventRef`.
- **DO** make `MockCallEAdapter` fire a real webhook HTTP request to our own running server (not an in-process function call) when running against the dev server, so the webhook route itself is exercised end-to-end, not bypassed. In unit tests, it's fine to call the use case directly.
- **DO NOT** trust `body.data.status` on a webhook to represent current truth without the DB-state check in step 3 above — a forged or duplicate request must not be able to flip a `Call` we never dispatched.
- **DO NOT** implement DTMF/IVR branching logic ourselves. CALL-E's agent handles live conversational branching from the `task` prompt; our job is prompt + schema + result-parsing, not a call-tree engine.

## Testing requirements

- `MockCallEAdapter` round-trip test: `place_call()` with N recipients → webhook fires → `AvailabilityResult` rows exist for all N facilities, statuses correctly mapped.
- Webhook route tests cover every rejection path (wrong token → 404; missing/mismatched event id → 400; unknown call id → 409; replayed event id → 200 no-op, no duplicate `AvailabilityResult`).
- `result_validation_failed` handling test: result is stored with `confidence=0` and flagged, not silently discarded, not crashing the handler.
- If `CALL_E_MODE=live` is exercised at all this sprint, it is **only** via a manually-run, explicitly-flagged smoke script (not CI, not `pytest`), per `RULES.md`.

## Explicitly deferred

- Deciding which facilities to call, geography resolution, chunking a large candidate list into multiple call tasks, retry-on-no-answer scheduling → Sprint 04.
- Commodity-specific question variants (cold-chain, expiry) → stretch, structure left open in `call_schemas.py` but not built now.
- Transcript/recording playback UI → out of scope (backend-only; storage/retrieval only).
