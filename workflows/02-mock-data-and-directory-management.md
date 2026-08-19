# Sprint 02 — Mock Kenyan Data & Facility/Commodity Directory Management

> Preconditions: Sprint 01 complete (entities, DB schema, repositories exist and are tested).

## Goal & Definition of Done

The database can be seeded with a realistic, clearly-synthetic Kenyan facility directory (Kirinyaga + Nairobi) and a commodity catalog (KEML subset + priority watchlist), through a `FacilityImportPort` abstraction — not a one-off script that bypasses the architecture. Facility and commodity management use cases (add/edit/list/filter, duplicate detection, phone verification state) exist and are unit-tested. Still no HTTP routes — those come in Sprint 05, once every domain module they'll expose already exists. (Sprint 02 and 05 are deliberately separated so the use-case layer is validated on its own before it's wrapped in HTTP.)

## Preconditions

- Sprint 01's `Facility`/`Commodity` entities, repository ports, and SQLAlchemy repositories exist.

## Architecture for this sprint

```
app/application/ports/
  facility_import_port.py     # FacilityImportPort(ABC): async def fetch_facilities(geography_filter) -> list[FacilityImportRecord]

app/infrastructure/facility_import/
  __init__.py
  mock_kmhfl_adapter.py        # MockKMHFLAdapter(FacilityImportPort) — reads local seed file
  real_kmhfl_adapter.py         # RealKMHFLAdapter(FacilityImportPort) — stub only, raises NotImplementedError, ready for future KMHFL API wiring

data/seed/
  facilities_kirinyaga.json    # hand-curated, ~40-60 facilities
  facilities_nairobi.json      # hand-curated, ~40-60 facilities
  chemists_manual.json          # a handful of "private chemist" entries, source=manual
  commodities_keml.json          # KEML-subset catalog with priority watchlist flags + aliases

app/application/use_cases/
  import_facilities.py          # runs FacilityImportPort → repository, dedupes
  manage_facilities.py           # add/edit facility, verify/flag phone number
  manage_commodities.py           # add/edit commodity, tag priority watchlist
  list_facilities.py               # filter by county/sub_county/ward/type/ownership
  list_commodities.py               # filter/search incl. alias fuzzy match

app/domain/services/
  dedup.py                       # pure function: is_duplicate(candidate, existing) -> bool
                                   # (phone-number match OR geo-proximity match within radius)
```

`FacilityImportRecord` is a small dataclass in `domain/` distinct from `Facility` — it's what an import source hands back (raw name/GPS/phone/type/county/etc., `kmhfl_code` optional), before it's turned into a persisted `Facility` with an id.

## Task checklist

