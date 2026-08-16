# PROJECT.md
## Medicine & Commodity Availability Agent — Feature Specification

This document scopes the full feature set for implementation, replacing the earlier Community Health Follow-Up Agent spec. It targets **Problem 1** from [problems.md](./problems.md): nobody has a live, queryable record of what medicines/commodities are actually in stock, where. The build is a **Python backend** + **live dashboard**, using CALL-E to call facility pharmacies and private chemists in parallel and turn their answers into structured, queryable availability data.

> **Note:** [README.md](./README.md) still describes the earlier Community Health Follow-Up Agent proposal and needs a rewrite to match this pivot — not done as part of this spec.

---

## 0. Core Concept

**Input:** a commodity (e.g. "carbetocin") + a geography (e.g. "Kirinyaga County", a ward, or a radius from a point).
**Process:** resolve the candidate facility list for that geography, place parallel outbound calls via CALL-E to each one, run a fixed structured questionnaire, extract structured answers.
**Output:**
1. An immediate ranked list of where the commodity is available right now (for a patient/clinician/NGO acting today).
2. A persisted data point that, accumulated over repeated sweeps, becomes a time series revealing stockout patterns nobody currently measures.

Two usage modes:
- **On-demand query** — someone needs an answer now: "where can I get carbetocin in Kirinyaga?" → live parallel calls → map lights up.
- **Scheduled sweep** — recurring background sweeps of priority-watchlist commodities across a geography, building the historical stockout time series that is the project's real differentiator.

---

## 1. System Architecture

```
┌───────────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  Facility Directory     │────▶│   Python Backend      │────▶│   CALL-E Voice API  │
│  (KMHFL seed + manual)  │     │  (API + Sweep Engine)  │◀────│  (parallel outbound) │
└───────────────────────┘     └──────────┬────────────┘     └────────────────────┘
                                          │
                              ┌───────────┴────────────┐
                              │        Database          │
                              │ (facilities, commodities, │
                              │  sweeps, calls, results,  │
                              │  escalations, subscribers)│
                              └───────────┬────────────┘
                                          │
                     ┌────────────────────┼────────────────────┐
                     ▼                    ▼                    ▼
              ┌────────────┐      ┌──────────────┐     ┌──────────────┐
              │Live Dashboard│      │ Public Query  │     │ SMS/Webhook   │
              │ (map + time  │      │ API (on-demand│     │ Alerts        │
              │  series)     │      │  lookup)      │     │ (stockout esc)│
              └────────────┘      └──────────────┘     └──────────────┘
```

**Components:**
1. **Backend service** (Python — FastAPI) — REST/WebSocket API, sweep orchestration, call dispatch, structured-result extraction
2. **Call engine integration** — wraps CALL-E to place parallel calls, run the stock-check conversation flow, receive transcripts/structured results
3. **Database** — persists facilities, commodities, sweeps, calls, availability results, escalations, subscribers
4. **Live dashboard** — real-time availability map + time series for analysts, NGOs, county health teams
5. **Public query interface** — the crisp "where can I get X in Y" demo path, usable by patients/clinicians directly
6. **Notification layer** — SMS/webhook push for confirmed local stockouts and for successful on-demand matches

---

## 2. Feature Modules

### 2.1 Facility & Commodity Directory Management
- [ ] **KMHFL import adapter** — bulk-import public facility data (name, GPS, county/sub-county/ward, facility type, ownership, KMHFL code) from the Kenya Master Health Facility Registry as the facility seed list
- [ ] Manual facility add/edit (for private chemists not in KMHFL, and to correct stale phone numbers — a known KMHFL data-quality issue)
- [ ] Facility phone number verification workflow (flag unverified/bounced numbers; allow crowd/CHV correction)
- [ ] Commodity catalog seeded from the Kenya Essential Medicines List (KEML), with common-name aliases for fuzzy matching (e.g. "PPH drug" → carbetocin)
- [ ] Priority watchlist tagging for commodities known to be in chronic crisis (carbetocin, ARVs, insulin, malaria/TB drugs, etc.)
- [ ] Facility list view with filters (county, sub-county, ward, facility type, ownership, call-success rate)
- [ ] Duplicate detection on facility import (by phone number + geo proximity)
- [ ] **Stretch:** DHIS2 cross-reference for facility metadata enrichment

### 2.2 Query & Sweep Orchestration
- [ ] On-demand query: commodity + geography → resolve candidate facility list → trigger immediate parallel call batch
- [ ] Scheduled recurring sweeps (e.g. "sweep carbetocin across Kirinyaga weekly") for priority-watchlist commodities, to build the time series
- [ ] Geography resolution: county / sub-county / ward / radius-from-point / "nearest N facilities"
- [ ] Call-list sizing & prioritization (cap facilities per sweep for cost/latency; order by distance, then public facilities before private chemists, or vice versa per query intent)
- [ ] Per-facility call-frequency throttling — never call the same facility more than once per configurable window, to avoid pharmacy fatigue/harassment
- [ ] Retry logic for no-answer/failed calls (retry once, cap at N attempts, vary time-of-day)
- [ ] Sweep status tracking (queued / in-progress / completed; N called / N total)
- [ ] Manual "call this facility now" action (e.g. to reconfirm a hold before a patient travels there)

