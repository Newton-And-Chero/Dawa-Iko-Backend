# Global Rules — Dos and Don'ts

These rules apply to **every** sprint workflow in this folder. Each sprint file lists rules specific to itself; this file is the baseline that never gets relaxed. If a sprint file ever seems to conflict with this one, this one wins — stop and ask rather than guessing.

This project is **backend-only** for now. No frontend/dashboard code is in scope until a future workflow explicitly reopens it.

---

## Architecture

- **DO** keep `backend/app/domain/` free of any framework import (no FastAPI, no SQLAlchemy, no Celery, no httpx). It contains entities, value objects, and pure functions only.
- **DO** put orchestration logic in `backend/app/application/use_cases/`. A use case depends only on **ports** (`backend/app/application/ports/`), never on a concrete adapter class.
- **DO** implement every external side effect — CALL-E, SMS, DB, Redis — as an adapter in `backend/app/infrastructure/` implementing a port interface defined in `application/ports/`.
- **DO NOT** let a FastAPI router (`backend/app/api/`) touch the database, Redis, or CALL-E directly. A router parses the request, calls a use case, serializes the response. That's it.
- **DO NOT** let a Celery task (`backend/app/workers/`) contain business logic beyond "call a use case." Tasks are thin triggers.
- **DO NOT** introduce a new abstraction (base class, generic repository, plugin system) unless the current sprint's checklist asks for it. Three similar lines beat a premature interface.

## Mock vs. real adapters

- **DO** give every adapter with a real-world side effect (CALL-E, SMS, KMHFL import) a `Mock*` counterpart implementing the same port, selected via an env var (e.g. `CALL_E_MODE=mock|live`, `SMS_MODE=mock|live`).
- **DO** default every environment except an explicit production-like one to `mock`. Nobody should place a real phone call or send a real SMS by accident.
- **DO NOT** call a real external paid API (CALL-E, Twilio) from an automated test, ever. Automated tests only exercise `Mock*` adapters.
- **DO** label mock/seed data as synthetic everywhere it surfaces — code comments at the seed source, log lines, and any future UI. Never let generated Kenyan facility data be mistaken for a real KMHFL export.

## Data & migrations

- **DO** make every schema change through an Alembic migration, committed alongside the model change that caused it.
- **DO NOT** hand-edit the database schema, in dev or anywhere else, outside of a migration.
- **DO NOT** commit secrets (API keys, DB passwords, JWT signing keys) to the repo. They live in `.env` (gitignored); `.env.example` documents every variable name with a placeholder value and stays current.

## CALL-E specifics

- **DO** attach an `Idempotency-Key` to every `POST /v1/calls` request, derived deterministically from the sweep id (and chunk index, if chunked) so retried dispatch code never double-calls facilities.
- **DO** respect a configurable `MAX_RECIPIENTS_PER_TASK` and chunk a sweep's candidate list into multiple call tasks above it — CALL-E's API does not document an upper bound, so assume there is one until proven otherwise.
- **DO** treat every inbound webhook payload as untrusted input: CALL-E does not sign webhooks (no HMAC, no `CALL-E-Signature`). Validate the `CALL-E-Event-Id` header against the body's `id`, only accept events for `call_id`s already persisted in `queued`/`in_progress` state, and require the per-deployment token embedded in the registered `webhook_url` (see Sprint 03).
- **DO NOT** build or plan a Swahili call flow. CALL-E's Kenya (`KE`) region is English-only as of this writing — this is a vendor constraint, not a bug in our code. Revisit only if CALL-E's supported-language list changes.
- **DO NOT** guess at CALL-E API shapes. If a sprint needs a detail this repo's workflow docs don't already specify, re-check `docs.heycall-e.com` (quickstart + OpenAPI spec at `/openapi/calle.openapi.yaml`) rather than assuming.

## Process

- **DO** finish a sprint's testing requirements before starting the next sprint's task checklist.
- **DO** create a commit at the end of each sprint (only when the user asks for a commit to be made, per standard git-safety practice — but keep the working tree in a committable state at every sprint boundary).
- **DO NOT** implement anything listed under PROJECT.md §6 "Explicitly Out of Scope": no ordering/payment flows, no medical advice delivered on a call, no impersonation of MOH/KEMSA in any call script, no native mobile app, no two-way SMS conversations.
- **DO NOT** scope-creep a sprint with another sprint's work, even if it looks convenient (e.g. don't build alerting logic while doing sweep orchestration). Note the temptation in that sprint's "Explicitly deferred" section instead.
- **DO** keep every new module small enough to review in one sitting. If a file is trying to do two jobs, split it along the architecture boundaries above, not arbitrarily.

## Reuse

- **DO** check `backend/app/domain/`, `application/ports/`, and existing repositories before writing a new entity, port, or repository — reuse what's there rather than duplicating.
- **DO NOT** add configuration flags, feature flags, or extension points for hypothetical future requirements not in the current sprint's checklist.
