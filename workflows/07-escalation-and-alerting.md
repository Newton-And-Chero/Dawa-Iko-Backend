# Sprint 07 — Escalation & Alerting (Stockout Detection)

> Preconditions: Sprint 04 (sweep results exist), Sprint 06 (event bus exists, for pushing alert events live).

## Goal & Definition of Done

A completed sweep with zero (or below-threshold) availability automatically creates a severity-classified `StockoutAlert`, matched to subscribers watching that geography/commodity, dispatched via SMS (Twilio, real + mock adapter) and webhook, with acknowledge/resolve tracking. A successful on-demand query also immediately returns a patient-facing match (facility, distance, price, hold reference) — this half doesn't need new infrastructure, it's a response-shaping concern on top of Sprint 04/05's existing query path, built here because it's conceptually part of "alerting the right result to the right person."

## Preconditions

- `Sweep`, `AvailabilityResult`, `StockoutAlert`, `Subscriber` entities/repositories (01).
- Sweep completion logic (04). Real-time event bus (06).

## Architecture for this sprint

```
app/application/ports/
  notifier_port.py            # NotifierPort(ABC): async def send(channel, recipient, message, metadata) -> NotificationResult

app/infrastructure/notifications/
  twilio_sms_adapter.py        # TwilioSmsAdapter(NotifierPort) — SMS via Twilio REST API
  mock_sms_adapter.py            # MockSMSAdapter(NotifierPort) — logs instead of sending
  webhook_notifier.py              # WebhookNotifier(NotifierPort) — POSTs to a subscriber's registered webhook_url
  email_notifier.py                  # (simple SMTP or provider-agnostic adapter; same pattern)

app/domain/services/
  severity.py                  # (already exists from Sprint 01 — used here, not redefined)
  subscriber_matching.py         # pure function: match_subscribers(alert, subscribers) -> list[Subscriber]

app/application/use_cases/
  detect_stockout.py             # on sweep completion: evaluate threshold, create StockoutAlert if crossed
  dispatch_escalation.py           # StockoutAlert -> matched subscribers -> NotifierPort per subscriber's channel
  acknowledge_escalation.py          # subscriber marks "redistributing stock" / free-text note
  resolve_escalation.py                # subscriber marks resolved
  build_patient_match_response.py        # on-demand query's in-stock results -> ranked, patient-facing shape
```

## Task checklist

