"""Validates a CALL-E webhook event and upserts Call + AvailabilityResult rows.

The event's `data` is a raw CALL-E `CallTask` snapshot (untrusted input — CALL-E
signs nothing, see RULES.md). This use case never trusts it blindly: it only
ever updates `Call` rows it already has a queued/in_progress record for, and
deduplicates by event id so a webhook redelivery is a no-op.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.ports.availability_result_repository import AvailabilityResultRepositoryPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.stockout_alert_repository import StockoutAlertRepositoryPort
from app.application.ports.subscriber_repository import SubscriberRepositoryPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.ports.webhook_event_repository import WebhookEventRepositoryPort
from app.application.realtime_events import (
    publish_availability_result_created,
    publish_call_status_changed,
    publish_sweep_status_event,
)
from app.application.use_cases.detect_stockout import DetectStockoutUseCase
from app.application.use_cases.dispatch_escalation import (
    DispatchEscalationUseCase,
    NotifierResolver,
)
from app.core.config import Settings
from app.core.exceptions import UnknownCallError
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.enums import CallStatus, StockStatus, SweepStatus

_PENDING_CALL_STATUSES = {CallStatus.QUEUED, CallStatus.IN_PROGRESS}


def _last_failure_code(recipient: dict[str, Any]) -> str | None:
    attempts = recipient.get("attempts") or []
    if not attempts:
        return None
    code = attempts[-1].get("failure_code")
    return str(code) if code else None


def _map_call_status(recipient_status: str, failure_code: str | None) -> CallStatus:
    if recipient_status == "completed":
        return CallStatus.COMPLETED
    if recipient_status == "skipped":
        return CallStatus.CANCELED
    if recipient_status == "failed":
        code = (failure_code or "").lower()
        if "no_answer" in code:
            return CallStatus.NO_ANSWER
        if "voicemail" in code:
            return CallStatus.VOICEMAIL
        return CallStatus.FAILED
    # "pending"/"in_progress" on a terminal webhook shouldn't happen — handle
    # defensively rather than crash the webhook receiver.
    return CallStatus.IN_PROGRESS


def _extract_result_fields(
    recipient: dict[str, Any], event_type: str, task_confidence: float | None
) -> dict[str, Any]:
    if event_type == "call.result_validation_failed":
        return {
            "in_stock": StockStatus.UNKNOWN,
            "quantity_band": None,
            "price_kes": None,
            "last_restock_date": None,
            "can_hold": None,
            "hold_duration_hours": None,
            "confidence": 0.0,
            "notes": "CALL-E result validation failed — flagged for human review.",
        }

    structured = recipient.get("structured_result")
    if structured is None:
        return {
            "in_stock": StockStatus.UNKNOWN,
            "quantity_band": None,
            "price_kes": None,
            "last_restock_date": None,
            "can_hold": None,
            "hold_duration_hours": None,
            "confidence": None,
            "notes": recipient.get("summary") or "No structured result was returned for this call.",
        }

    price_kes = structured.get("price_kes")
    restock_date = structured.get("last_restock_date")
    hold_hours = structured.get("hold_duration_hours")
    return {
        "in_stock": StockStatus(structured.get("in_stock") or "unknown"),
        "quantity_band": structured.get("quantity_band"),
        "price_kes": Decimal(str(price_kes)) if price_kes is not None else None,
        "last_restock_date": date.fromisoformat(restock_date) if restock_date else None,
        "can_hold": structured.get("can_hold"),
        "hold_duration_hours": int(hold_hours) if hold_hours is not None else None,
        "confidence": task_confidence,
        "notes": structured.get("notes"),
    }


class HandleCalleWebhookUseCase:
    def __init__(
        self,
        call_repository: CallRepositoryPort,
        availability_result_repository: AvailabilityResultRepositoryPort,
        webhook_event_repository: WebhookEventRepositoryPort,
        sweep_repository: SweepRepositoryPort,
        facility_repository: FacilityRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        stockout_alert_repository: StockoutAlertRepositoryPort,
        subscriber_repository: SubscriberRepositoryPort,
        notifier_resolver: NotifierResolver,
        realtime_event_bus: RealtimeEventBusPort,
        settings: Settings,
    ) -> None:
        self._calls = call_repository
        self._results = availability_result_repository
        self._events = webhook_event_repository
        self._sweeps = sweep_repository
        self._facilities = facility_repository
        self._commodities = commodity_repository
        self._alerts = stockout_alert_repository
        self._subscribers = subscriber_repository
        self._notifier_resolver = notifier_resolver
        self._realtime_event_bus = realtime_event_bus
        self._settings = settings

    async def handle(self, *, event_id: str, event_type: str, call_data: dict[str, Any]) -> None:
        is_new = await self._events.mark_processed(event_id)
        if not is_new:
            return  # redelivery of an event we've already processed — no-op

        provider_call_id = call_data["id"]
        calls = await self._calls.list_by_provider_call_id(provider_call_id)
        pending_by_recipient = {
            call.provider_recipient_id: call
            for call in calls
            if call.status in _PENDING_CALL_STATUSES
        }
        if not pending_by_recipient:
            raise UnknownCallError(
                f"no queued/in_progress Call rows for provider_call_id={provider_call_id!r}"
            )

        confidence_data = call_data.get("completion_confidence")
        task_confidence = confidence_data["score"] if confidence_data else None

        commodity_id_by_sweep: dict[UUID, UUID] = {}
        touched_sweep_ids: set[UUID] = set()
        for recipient in call_data.get("recipients", []):
            call = pending_by_recipient.get(recipient.get("id"))
            if call is None:
                continue
            commodity_id = await self._resolve_commodity_id(call.sweep_id, commodity_id_by_sweep)
            await self._apply_recipient(call, recipient, event_type, task_confidence, commodity_id)
            touched_sweep_ids.add(call.sweep_id)

        for sweep_id in touched_sweep_ids:
            await self._maybe_complete_sweep(sweep_id)

    async def _maybe_complete_sweep(self, sweep_id: UUID) -> None:
        """Flip Sweep.status to completed once every Call in it is terminal,
        then publish the sweep's current progress either way — this call's
        webhook always moves the sweep's state forward."""
        calls = await self._calls.list_by_sweep_id(sweep_id)
        if calls and all(call.status not in _PENDING_CALL_STATUSES for call in calls):
            await self._sweeps.update_status(sweep_id, SweepStatus.COMPLETED)
            await self._detect_and_dispatch_stockout(sweep_id)
        await publish_sweep_status_event(
            self._realtime_event_bus, self._sweeps, self._calls, sweep_id
        )

    async def _detect_and_dispatch_stockout(self, sweep_id: UUID) -> None:
        alert = await DetectStockoutUseCase(
            sweep_repository=self._sweeps,
            call_repository=self._calls,
            availability_result_repository=self._results,
            commodity_repository=self._commodities,
            stockout_alert_repository=self._alerts,
            realtime_event_bus=self._realtime_event_bus,
            settings=self._settings,
        ).execute(sweep_id)
        if alert is not None:
            await DispatchEscalationUseCase(
                subscriber_repository=self._subscribers,
                notifier_resolver=self._notifier_resolver,
            ).execute(alert)

    async def _resolve_commodity_id(self, sweep_id: UUID, cache: dict[UUID, UUID]) -> UUID:
        if sweep_id not in cache:
            sweep = await self._sweeps.get_by_id(sweep_id)
            if sweep is None:
                raise UnknownCallError(f"sweep {sweep_id} referenced by call not found")
            cache[sweep_id] = sweep.commodity_id
        return cache[sweep_id]

    async def _apply_recipient(
        self,
        call: Call,
        recipient: dict[str, Any],
        event_type: str,
        task_confidence: float | None,
        commodity_id: UUID,
    ) -> None:
        call.status = _map_call_status(recipient["status"], _last_failure_code(recipient))
        call.ended_at = datetime.now(UTC)
        await self._calls.update(call)

        facility = await self._facilities.get_by_id(call.facility_id)
        if facility is not None:
            await publish_call_status_changed(
                self._realtime_event_bus, call, county=facility.county, commodity_id=commodity_id
            )

        fields = _extract_result_fields(recipient, event_type, task_confidence)
        existing = await self._results.get_by_call_id(call.id)
        if existing is not None:
            for key, value in fields.items():
                setattr(existing, key, value)
            result = await self._results.update(existing)
        else:
            result = await self._results.add(
                AvailabilityResult(
                    call_id=call.id,
                    facility_id=call.facility_id,
                    commodity_id=commodity_id,
                    **fields,
                )
            )

        if facility is not None:
            await publish_availability_result_created(
                self._realtime_event_bus, call.sweep_id, result, county=facility.county
            )
