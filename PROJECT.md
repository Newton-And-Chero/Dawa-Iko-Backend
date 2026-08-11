# PROJECT.md
## Community Health Follow-Up Agent — Feature Specification

This document scopes the full feature set for implementation. It translates the proposal in [README.md](./README.md) into concrete system components, features, and data contracts for a **Python backend** + **live dashboard** build.

---

## 1. System Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌────────────────────┐
│  Patient Data    │────▶│   Python Backend      │────▶│   CALL-E Voice API  │
│  (CSV / DHIS2)   │     │   (API + Scheduler)   │◀────│   (outbound calls)  │
└─────────────────┘     └──────────┬────────────┘     └────────────────────┘
                                    │
                         ┌──────────┴────────────┐
                         │      Database          │
                         │ (patients, calls,      │
                         │  results, escalations)  │
                         └──────────┬────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
             ┌────────────┐  ┌────────────┐  ┌──────────────┐
             │Live Dashboard│  │ Webhook /  │  │ SMS Alerts    │
             │  (real-time) │  │ Alerts API │  │ (escalation)  │
             └────────────┘  └────────────┘  └──────────────┘
```

**Components:**
1. **Backend service** (Python — e.g. FastAPI) — REST/WebSocket API, call orchestration, business logic
2. **Call engine integration** — wraps CALL-E to place calls, run conversation flows, receive transcripts/structured results
3. **Database** — persists patients, campaigns, call records, outcomes, escalations
4. **Live dashboard** — real-time view of call activity and outcomes for CHV/CHEW/facility staff
5. **Notification layer** — SMS/webhook push for urgent escalations

---

## 2. Feature Modules

### 2.1 Patient & Data Management
- [ ] CSV upload/import (name, phone number, appointment type, date, language preference)
- [ ] Manual patient entry via form (single-record add/edit)
- [ ] Patient record schema validation (phone format, required fields)
- [ ] Duplicate detection on import (by phone number)
- [ ] Patient list view with filters (appointment type, date range, language, status)
- [ ] **Stretch:** DHIS2 export ingestion adapter

### 2.2 Campaign & Call Scheduling
- [ ] Create a "follow-up campaign" from an imported patient list (e.g. "ANC reminders — week 32")
- [ ] Schedule calls (immediate / at a specific date-time / batch window)
- [ ] Per-patient call retry logic (e.g. retry once if no answer, cap at N attempts)
- [ ] Campaign status tracking (queued, in-progress, completed)
- [ ] Manual "trigger call now" action for a single patient (dashboard action)

### 2.3 Voice Call Engine (CALL-E Integration)
- [ ] Outbound call placement via CALL-E API
- [ ] Conversation flow selection based on appointment type (ANC / immunization / chronic disease check-in)
- [ ] Language selection at call time (Swahili / English / other, per patient preference)
- [ ] Call status webhook receiver (initiated, connected, no-answer, failed, completed)
- [ ] Call transcript/result ingestion and storage

### 2.4 Conversation Flows (Call Scripts)
- [ ] **Branch 1 — Confirm/Reschedule:** confirm attendance for upcoming appointment; capture new date if rescheduling
- [ ] **Branch 2 — No-show reason capture:** structured reason categorization (no transport, too far, forgot, can't afford, other — free text fallback)
- [ ] **Branch 3 — Urgent symptom triage:** basic symptom checklist per condition type (e.g. bleeding, severe pain, child not eating); risk classification (routine / urgent)
- [ ] Flow branching logic engine (decision tree per conversation, condition-aware)
- [ ] **Stretch:** automatic language switching mid-call based on respondent's spoken replies

### 2.5 Escalation & Alerting
- [ ] Red-flag symptom detection triggers immediate escalation
- [ ] In-call guidance delivered to patient ("seek care now at nearest facility")
- [ ] Escalation record created and linked to responsible CHV/CHEW
- [ ] Outbound alert dispatch: SMS to CHV, dashboard flag, and/or webhook POST to external system
- [ ] Escalation acknowledgment/resolution tracking (CHV marks as "visited"/"resolved")

### 2.6 Backend API
- [ ] REST endpoints for patients, campaigns, calls, results, escalations (CRUD where applicable)
- [ ] Authentication for facility/CHV/CHEW users (login, role-based access: admin, CHEW, CHV)
- [ ] Webhook receiver endpoint for CALL-E call events and results
- [ ] WebSocket or SSE channel for real-time dashboard updates
- [ ] Pagination, filtering, and search on list endpoints

### 2.7 Live Dashboard
- [ ] Real-time call activity feed (calls in progress, just completed)
- [ ] Outcome buckets view: **Confirmed / Rescheduled / No-show (with reason) / Urgent — flagged for visit**
- [ ] Campaign summary view (progress bar: N called / N total, success rate)
- [ ] Patient detail drill-down (call history, transcript, outcome, escalation status)
- [ ] Urgent-case queue with one-click "assign to CHV" / "mark visited"
- [ ] Filters by facility, date range, appointment type, language
- [ ] Live status indicators (calling, ringing, connected, completed) via WebSocket/SSE

### 2.8 Analytics & Reporting
- [ ] No-show reason aggregation (e.g. "38% cited transport this week")
- [ ] Attendance/confirmation rate trends over time
- [ ] Per-CHV/facility performance summary (calls made, escalations resolved)
- [ ] Exportable reports (CSV/PDF) for facility review
- [ ] **Stretch:** geographic/ward-level breakdown of no-show reasons

---

## 3. Data Model (Core Entities)

| Entity | Key Fields |
|---|---|
| **Patient** | id, name, phone_number, language_pref, appointment_type, appointment_date, facility_id, chv_id |
| **Campaign** | id, name, created_at, status, patient_ids[] |
| **Call** | id, patient_id, campaign_id, status, attempt_number, started_at, ended_at, transcript_url |
| **CallResult** | id, call_id, outcome (confirmed/rescheduled/no_show/urgent), no_show_reason, new_appointment_date, symptom_flags[] |
| **Escalation** | id, patient_id, call_id, reason, severity, assigned_chv_id, status (open/acknowledged/resolved), created_at, resolved_at |
| **User** | id, name, role (admin/chew/chv), facility_id, phone_number |
| **Facility** | id, name, ward, county |

---

## 4. MVP Scope (Hackathon Build)

Minimum feature set to demonstrate the end-to-end loop:

1. CSV patient import
2. Manual campaign trigger → CALL-E places calls
3. All 3 conversation branches functional
4. Call results written to database
5. Live dashboard showing the 4 outcome buckets, updating in near-real-time
6. Basic escalation alert (dashboard flag is sufficient; SMS/webhook optional for MVP)

## 5. Stretch Goals (Post-MVP)

- Automatic language switching within a call
- No-show-reason analytics dashboard panel
- DHIS2 data ingestion
- Role-based multi-facility access control
- SMS escalation delivery (vs. dashboard-only)
- Exportable facility-level reports

## 6. Explicitly Out of Scope (for now)

- Native mobile app for CHVs
- Two-way SMS conversation flows (voice-only for MVP)
- Payment/financial-aid integrations tied to "can't afford" no-show reason
- Multi-country/multi-language localization beyond Swahili/English

---

## 7. Tech Stack (proposed)

| Layer | Choice |
|---|---|
| Backend | Python — FastAPI |
| Database | PostgreSQL |
| Real-time updates | WebSockets (FastAPI native) or Server-Sent Events |
| Voice calling | CALL-E API |
| Dashboard frontend | React (or lightweight server-rendered templates for hackathon speed) |
| Background jobs / scheduling | Celery + Redis, or APScheduler for hackathon scope |
| Deployment | TBD — containerized (Docker) for portability |
