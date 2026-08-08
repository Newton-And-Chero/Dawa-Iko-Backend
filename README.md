# CALL-E Hackathon Proposal
## Community Health Follow-Up Agent — Kenya

---

## 1. Overview

**Problem area:** Maternal & child health follow-up in Kenya
**Solution:** An AI voice-calling agent, built on CALL-E, that autonomously follows up with patients on antenatal care visits, child immunizations, and chronic-disease (e.g. TB) check-ins — reaching people by phone call alone, no app or smartphone required.

**Why it matters:** Kenya's community health system is chronically understaffed. The gap between how many people need follow-up and how many Community Health Volunteers (CHVs) exist to do it is large, measurable, and directly linked to missed vaccinations, late-detected pregnancy complications, and preventable under-five deaths. CALL-E is built to make and hold real phone conversations and return structured, actionable results — which is exactly the intervention this problem needs.

---

## 2. The Problem, Documented

### 2.1 CHVs are structurally overstretched

- National guidance recommends **~100 households per CHV**. In practice this is often far exceeded — in one documented area, **70 CHVs serve a population of 76,000**, over 1,000 people each.
- **90.4%** of surveyed CHVs in Machakos County reported excessive workloads that significantly hampered their ability to deliver services — driven by community education, tracking/follow-up, and household visits stacking on top of each other.
- Kenya's broader health workforce is short by **nearly 60,000 professionals** (2021 estimate), a gap projected to grow to over **114,000 by 2030**.

### 2.2 The downstream cost: missed appointments

- In 2017, **502,860 children in Kenya were not immunized**, and **1.7 million children** born between 2013–2017 did not receive all prescribed vaccines — largely attributed to missed appointments.
- In Migori County (2020), only about **22% of pregnant women** presented for antenatal care (ANC) early enough (first 16 weeks) to fully benefit from testing and treatment of conditions like HIV, syphilis, anaemia, and malaria.
- Missed appointments are directly linked to Kenya's high under-five mortality rate, and to late detection of maternal health complications.

### 2.3 The intervention already works — it just doesn't scale

- In Siaya County, CHWs reminding expectant mothers by phone and household visit to attend ANC appointments — and holding them accountable — measurably improved attendance. In one case, a CHV was reachable during an actual labor emergency and helped the mother safely reach hospital after being called.
- The mechanism (a phone call, a reminder, a check-in, an escalation when something's wrong) is proven. What's missing is enough people to make the calls.

---

## 3. The Solution: AI Follow-Up Agent on CALL-E

An outbound-calling agent that a CHV, CHEW, or health facility can hand a patient list to (from a DHIS2 export, spreadsheet, or simple form), which then autonomously:

1. **Calls patients/mothers** in Swahili, English, or a preferred local language to remind them of an upcoming ANC visit, immunization date, or medication refill.
2. **Holds a real conversation** — confirms whether they can attend, and if not, asks why ("no transport," "clinic too far," "forgot," "can't afford") and logs the reason.
3. **Triages urgency** — for TB/chronic-disease patients, runs a basic symptom check and flags anyone who needs an in-person CHV visit today, not just a routine reminder.
4. **Escalates automatically** — on a red-flag symptom (e.g. bleeding, severe pain, child not eating), the agent gives immediate guidance to seek care and pushes an alert (SMS, dashboard, or webhook) to the responsible CHV/CHEW.
5. **Returns structured, actionable output** — confirmed attendees, no-shows with categorized reasons, and a short priority list of only the households that actually need an in-person visit.

### Why this fits CALL-E specifically

| CALL-E capability | Why it matters here |
|---|---|
| Real phone calls, not just chat/text | Reaches people on **basic phones**, no smartphone, app, or data bundle needed |
| Natural, adaptive conversation | Mirrors what CHVs already do successfully by phone — this scales a proven behavior, not a new one |
| Structured results returned | Converts "CHV must visit everyone" into "CHV visits the ~15% who actually need it" |
| Real-time adaptation | Enables in-call triage and escalation, not just a static reminder script |

---

## 4. MVP Scope for the Hackathon

- **Seed data:** A small mock patient list (CSV) — name, phone number, appointment type, date, language preference.
- **Conversation script with 3 branches:**
  - Confirm / reschedule appointment
  - Capture and categorize no-show reason
  - Urgent symptom triage with escalation
- **Output layer:** A simple dashboard or webhook receiver showing results bucketed as: *Confirmed*, *Rescheduled*, *No-show (with reason)*, *Urgent — flagged for CHV visit*.
- **Stretch goals:**
  - Automatic language switching (Swahili/English) based on the respondent's replies
  - Aggregated no-show-reason analytics (e.g. "38% of no-shows this week cited transport") to help facilities target the *real* barrier, not just the symptom

---

## 5. Impact Framing (for judging / pitch)

- **Who it helps:** Pregnant women, mothers of young children, and chronic-disease patients in areas with CHV ratios far above national guidance.
- **What it replaces/augments:** Manual CHV phone follow-up and home-visit triage — not replacing CHVs, but multiplying their reach and directing their limited time to the cases that actually need a physical visit.
- **What success looks like:** A measurable increase in confirmed ANC/immunization attendance, a categorized understanding of *why* people miss appointments, and faster identification of urgent cases needing in-person follow-up.

---

## 6. Sources

- Community perspectives on access to maternal health services during the COVID-19 pandemic in rural Western Kenya (PMC)
- Exploring acceptability, opportunities, and challenges of community-based home pregnancy testing for early ANC initiation in rural Kenya (PMC)
- Four antenatal care visits by four months of pregnancy — Migori County, Kenya (PMC)
- Kenya's Community Health Volunteer Program (CHW Central)
- Kenya's Community Health Workers Shortage Undermines Universal Health Care (CHW Central)
- Contribution of health workers and patient characteristics on adherence to antenatal clinic appointments — Homabay & Kisumu, Kenya (PAMJ-One Health)
- Performance of community health volunteers during the COVID-19 pandemic — Machakos County, Kenya (PMC)
- Modelling the health labour market outlook in Kenya, 2021–2035 (PMC)