### 2.3 Voice Call Engine (CALL-E Integration)
- [ ] Outbound call placement via CALL-E API, dispatched as a parallel batch per sweep
- [ ] Structured question-set delivery, selected by commodity type (core fixed questions + commodity-specific variants, e.g. cold-chain question for vaccines)
- [ ] Language selection (Swahili/English) per facility, learned/stored after first successful call
- [ ] Call status webhook receiver (initiated, connected, no-answer, failed, completed, voicemail)
- [ ] Structured-result extraction from the conversation, mapped to fixed fields (in_stock, quantity_band, price, last_restock_date, can_hold) with a confidence score
- [ ] Ambiguous/uncertain answers marked "unknown" rather than guessed, flagged for human review
- [ ] Transcript and recording storage/retrieval

### 2.4 Conversation Flow (Call Script)
- [ ] Opening: identifies the caller as an independent availability-monitoring service (not MOH/KEMSA), states purpose in one sentence, respects that pharmacy staff are busy
- [ ] **Core fixed question set:**
  1. Do you currently have [commodity] in stock?
  2. Approximately how many units do you have (quantity band)?
  3. What's your current price?
  4. When did you last restock this item?
  5. Could you hold a unit for a patient, and for how long?
- [ ] **Branch — In stock:** capture quantity band, price, hold offer, hold reference/confirmation code
- [ ] **Branch — Out of stock:** capture last restock date, expected restock date if known, ask if they know a nearby facility that might have it
- [ ] **Branch — Uncertain/needs to check:** offer a callback window, schedule an automatic retry
- [ ] Decision-tree/branching engine reusable across commodities (condition-aware, same engine regardless of drug)
- [ ] **Stretch:** automatic language switching mid-call based on the respondent's spoken replies
- [ ] **Stretch:** commodity-specific follow-up questions (cold-chain compliance for vaccines, expiry date for time-sensitive drugs)

### 2.5 Escalation & Alerting (Stockout Detection)
- [ ] Zero-availability detection: a sweep completing with 0% (or below-threshold %) of facilities in-stock auto-flags as a confirmed local stockout
- [ ] Severity classification from commodity priority tier + % facilities with zero stock + facility density in the area
- [ ] Escalation record created and linked to subscribers watching that geography/commodity (county pharmacist, NGO partner, MOH contact)
- [ ] Outbound alert dispatch: SMS/email/webhook when a stockout is confirmed or a watchlist commodity crosses a scarcity threshold
- [ ] Escalation acknowledgment/resolution tracking (subscriber marks "redistributing stock" / "resolved")
- [ ] Patient-facing match alert: when an on-demand query finds availability, immediately return facility name, distance, price, and hold reference to the requester

### 2.6 Backend API
- [ ] REST endpoints for facilities, commodities, sweeps, calls, availability results, escalations, subscribers (CRUD where applicable)
- [ ] **Public query endpoint** — `POST {commodity, geography}` → triggers a sweep, returns a `sweep_id` for polling/streaming results (this is the demo path)
- [ ] Authentication & role-based access (admin, analyst/dispatcher, NGO/subscriber viewer, public read-only for the aggregate map)
- [ ] Webhook receiver endpoint for CALL-E call events and structured results
- [ ] WebSocket/SSE channel for real-time dashboard updates and live query-result streaming
- [ ] Pagination, filtering, search on list endpoints (by commodity, geography, date range, stock status)
- [ ] Rate limiting on the public query endpoint (each query triggers real phone calls to real pharmacies — must not be abusable)

### 2.7 Live Dashboard
- [ ] **Live availability map** — pin/choropleth map by county/ward, color-coded by stock status for the selected commodity, updating in real time as calls complete
- [ ] **Query view** — enter commodity + geography, watch live call progress (N/M facilities called), see ranked results stream in (in-stock first, sorted by distance/confidence), with hold status
- [ ] **Time-series view** — per commodity/geography, stockout rate over time (e.g. "carbetocin unavailable in this ward for 6 of the last 8 weeks") — the core differentiated feature no one else currently measures
- [ ] Sweep summary view (progress bar, completion %, success/no-answer/failed breakdown)
- [ ] Facility detail drill-down (call history, availability history, transcript, reliability score)
- [ ] Stockout alert queue with acknowledge/resolve actions for NGO/county subscribers
- [ ] Filters by county, ward, facility type, commodity, date range
- [ ] Live call status indicators (calling / ringing / connected / completed) via WebSocket/SSE
- [ ] Simplified public-facing read-only view ("where can I find X near me")