- [ ] Build `data/seed/facilities_kirinyaga.json` and `facilities_nairobi.json`: real county/sub-county/ward names (Kirinyaga: Kerugoya, Mwea, etc.; Nairobi: Westlands, Kibra, Embakasi, etc.), GPS coordinates plausibly inside each area's real bounding box, `+254` phone numbers in a clearly-fake but correctly-formatted range (e.g. a reserved test prefix, documented as such in the file's header comment), a realistic mix of `facility_type` and `source=kmhfl`.
- [ ] Build `data/seed/chemists_manual.json`: 8-10 private-chemist-style entries, `source=manual`, to exercise the non-KMHFL path.
- [ ] Build `data/seed/commodities_keml.json`: carbetocin + 4-5 other essential medicines from PROJECT.md's MVP scope (e.g. ARVs, insulin, an antimalarial, an anti-TB drug), each with `keml_code`, `category`, `aliases[]` (e.g. carbetocin → `["PPH drug", "pitocin alternative"]`), `is_priority_watchlist=true` for the watchlist set.
- [ ] Every seed file's header comment states plainly: **this is synthetic data for development/demo, not a real KMHFL or KEML export.**
- [ ] `FacilityImportPort` + `MockKMHFLAdapter` (reads the JSON seed files, returns `FacilityImportRecord`s) + `RealKMHFLAdapter` stub (constructor takes a base URL/API key, all methods raise `NotImplementedError("real KMHFL adapter not implemented — see workflows/02")`).
- [ ] `domain/services/dedup.py` — pure duplicate-detection function (phone match OR haversine/PostGIS-distance-within-N-meters match), unit-tested with no DB.
- [ ] `use_cases/import_facilities.py` — pulls records from a `FacilityImportPort`, runs each through dedup against existing DB rows, inserts new ones, and reports (imported, skipped-as-duplicate) counts. Selecting mock vs. real adapter is a `Settings`-driven choice (`FACILITY_IMPORT_MODE=mock|real`), same pattern as `CALL_E_MODE`.
- [ ] `use_cases/manage_facilities.py` — add facility manually (source=manual), edit facility fields, mark a phone number `unverified`/`bounced`/`verified` (a small state field on `Facility`, transitions triggered by this use case — actual bounce detection from failed calls is wired in Sprint 04, this sprint only builds the state machine and manual-correction path).
- [ ] `use_cases/manage_commodities.py` — add/edit commodity, toggle priority-watchlist flag.
- [ ] `use_cases/list_facilities.py` / `list_commodities.py` — filtered listing (county/sub_county/ward/type/ownership for facilities; category/watchlist/alias-search for commodities), backed by repository query methods added now (this is the sprint that needs them, per Sprint 01's deferral note).
- [ ] A `scripts/seed_db.py` CLI entrypoint (invoked via `uv run python -m scripts.seed_db`) that runs the import use case against both counties' seed files plus the manual chemists and the commodity catalog — this is what Sprint 09's demo setup will call.
- [ ] Unit tests for `dedup.py`, `import_facilities.py` (with `MockKMHFLAdapter`), `manage_facilities.py`, `manage_commodities.py`, `list_facilities.py`/`list_commodities.py`.

## API / data contract additions

None yet (no routers this sprint — see Sprint 05). Internally, `FacilityImportRecord` and the filtered-list query shapes (`FacilityFilter`, `CommodityFilter` dataclasses in `application/use_cases/`) are now fixed and will map directly onto Sprint 05's query-parameter schemas.

## Rules specific to this sprint

- **DO NOT** hardcode seed data inline in Python — it lives in `data/seed/*.json` so it's reviewable as data, not code, and easy to extend to more counties later.
- **DO** make `MockKMHFLAdapter` and `RealKMHFLAdapter` genuinely interchangeable behind `FacilityImportPort` — the use case must not know or care which one it's talking to.
- **DO NOT** implement `RealKMHFLAdapter`'s actual HTTP calls this sprint — it's an explicit stub per PROJECT.md's "Stretch: DHIS2/real KMHFL" framing. Implementing it now is scope creep.
- **DO** run every seeded phone number through the same `E.164`-with-`+254` validation that manual/production entries would go through — the seed data should look exactly like what a real import would produce, error-shape and all.

## Testing requirements

- `dedup.py` unit tests cover: exact phone match → duplicate; same phone different formatting → duplicate; close GPS + different phone → duplicate; far GPS + different phone → not duplicate.
- `import_facilities.py` integration test: running the seed import twice is idempotent (second run reports 0 new imports, all duplicates).
- `manage_facilities.py`/`manage_commodities.py` unit tests cover the add/edit/verify-state-transition paths, including rejecting an invalid phone format.
- `scripts/seed_db.py` runs end-to-end against a fresh test DB and leaves the expected row counts.

## Explicitly deferred

- Real KMHFL/DHIS2 API integration (stretch, PROJECT.md §2.1) — stub only.
- Phone-bounce detection triggered by actual failed CALL-E calls — that hook is added in Sprint 04, this sprint only builds the state machine it writes into.
- Any HTTP-exposed CRUD endpoint — Sprint 05.
- Facility reliability scoring — Sprint 08.
