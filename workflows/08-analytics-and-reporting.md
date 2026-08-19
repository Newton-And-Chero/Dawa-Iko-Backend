# Sprint 08 — Analytics & Reporting

> Preconditions: Sprints 01-07 complete — this sprint only reads data other sprints already produce; it writes nothing new to the core domain.

## Goal & Definition of Done

The accumulated sweep history (the project's actual differentiator, per PROJECT.md §0: "a persisted data point that, accumulated over repeated sweeps, becomes a time series") is queryable as stockout frequency/duration analytics, facility reliability scores, and priority-watchlist trends, with CSV/PDF export. This sprint is read-model/reporting only — it must not introduce a second way to write `AvailabilityResult` or `Sweep` data.

## Preconditions

- `AvailabilityResult`/`Sweep`/`Call`/`StockoutAlert` data exists and accumulates from Sprints 04 and 07 (both mock-driven, per Sprint 09's demo seed script pre-running multiple sweeps so this sprint has real time-series data to query against).

## Architecture for this sprint

```
app/application/use_cases/
  compute_stockout_analytics.py    # per commodity+geography: stockout rate/frequency/duration over a date range
  compute_facility_reliability.py    # per facility: answer rate, historical report accuracy -> reliability_score
  compute_watchlist_trends.py          # cross-commodity, cross-county comparison for the priority watchlist
  export_report.py                       # analytics result -> CSV or PDF

app/infrastructure/db/repositories/
  analytics_repository.py            # read-only, hand-written aggregate SQL/SQLAlchemy queries
                                       # (this is the one place raw aggregate queries live — not scattered
                                       #  across use cases, so they're reviewable and indexable together)

app/infrastructure/reporting/
  csv_exporter.py
  pdf_exporter.py                       # e.g. via weasyprint or reportlab — pick one, keep it isolated here
```

## Task checklist

- [ ] `analytics_repository.py` — aggregate queries against `AvailabilityResult`/`Sweep`/`Call`, using the indexes Sprint 01 already created (`AvailabilityResult.commodity_id + created_at`) plus any new index this sprint's query patterns reveal a need for (add via a new Alembic migration, not a hand edit):
  - Stockout rate over time: for a commodity+geography, % of sweeps where in-stock facilities were below threshold, bucketed by week/month.
  - Stockout duration: longest/current consecutive-sweeps-below-threshold streak.
  - Facility reliability inputs: `Call` answer rate (`completed` vs `no_answer`/`failed` outcomes) and, where later cross-checkable, consistency of a facility's self-reported stock across repeated calls.
- [ ] `compute_stockout_analytics.py` — wraps the repository query, returns a structured result matching PROJECT.md 2.8/2.7's "e.g. carbetocin unavailable in this ward for 6 of the last 8 weeks" framing.
- [ ] `compute_facility_reliability.py` — combines answer rate + report consistency into a single `reliability_score` (documented formula, not a black box — write the weighting rationale as a one-line comment where the score is computed), persisted back onto `Facility.reliability_score` (the column already exists per Sprint 01's entity) via the facility repository, recomputed on a schedule (a Celery Beat task, reusing Sprint 04's scheduling pattern) rather than on every single call.
- [ ] `compute_watchlist_trends.py` — cross-commodity/cross-county comparison for PROJECT.md 2.8's "which essential medicines are most chronically unavailable, county comparison."
- [ ] `export_report.py` + `csv_exporter.py`/`pdf_exporter.py` — takes any of the above use cases' structured output and renders CSV or PDF.
- [ ] Extend Sprint 05's routers with an `analytics` router: `GET /analytics/stockout-rate`, `GET /analytics/facility-reliability`, `GET /analytics/watchlist-trends`, `GET /analytics/export` (query params select which report + format; role-gated to at least `viewer`, since this is aggregate/analytical data rather than raw operational data — confirm against PROJECT.md 2.6's role list, adjust if this project's `viewer` role wasn't intended to see analytics before `analyst`).
- [ ] Unit/integration tests: seed a small multi-sweep history (reuse Sprint 04's `MockCallEAdapter`-driven sweep flow across several simulated dates) and assert the analytics queries produce the expected rate/duration/trend numbers against known input.

## API / data contract additions

- `GET /analytics/stockout-rate`, `GET /analytics/facility-reliability`, `GET /analytics/watchlist-trends`, `GET /analytics/export` — all additive to Sprint 05's API surface, no changes to existing endpoints.

## Rules specific to this sprint

- **DO NOT** write to `AvailabilityResult`, `Sweep`, or `Call` tables from anything in this sprint — this sprint reads and derives, it does not mutate operational data (the one exception, `Facility.reliability_score`, is an explicitly-scoped derived-and-cached field, recomputed on schedule, not on the hot path).
- **DO** keep aggregate SQL in `analytics_repository.py` rather than building ad hoc queries inline in each use case — one place to review query correctness and add indexes against.
- **DO NOT** compute `reliability_score` synchronously inside the webhook handler or any hot path — it's a scheduled batch recomputation, kept out of Sprint 03/04's latency-sensitive code.

## Testing requirements

- Analytics queries produce correct results against a seeded multi-sweep fixture with known expected output (not just "doesn't crash" — assert actual numbers).
- CSV/PDF export produces valid, parseable output (assert CSV has the expected header row + row count; assert PDF export doesn't raise and produces non-trivial byte output).
- Full test suite (Sprints 00-08) still green.

## Explicitly deferred

- KEMSA fill-rate correlation, ward-level chronic-stockout heatmap — both are explicit PROJECT.md §5 stretch goals, not built now; leave a one-line note in `compute_watchlist_trends.py`'s module docstring pointing at where that correlation would plug in, nothing more.
