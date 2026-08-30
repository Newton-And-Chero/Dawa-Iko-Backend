import logging
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
from app.domain.services.phone import normalize_phone
from app.domain.value_objects.call_task_ref import (
    CallRecipient,
    CallRecipientResultRef,
    CallTaskRef,
)
from app.domain.value_objects.geography_scope import GeographyScope, geography_scope_to_dict

logger = logging.getLogger(__name__)


def _resolve_call_phones(
    facilities: list[Facility], demo_redirect_numbers: list[str] | None
) -> tuple[list[Facility], list[str]]:
    if not demo_redirect_numbers:
        return facilities, [f.phone_number for f in facilities]

    redirect = [normalize_phone(n) for n in demo_redirect_numbers]
    kept = facilities[: len(redirect)]
    if len(kept) < len(facilities):
        logger.warning(
            "CALL_DEMO_REDIRECT_NUMBERS active: dialing %d of %d facilities this chunk, "
            "all redirected to demo numbers",
            len(kept),
            len(facilities),
        )
    return kept, redirect[: len(kept)]


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
    demo_redirect_numbers: list[str] | None = None,
) -> CallTaskRef:
    facilities, call_phones = _resolve_call_phones(facilities, demo_redirect_numbers)

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
            phones=[phone],
            region=CALLE_RECIPIENT_REGION,
            locale=CALLE_RECIPIENT_LOCALE,
        )
        for phone in call_phones
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

    recipients_in_order = _recipients_in_request_order(call_task, call_phones)
    for call, phone, recipient_ref in zip(calls, call_phones, recipients_in_order, strict=True):
        call.provider_call_id = call_task.id
        call.provider_recipient_id = recipient_ref.id if recipient_ref is not None else None
        if recipient_ref is None:
            logger.warning(
                "CALL-E task %s returned no recipient matching phone %s; webhook results "
                "for this call cannot be correlated",
                call_task.id,
                phone,
            )
    await call_repository.bulk_update(calls)

    return call_task


def _recipients_in_request_order(
    call_task: CallTaskRef, call_phones: list[str]
) -> list[CallRecipientResultRef | None]:
    originals = list(call_task.recipients)
    used: set[int] = set()
    ordered: list[CallRecipientResultRef | None] = []
    for index, phone in enumerate(call_phones):
        pick = next(
            (i for i, r in enumerate(originals) if i not in used and phone in r.phones), None
        )
        if pick is None and index < len(originals) and index not in used:
            pick = index
        if pick is None:
            ordered.append(None)
            continue
        used.add(pick)
        ordered.append(originals[pick])
    return ordered


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
            demo_redirect_numbers=deps.settings.CALL_DEMO_REDIRECT_NUMBERS,
        )

    await deps.sweep_repository.update_status(sweep.id, SweepStatus.IN_PROGRESS)
    await publish_sweep_status_event(
        deps.realtime_event_bus, deps.sweep_repository, deps.call_repository, sweep.id
    )
    return sweep.id