- [ ] `NotifierPort` — one method, `send(channel: NotificationChannel, recipient, message, metadata)`, so SMS/email/webhook are interchangeable from the caller's perspective (the concrete adapter chosen per `Subscriber.notification_channel`).
- [ ] `TwilioSmsAdapter` — real Twilio SMS integration (Twilio's REST API directly via `httpx`, no `twilio` package), reading `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`/`TWILIO_FROM_NUMBER` from `Settings`. Honours `SMS_DEMO_REDIRECT_NUMBERS` (the notification-side mirror of `CALL_DEMO_REDIRECT_NUMBERS`): when set, every SMS is fanned out to those verified numbers instead of the subscriber.
- [ ] `MockSMSAdapter` — logs the message (structured log line, and optionally persists to a `sent_notifications` table/list for test assertions) instead of sending; selected via `Settings.SMS_MODE=mock|live`, mock by default per `RULES.md`.
- [ ] `WebhookNotifier` — POSTs a JSON payload to a subscriber's `webhook_url` (if that's their chosen channel), with a reasonable timeout and no retry storm (a small number of retries with backoff, then give up and log — a failed subscriber webhook must never block other subscribers' notifications).
- [ ] `domain/services/subscriber_matching.py` — pure function matching a `StockoutAlert`'s commodity+geography against each `Subscriber.watchlist_commodities`/`watchlist_geography`, unit-testable with no DB.
- [ ] `detect_stockout.py` — hooked into sweep-completion (extend the same place Sprint 04's sweep-status-flip logic lives, don't create a second "sweep finished" trigger point): compute `facilities_with_stock_count / facilities_checked_count`; if at/below `Settings.STOCKOUT_THRESHOLD_PCT` (default matches PROJECT.md's "0% or below-threshold %"), call `domain/services/severity.py` (from Sprint 01) with commodity priority tier + facility density, create a `StockoutAlert` row, publish an `alert.created` event on the Sprint 06 event bus.
- [ ] `dispatch_escalation.py` — given a new `StockoutAlert`, run `subscriber_matching`, then call `NotifierPort.send()` once per matched subscriber via their preferred channel, recording delivery outcome.
- [ ] `acknowledge_escalation.py` / `resolve_escalation.py` — state-transition use cases (`EscalationStatus: open → acknowledged → resolved`), publish `alert.updated` events on the event bus.
- [ ] `build_patient_match_response.py` — given a completed (or in-progress, partially-completed) sweep's `AvailabilityResult`s, return the in-stock subset ranked (in-stock first, then by confidence/distance per PROJECT.md 2.7), each with facility name, distance, price, hold reference — this is what Sprint 05's `GET /sweeps/{id}` (and Sprint 06's WS stream) should already be shaping via `AvailabilityResult` filtering; this sprint makes that ranking explicit and reusable rather than ad hoc per endpoint.
- [ ] Extend Sprint 05's routers: `POST /escalations/{id}/acknowledge`, `POST /escalations/{id}/resolve` (subscriber/analyst role), `GET /escalations` (filter by status/severity/geography/commodity, paginated).
- [ ] Extend Sprint 05's subscriber schemas into a real router: `GET/POST/PATCH /subscribers` (admin-managed, or self-service if a subscriber has a `User` account — decide based on whether `Subscriber` and `User` are meant to be the same identity or separate per PROJECT.md's data model, which lists them as distinct entities — keep them distinct, a `Subscriber` need not have login access).
- [ ] Unit tests: `subscriber_matching.py` (pure), `detect_stockout.py` threshold/severity logic (using the existing `severity.py` tests as a base, extended for the full detect flow), `MockSMSAdapter`-backed `dispatch_escalation.py` integration test asserting the right subscribers get the right channel.

## API / data contract additions

- `POST /escalations/{id}/acknowledge`, `POST /escalations/{id}/resolve`, `GET /escalations` (extends Sprint 05's placeholder schemas with real data).
- `GET/POST/PATCH /subscribers`.
- New event types on the Sprint 06 bus: `alert.created`, `alert.updated` (additive, `v` stays 1).
- `GET /sweeps/{id}` response gains a `matches` field (or equivalent) carrying `build_patient_match_response`'s ranked in-stock list — an additive field, not a breaking change to Sprint 05's existing shape.

## Rules specific to this sprint

- **DO** trigger `detect_stockout` from the same code path that already flips `Sweep.status` to `completed` in Sprint 04 — don't add a second sweep-completion listener that could drift out of sync with the first.
- **DO NOT** let one subscriber's failed notification (bad phone number, webhook timeout) block or fail notifications to other matched subscribers — dispatch is per-subscriber, failures are isolated and logged, not exception-propagated across the batch.
- **DO** default `SMS_MODE=mock` everywhere except an explicit production-like environment, per `RULES.md` — no automated test or default dev run sends a real SMS.
- **DO NOT** conflate `Subscriber` and `User` — PROJECT.md's data model keeps them separate; a subscriber is someone who receives alerts, a user is someone who logs into the system, and a person can be both without those being the same row.

## Testing requirements

- `detect_stockout` unit tests cover: threshold crossed → alert created with correct severity; threshold not crossed → no alert; zero facilities checked → no alert (not a false-positive stockout).
- `dispatch_escalation` integration test with `MockSMSAdapter` + `WebhookNotifier` (against a local test HTTP endpoint) confirms both channels are exercised correctly per subscriber preference, and one subscriber's simulated failure doesn't block another's delivery.
- `build_patient_match_response` unit test confirms correct ranking (in-stock first, then by the documented tiebreaker).
- Full test suite (Sprints 00-07) still green.

## Explicitly deferred

- Analytics/trend views over alert history — Sprint 08.
- Two-way SMS (subscriber replying to an alert via SMS) — explicitly out of scope per PROJECT.md §6.
