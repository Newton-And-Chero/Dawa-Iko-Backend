# Sprint 01 — Domain Model & Database Schema

> Preconditions: Sprint 00 complete (`backend/` runs, migrates, tests pass).

## Goal & Definition of Done

Every entity in PROJECT.md §3 exists as (a) a framework-free domain representation and (b) a SQLAlchemy model with a corresponding Alembic migration that creates the real schema (with PostGIS geometry where relevant). Repository **ports** exist for each aggregate, with SQLAlchemy implementations. No API routes yet — this sprint is pure data layer.

## Preconditions

Sprint 00's skeleton exists: `app/domain/`, `app/application/ports/`, `app/infrastructure/db/`, Alembic wired up.

## Architecture for this sprint

```
app/domain/
  enums.py                  # FacilityType, FacilitySource, SweepStatus, SweepTrigger,
                              # CallStatus, StockStatus (yes/no/unknown), CommodityCategory,
                              # EscalationSeverity, EscalationStatus, UserRole, NotificationChannel
  entities/
    facility.py               # Facility dataclass
    commodity.py               # Commodity dataclass
    sweep.py                   # Sweep dataclass
    call.py                     # Call dataclass
    availability_result.py       # AvailabilityResult dataclass
    stockout_alert.py             # StockoutAlert dataclass
    subscriber.py                   # Subscriber dataclass
    user.py                           # User dataclass
  services/
    severity.py               # pure function: classify_severity(commodity_priority, pct_in_stock, facility_density) -> EscalationSeverity

app/application/ports/
  facility_repository.py      # FacilityRepositoryPort (ABC)
  commodity_repository.py
  sweep_repository.py
  call_repository.py
  availability_result_repository.py
  stockout_alert_repository.py
  subscriber_repository.py
  user_repository.py

app/infrastructure/db/
  models.py                   # SQLAlchemy declarative models, one class per entity
  repositories/
    facility_repository.py    # SqlAlchemyFacilityRepository(FacilityRepositoryPort)
    commodity_repository.py
    sweep_repository.py
    call_repository.py
    availability_result_repository.py
    stockout_alert_repository.py
    subscriber_repository.py
    user_repository.py

alembic/versions/0001_initial_schema.py
```

Each domain entity is a plain `@dataclass` (or `attrs`/`pydantic.dataclasses` if preferred, but no SQLAlchemy or FastAPI imports inside `domain/`). Each repository port declares the minimal async interface a use case needs (`get_by_id`, `add`, `list_by_geography`, etc.) — not a generic CRUD base class; each port's methods reflect what PROJECT.md's use cases actually need, added incrementally in later sprints as those use cases are built. This sprint only needs `get_by_id`, `add`, and `list_all` on each — enough to prove the DB round-trip works. Query-heavy methods (geography filters, throttling checks) belong to the sprint that needs them.

## Task checklist

- [ ] `domain/enums.py` — all enums per PROJECT.md §3, e.g.:
  - `FacilityType`: `public | dispensary | private_chemist | faith_based`
  - `FacilitySource`: `kmhfl | manual | crowd`
  - `StockStatus`: `yes | no | unknown`
  - `SweepTrigger`: `on_demand | scheduled`
  - `SweepStatus`: `queued | in_progress | completed`
  - `CallStatus`: `queued | in_progress | completed | failed | canceled | no_answer | voicemail`
  - `EscalationStatus`: `open | acknowledged | resolved`
  - `UserRole`: `admin | analyst | viewer | public`
- [ ] `domain/entities/*.py` — one dataclass per PROJECT.md §3 row, field names matching that table exactly (so the mapping to API schemas in Sprint 05 is mechanical).
- [ ] `domain/services/severity.py` — pure function for stockout severity classification (commodity priority tier × % facilities with zero stock × facility density → `EscalationSeverity`), unit-testable with no DB.
- [ ] `application/ports/*.py` — one `Protocol` or `ABC` per aggregate, async methods only.
- [ ] `infrastructure/db/models.py` — SQLAlchemy 2.0 declarative models:
  - `Facility.location` as a `geoalchemy2.Geometry("POINT", srid=4326)` column (not separate lat/lng floats — this is what makes county/radius/nearest-N geography queries in Sprint 04 correct and fast with a GIST index).
  - Foreign keys: `Sweep.commodity_id → Commodity`, `Call.sweep_id → Sweep`, `Call.facility_id → Facility`, `AvailabilityResult.call_id → Call`, `AvailabilityResult.facility_id → Facility`, `AvailabilityResult.commodity_id → Commodity`, `StockoutAlert.commodity_id → Commodity`.
  - Indexes: GIST index on `Facility.location`; b-tree on `Facility.county`/`sub_county`/`ward`; on `Call.facility_id` + `started_at` (needed by Sprint 04's throttling check); on `AvailabilityResult.commodity_id` + `created_at` (needed by Sprint 08's time series).
- [ ] `infrastructure/db/repositories/*.py` — one concrete class per port, using the async session from Sprint 00's `session.py`.
- [ ] Alembic migration `0001_initial_schema` — enable the `postgis` extension, create all tables, indexes, enum types.
- [ ] Unit tests for `severity.py` (framework-free, no DB) covering: 0% stock + priority commodity = high severity; partial stock = lower severity; edge cases (zero facilities checked → not an alert).
- [ ] Integration tests: for each repository, `add()` then `get_by_id()` round-trips correctly against a real (test) Postgres/PostGIS instance.

## API / data contract additions

None yet — no routers touched this sprint. (Contract groundwork: entity field names are now fixed, which Sprint 05's Pydantic schemas will mirror.)

## Rules specific to this sprint

- **DO NOT** import SQLAlchemy, FastAPI, or Celery inside anything in `domain/`. If a domain file needs to import from `infrastructure/` or `api/`, that's a sign the code belongs in a different layer.
- **DO** store facility coordinates as a PostGIS `POINT` geometry, not raw float columns — Sprint 04's geography resolution depends on this.
- **DO NOT** add repository methods speculatively "because they'll probably be needed" — add `get_by_id`/`add`/`list_all` now; add anything else (filters, throttle checks, aggregate queries) in the sprint that actually calls it, right next to that use case.
- **DO** use `Decimal` (not `float`) for `price_kes` in both the domain entity and the DB column — money never gets float rounding error.

## Testing requirements

- All repository round-trip integration tests pass against a real Postgres+PostGIS (docker-compose service, matching Sprint 00's setup).
- `severity.py` unit tests pass with no DB dependency.
- `alembic upgrade head` on a clean DB creates the full schema with no errors; `alembic downgrade base` cleanly drops it.
- `mypy` passes on all new `domain/` and `application/ports/` files with strict settings (this is where type discipline pays off most, since these are the interfaces everything else depends on).

## Explicitly deferred

- No repository method beyond basic CRUD — geography filters, throttle-window queries, and time-series aggregation queries are added in the sprints that need them (04, 08), not preemptively here.
- No API endpoints exposing any of this yet — Sprint 05.
- No seed/mock data yet — Sprint 02.
