import logging
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
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
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.enums import CallStatus, StockStatus, SweepStatus

logger = logging.getLogger(__name__)

_PENDING_CALL_STATUSES = {CallStatus.QUEUED, CallStatus.IN_PROGRESS}
_STOCK_VALUES = {status.value for status in StockStatus}


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
    return CallStatus.IN_PROGRESS


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"yes", "true"}:
            return True
        if value.lower() in {"no", "false"}:
            return False
    return None


def _quantity_band(value: Any) -> str | None:
    if isinstance(value, str) and value and value.lower() != "unknown":
        return value
    return None


def _combine_notes(*parts: Any) -> str | None:
    seen: list[str] = []
    for part in parts:
        text = str(part).strip() if part else ""
        if text and text not in seen:
            seen.append(text)
    return " | ".join(seen) or None


def _extract_result_fields(
    recipient: dict[str, Any],
    event_type: str,
    task_confidence: float | None,
    task_evidence: list[str],
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
    if not isinstance(structured, dict):
        return {
            "in_stock": StockStatus.UNKNOWN,
            "quantity_band": None,
            "price_kes": None,
            "last_restock_date": None,
            "can_hold": None,
            "hold_duration_hours": None,
            "confidence": None,
            "notes": _combine_notes(recipient.get("summary"), "; ".join(task_evidence))
            or "No structured result was returned for this call.",
        }

    in_stock = str(structured.get("in_stock") or "unknown").lower()
    return {
        "in_stock": StockStatus(in_stock) if in_stock in _STOCK_VALUES else StockStatus.UNKNOWN,
        "quantity_band": _quantity_band(structured.get("quantity_band")),
        "price_kes": _as_decimal(structured.get("price_kes")),
        "last_restock_date": _as_date(structured.get("last_restock_date")),
        "can_hold": _as_bool(structured.get("can_hold")),
        "hold_duration_hours": _as_int(structured.get("hold_duration_hours")),
        "confidence": task_confidence,
        "notes": _combine_notes(structured.get("notes"), "; ".join(task_evidence)),
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
        if await self._events.was_processed(event_id):
            return

        provider_call_id = call_data["id"]
        calls = await self._calls.list_by_provider_call_id(provider_call_id)
        if not calls:
            logger.warning(
                "CALL-E webhook %s references unknown provider_call_id=%r; acknowledging "
                "without changes",
                event_id,
                provider_call_id,
            )
            return

        calls_by_recipient = {call.provider_recipient_id: call for call in calls}

        confidence_data = call_data.get("completion_confidence")
        task_confidence = (
            confidence_data.get("score") if isinstance(confidence_data, dict) else None
        )
        task_evidence = [str(item) for item in call_data.get("evidence") or []]

        commodity_id_by_sweep: dict[UUID, UUID] = {}
        touched_sweep_ids: set[UUID] = set()
        for recipient in call_data.get("recipients", []):
            call = calls_by_recipient.get(recipient.get("id"))
            if call is None:
                continue
            commodity_id = await self._resolve_commodity_id(call.sweep_id, commodity_id_by_sweep)
            if commodity_id is None:
                continue
            await self._apply_recipient(
                call, recipient, event_type, task_confidence, task_evidence, commodity_id
            )
            touched_sweep_ids.add(call.sweep_id)

        for sweep_id in touched_sweep_ids:
            await self._maybe_complete_sweep(sweep_id)

        await self._events.mark_processed(event_id)

    async def _maybe_complete_sweep(self, sweep_id: UUID) -> None:
        sweep = await self._sweeps.get_by_id(sweep_id)
        already_completed = sweep is not None and sweep.status == SweepStatus.COMPLETED
        calls = await self._calls.list_by_sweep_id(sweep_id)
        if (
            not already_completed
            and calls
            and all(call.status not in _PENDING_CALL_STATUSES for call in calls)
        ):
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

    async def _resolve_commodity_id(self, sweep_id: UUID, cache: dict[UUID, UUID]) -> UUID | None:
        if sweep_id not in cache:
            sweep = await self._sweeps.get_by_id(sweep_id)
            if sweep is None:
                logger.warning(
                    "sweep %s referenced by call not found; skipping recipient", sweep_id
                )
                return None
            cache[sweep_id] = sweep.commodity_id
        return cache[sweep_id]

    async def _apply_recipient(
        self,
        call: Call,
        recipient: dict[str, Any],
        event_type: str,
        task_confidence: float | None,
        task_evidence: list[str],
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

        fields = _extract_result_fields(recipient, event_type, task_confidence, task_evidence)
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