### 2.8 Analytics & Reporting
- [ ] Stockout frequency/duration analytics per commodity per geography
- [ ] Facility reliability scoring (answer rate, historical report accuracy)
- [ ] Priority-watchlist trend dashboard (which essential medicines are most chronically unavailable, county comparison)
- [ ] Exportable reports (CSV/PDF) for county health teams, NGOs, journalists
- [ ] **Stretch:** correlate local stockout patterns against published KEMSA fill-rate data to distinguish systemic vs. local causes
- [ ] **Stretch:** ward-level chronic-stockout heatmap for advocacy/reporting use

---

## 3. Data Model (Core Entities)

| Entity | Key Fields |
|---|---|
| **Facility** | id, name, type (public/dispensary/private chemist/faith-based), county, sub_county, ward, gps_lat, gps_lng, phone_number, kmhfl_code, source (kmhfl/manual/crowd), operational_status, last_verified_at, reliability_score |
| **Commodity** | id, name, category (essential medicine/vaccine/supply), keml_code, aliases[], is_priority_watchlist |
| **Sweep** | id, commodity_id, geography_scope, trigger_type (on_demand/scheduled), status, requester_id, created_at |
| **Call** | id, sweep_id, facility_id, status, attempt_number, started_at, ended_at, transcript_url, recording_url |
| **AvailabilityResult** | id, call_id, facility_id, commodity_id, in_stock (yes/no/unknown), quantity_band, price_kes, last_restock_date, can_hold, hold_duration_hours, hold_reference_code, confidence, notes |
| **StockoutAlert** | id, commodity_id, geography, severity, facilities_checked_count, facilities_with_stock_count, triggered_at, status (open/acknowledged/resolved) |
| **Subscriber** | id, name, org, phone, email, watchlist_commodities[], watchlist_geography, notification_channel |
| **User** | id, name, role (admin/analyst/viewer), org, phone_number |

---

## 4. MVP Scope (Hackathon Build)

Minimum feature set to demonstrate the end-to-end loop:

1. Facility directory seeded from KMHFL for 1–2 target counties (e.g. Kirinyaga + Nairobi) plus a handful of manually added private chemists
2. Commodity catalog seeded with a short priority watchlist (carbetocin + 4–5 other essential medicines)
3. On-demand query flow: commodity + geography → CALL-E places parallel calls → structured results
4. Core fixed question set functional (in stock / quantity band / price / last restock / can hold)
5. Results written to DB; live map + ranked results list updating in near-real-time
6. Zero-availability stockout flag (dashboard flag sufficient; SMS/webhook optional for MVP)
7. At least one repeated sweep pre-run before the demo so the time-series view has real data to show

## 5. Stretch Goals (Post-MVP)

- Scheduled recurring sweeps across the full watchlist
- SMS/webhook escalation delivery (vs. dashboard-only)
- Multi-county scale-up beyond the demo counties
- Commodity-specific question variants (cold-chain, expiry)
- Automatic language switching within a call
- Facility reliability scoring
- Public-facing simplified map for direct patient use
- Correlation with published KEMSA fill-rate data

## 6. Explicitly Out of Scope (for now)

- Any write-back/integration into KEMSA or KMHFL systems — this is an independent enrichment layer, not a replacement for facility inventory systems
- E-commerce, ordering, or payment flows
- Medical advice delivered to patients on the call
- Any impersonation of MOH/KEMSA in the call script
- Native mobile app
- Two-way SMS conversation flows (voice-only for MVP)

---

## 7. Tech Stack (proposed)

| Layer | Choice |
|---|---|
| Backend | Python — FastAPI |
| Database | PostgreSQL + PostGIS (for geography queries) |
| Real-time updates | WebSockets (FastAPI native) or Server-Sent Events |
| Voice calling | CALL-E API |
| Facility geodata source | KMHFL/KMHFR bulk export |
| Dashboard frontend | React (map via a lightweight JS mapping lib), or server-rendered templates for hackathon speed |
| Background jobs / scheduling | Celery + Redis, or APScheduler for hackathon scope |
| Deployment | TBD — containerized (Docker) for portability |

---

## 8. Data Sources & Constraints

- **Facility directory (public, available now):** Kenya Master Health Facility List / Registry (kmhfl.health.go.ke, kmhfr.health.go.ke) — facility name, GPS, county/sub-county/ward, ownership, type, facility code. Known issue: phone numbers are frequently stale, so a verification/correction workflow (2.1) is required, not optional.
- **Commodity catalog (public):** Kenya Essential Medicines List (KEML).
- **Aggregate crisis evidence (public, for the pitch narrative):** KEMSA/Ministry of Health fill-rate reporting (e.g. Economic Survey figures, KEMSA public statements) — useful for framing, not for live per-facility stock (that data does not exist publicly, which is the gap this project fills).
- **Live per-facility stock data:** not publicly available anywhere — this project is the first system to generate it, via direct calls rather than a data feed.
