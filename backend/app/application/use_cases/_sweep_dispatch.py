"""Shared dispatch pipeline behind `run_on_demand_sweep` and
`run_scheduled_sweep` — the only difference between the two triggers is
`trigger_type` and whether a human `requester_id` exists, so the resolve ->
cooldown-filter -> prioritize -> chunk -> dispatch pipeline lives here once.

`dispatch_call_chunk` is also reused by `retry_failed_calls` and
`request_manual_call`, which dispatch a single facility outside the full
sweep pipeline (a retry, or a deliberate "call this now").

Not a use case itself — an internal helper module for the `use_cases`
package (hence the leading underscore).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.geography_resolver_port import GeographyResolverPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.realtime_events import publish_sweep_status_event
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.core.webhook_security import build_webhook_url
from app.domain.call_schemas import (
    CALLE_RECIPIENT_LOCALE,
    CALLE_RECIPIENT_REGION,
    STOCK_CHECK_RESULT_SCHEMA,
    build_stock_check_task,
)
from app.domain.entities.call import Call
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import CallListIntent, CallStatus, SweepStatus, SweepTrigger
from app.domain.services.call_list_policy import chunk as chunk_facilities
from app.domain.services.call_list_policy import is_cooldown_blocked, prioritize
from app.domain.value_objects.call_task_ref import CallRecipient, CallTaskRef
from app.domain.value_objects.geography_scope import GeographyScope, geography_scope_to_dict


@dataclass
class SweepDependencies:
    geography_resolver: GeographyResolverPort
    call_repository: CallRepositoryPort
    sweep_repository: SweepRepositoryPort
    commodity_repository: CommodityRepositoryPort
    call_provider: CallProviderPort
    settings: Settings
    realtime_event_bus: RealtimeEventBusPort


async def dispatch_call_chunk(
    call_repository: CallRepositoryPort,
    call_provider: CallProviderPort,
    *,
    commodity_name: str,
    facilities: list[Facility],
    sweep_id: UUID,
    idempotency_key: str,
    attempt_number: int,
) -> CallTaskRef:
    """Create Call rows for `facilities` (all belonging to `sweep_id`) and
    place one CALL-E call task covering all of them. Returns immediately once
    CALL-E accepts the task — completion is observed later via the webhook
    pipeline (Sprint 03), never awaited here.
    """
    now = datetime.now(UTC)
    calls = [
        Call(
            sweep_id=sweep_id,
            facility_id=facility.id,
            status=CallStatus.QUEUED,
            attempt_number=attempt_number,
            started_at=now,
        )
        for facility in facilities
    ]
    for call in calls:
        await call_repository.add(call)

    recipients = [
        CallRecipient(
            phones=[facility.phone_number],
            region=CALLE_RECIPIENT_REGION,
            locale=CALLE_RECIPIENT_LOCALE,
        )
        for facility in facilities
    ]
    call_task = await call_provider.place_call(
        task=build_stock_check_task(commodity_name),
        recipients=recipients,
        result_schema=None,
        recipient_result_schema=STOCK_CHECK_RESULT_SCHEMA,
        webhook_url=build_webhook_url(),
        idempotency_key=idempotency_key,
        metadata={"sweep_id": str(sweep_id)},
    )

    # CALL-E assigns its own opaque recipient ids — match them back to our
    # Call rows by phone number so the webhook handler can find them later.
    # Linked in one bulk_update (one commit) rather than per-row: a webhook
    # can arrive the instant place_call() returns, and a partial write here
    # would leave some rows linked and others silently unreachable forever.
    recipient_by_phone = {r.phones[0]: r for r in call_task.recipients}
    for call, facility in zip(calls, facilities, strict=True):
        recipient_ref = recipient_by_phone[facility.phone_number]
        call.provider_call_id = call_task.id
        call.provider_recipient_id = recipient_ref.id
    await call_repository.bulk_update(calls)

    return call_task


async def dispatch_sweep(
    deps: SweepDependencies,
    *,
    commodity_id: UUID,
    geography: GeographyScope,
    trigger_type: SweepTrigger,
    requester_id: UUID | None,
    intent: CallListIntent,
) -> UUID:
    commodity = await deps.commodity_repository.get_by_id(commodity_id)
    if commodity is None:
        raise NotFoundError(f"commodity {commodity_id} not found")

    candidates = await deps.geography_resolver.resolve(geography)

    now = datetime.now(UTC)
    eligible: list[Facility] = []
    for facility in candidates:
        last_call = await deps.call_repository.get_last_call_for_facility(facility.id)
        if last_call is not None and is_cooldown_blocked(
            last_call.started_at, now, deps.settings.FACILITY_CALL_COOLDOWN_HOURS
        ):
            continue
        eligible.append(facility)

    ordered = prioritize(eligible, geography, intent)
    chunks = chunk_facilities(ordered, deps.settings.MAX_RECIPIENTS_PER_TASK)

    sweep = await deps.sweep_repository.add(
        Sweep(
            commodity_id=commodity_id,
            geography_scope=geography_scope_to_dict(geography),
            trigger_type=trigger_type,
            status=SweepStatus.QUEUED,
            requester_id=requester_id,
        )
    )

    if not chunks:
        # No candidates survived resolution/cooldown — nothing to wait on.
        # Deliberately does not run stockout detection (workflows/07): a sweep
        # that completes here always has facilities_checked_count == 0, and
        # classify_severity treats that as "nothing to detect" by contract —
        # there is no false-positive stockout to guard against, so there is
        # nothing this path could ever find.
        await deps.sweep_repository.update_status(sweep.id, SweepStatus.COMPLETED)
        await publish_sweep_status_event(
            deps.realtime_event_bus, deps.sweep_repository, deps.call_repository, sweep.id
        )
        return sweep.id

    for index, facility_chunk in enumerate(chunks):
        await dispatch_call_chunk(
            deps.call_repository,
            deps.call_provider,
            commodity_name=commodity.name,
            facilities=facility_chunk,
            sweep_id=sweep.id,
            idempotency_key=f"{sweep.id}:{index}",
            attempt_number=1,
        )

    await deps.sweep_repository.update_status(sweep.id, SweepStatus.IN_PROGRESS)
    await publish_sweep_status_event(
        deps.realtime_event_bus, deps.sweep_repository, deps.call_repository, sweep.id
    )
    return sweep.id
