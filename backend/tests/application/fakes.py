import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.ports.call_gate_port import CallEngineState
from app.application.use_cases.list_commodities import CommodityFilter
from app.application.use_cases.list_escalations import EscalationFilter
from app.application.use_cases.list_facilities import FacilityFilter
from app.core.exceptions import NotFoundError
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber
from app.domain.entities.sweep import Sweep
from app.domain.enums import NotificationChannel, SweepStatus
from app.domain.value_objects.analytics import FacilityCallStats, SweepStockSummary
from app.domain.value_objects.call_task_ref import (
    CallRecipient,
    CallRecipientResultRef,
    CallTaskRef,
)
from app.domain.value_objects.notification_result import NotificationResult


class InMemoryFacilityRepository:
    def __init__(self) -> None:
        self._facilities: dict[UUID, Facility] = {}

    async def get_by_id(self, facility_id: UUID) -> Facility | None:
        return self._facilities.get(facility_id)

    async def add(self, facility: Facility) -> Facility:
        self._facilities[facility.id] = facility
        return facility

    async def update(self, facility: Facility) -> Facility:
        if facility.id not in self._facilities:
            raise NotFoundError(f"facility {facility.id} not found")
        self._facilities[facility.id] = facility
        return facility

    async def list_all(self) -> list[Facility]:
        return list(self._facilities.values())

    async def list_by_filter(self, facility_filter: FacilityFilter) -> list[Facility]:
        results = list(self._facilities.values())
        if facility_filter.county is not None:
            results = [f for f in results if f.county == facility_filter.county]
        if facility_filter.sub_county is not None:
            results = [f for f in results if f.sub_county == facility_filter.sub_county]
        if facility_filter.ward is not None:
            results = [f for f in results if f.ward == facility_filter.ward]
        if facility_filter.type is not None:
            results = [f for f in results if f.type == facility_filter.type]
        if facility_filter.source is not None:
            results = [f for f in results if f.source == facility_filter.source]
        return results


class InMemoryCommodityRepository:
    def __init__(self) -> None:
        self._commodities: dict[UUID, Commodity] = {}

    async def get_by_id(self, commodity_id: UUID) -> Commodity | None:
        return self._commodities.get(commodity_id)

    async def add(self, commodity: Commodity) -> Commodity:
        self._commodities[commodity.id] = commodity
        return commodity

    async def update(self, commodity: Commodity) -> Commodity:
        if commodity.id not in self._commodities:
            raise NotFoundError(f"commodity {commodity.id} not found")
        self._commodities[commodity.id] = commodity
        return commodity

    async def list_all(self) -> list[Commodity]:
        return list(self._commodities.values())

    async def list_by_filter(self, commodity_filter: CommodityFilter) -> list[Commodity]:
        results = list(self._commodities.values())
        if commodity_filter.category is not None:
            results = [c for c in results if c.category == commodity_filter.category]
        if commodity_filter.is_priority_watchlist is not None:
            results = [
                c
                for c in results
                if c.is_priority_watchlist == commodity_filter.is_priority_watchlist
            ]
        if commodity_filter.search is not None:
            needle = commodity_filter.search.lower()
            results = [
                c
                for c in results
                if needle in c.name.lower() or any(needle in a.lower() for a in c.aliases)
            ]
        return results


class InMemorySweepRepository:
    def __init__(self) -> None:
        self._sweeps: dict[UUID, Sweep] = {}

    async def get_by_id(self, sweep_id: UUID) -> Sweep | None:
        return self._sweeps.get(sweep_id)

    async def add(self, sweep: Sweep) -> Sweep:
        self._sweeps[sweep.id] = sweep
        return sweep

    async def list_all(self) -> list[Sweep]:
        return list(self._sweeps.values())

    async def update_status(self, sweep_id: UUID, status: SweepStatus) -> None:
        sweep = self._sweeps.get(sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {sweep_id} not found")
        sweep.status = status


class InMemoryCallRepository:
    def __init__(self) -> None:
        self._calls: dict[UUID, Call] = {}

    async def get_by_id(self, call_id: UUID) -> Call | None:
        return self._calls.get(call_id)

    async def add(self, call: Call) -> Call:
        self._calls[call.id] = call
        return call

    async def update(self, call: Call) -> Call:
        if call.id not in self._calls:
            raise NotFoundError(f"call {call.id} not found")
        self._calls[call.id] = call
        return call

    async def list_all(self) -> list[Call]:
        return list(self._calls.values())

    async def bulk_update(self, calls: list[Call]) -> None:
        for call in calls:
            if call.id not in self._calls:
                raise NotFoundError(f"call {call.id} not found")
        for call in calls:
            self._calls[call.id] = call

    async def list_by_provider_call_id(self, provider_call_id: str) -> list[Call]:
        return [c for c in self._calls.values() if c.provider_call_id == provider_call_id]

    async def list_by_sweep_id(self, sweep_id: UUID) -> list[Call]:
        return [c for c in self._calls.values() if c.sweep_id == sweep_id]

    async def get_last_call_for_facility(self, facility_id: UUID) -> Call | None:
        calls = [
            c
            for c in self._calls.values()
            if c.facility_id == facility_id and c.started_at is not None
        ]
        if not calls:
            return None
        return max(calls, key=lambda c: c.started_at)  # type: ignore[arg-type, return-value]


class InMemoryAvailabilityResultRepository:
    def __init__(self) -> None:
        self._results: dict[UUID, AvailabilityResult] = {}

    async def get_by_id(self, availability_result_id: UUID) -> AvailabilityResult | None:
        return self._results.get(availability_result_id)

    async def get_by_call_id(self, call_id: UUID) -> AvailabilityResult | None:
        return next((r for r in self._results.values() if r.call_id == call_id), None)

    async def add(self, availability_result: AvailabilityResult) -> AvailabilityResult:
        self._results[availability_result.id] = availability_result
        return availability_result

    async def update(self, availability_result: AvailabilityResult) -> AvailabilityResult:
        if availability_result.id not in self._results:
            raise NotFoundError(f"availability result {availability_result.id} not found")
        self._results[availability_result.id] = availability_result
        return availability_result

    async def list_all(self) -> list[AvailabilityResult]:
        return list(self._results.values())


class InMemoryRealtimeEventBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        self.published.append((channel, event))

    async def subscribe(self, channel: str) -> Any:
        return
        yield


class InMemoryWebhookEventRepository:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    async def was_processed(self, event_id: str) -> bool:
        return event_id in self._seen

    async def mark_processed(self, event_id: str) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        return True


class FakeGeographyResolver:
    def __init__(self, facilities: list[Facility]) -> None:
        self._facilities = facilities

    async def resolve(self, geography: Any) -> list[Facility]:
        return list(self._facilities)


class FakeCallProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def place_call(
        self,
        *,
        task: str,
        recipients: list[CallRecipient],
        result_schema: dict[str, Any] | None,
        recipient_result_schema: dict[str, Any] | None,
        webhook_url: str,
        idempotency_key: str,
        metadata: dict[str, Any] | None = None,
    ) -> CallTaskRef:
        self.calls.append(
            {
                "task": task,
                "recipients": recipients,
                "webhook_url": webhook_url,
                "idempotency_key": idempotency_key,
                "metadata": metadata,
            }
        )
        recipient_refs = [
            CallRecipientResultRef(
                id=f"recip_{secrets.token_hex(4)}",
                phones=list(r.phones),
                status="completed",
                structured_result=None,
                summary=None,
            )
            for r in recipients
        ]
        return CallTaskRef(
            id=f"call_{secrets.token_hex(6)}",
            status="completed",
            task=task,
            recipients=recipient_refs,
            structured_result=None,
            summary=None,
            task_completed=True,
            completion_confidence=None,
            failure_code=None,
            failure_message=None,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
            completed_at=None,
        )

    async def get_call(self, call_id: str) -> CallTaskRef:
        raise NotImplementedError

    async def list_call_events(self, call_id: str) -> list[Any]:
        raise NotImplementedError


class InMemoryStockoutAlertRepository:
    def __init__(self) -> None:
        self._alerts: dict[UUID, StockoutAlert] = {}

    async def get_by_id(self, stockout_alert_id: UUID) -> StockoutAlert | None:
        return self._alerts.get(stockout_alert_id)

    async def add(self, stockout_alert: StockoutAlert) -> StockoutAlert:
        self._alerts[stockout_alert.id] = stockout_alert
        return stockout_alert

    async def update(self, stockout_alert: StockoutAlert) -> StockoutAlert:
        if stockout_alert.id not in self._alerts:
            raise NotFoundError(f"stockout alert {stockout_alert.id} not found")
        self._alerts[stockout_alert.id] = stockout_alert
        return stockout_alert

    async def list_all(self) -> list[StockoutAlert]:
        return list(self._alerts.values())

    async def list_by_filter(self, escalation_filter: EscalationFilter) -> list[StockoutAlert]:
        results = list(self._alerts.values())
        if escalation_filter.commodity_id is not None:
            results = [a for a in results if a.commodity_id == escalation_filter.commodity_id]
        if escalation_filter.status is not None:
            results = [a for a in results if a.status == escalation_filter.status]
        if escalation_filter.severity is not None:
            results = [a for a in results if a.severity == escalation_filter.severity]
        return results


class InMemorySubscriberRepository:
    def __init__(self) -> None:
        self._subscribers: dict[UUID, Subscriber] = {}

    async def get_by_id(self, subscriber_id: UUID) -> Subscriber | None:
        return self._subscribers.get(subscriber_id)

    async def add(self, subscriber: Subscriber) -> Subscriber:
        self._subscribers[subscriber.id] = subscriber
        return subscriber

    async def update(self, subscriber: Subscriber) -> Subscriber:
        if subscriber.id not in self._subscribers:
            raise NotFoundError(f"subscriber {subscriber.id} not found")
        self._subscribers[subscriber.id] = subscriber
        return subscriber

    async def list_all(self) -> list[Subscriber]:
        return list(self._subscribers.values())


class InMemoryAnalyticsRepository:
    def __init__(self) -> None:
        self._summaries: dict[UUID, list[tuple[str | None, SweepStockSummary]]] = {}
        self._facility_stats: dict[UUID, FacilityCallStats] = {}
        self._facility_confidences: dict[UUID, list[float]] = {}

    def seed_summaries(
        self, commodity_id: UUID, geography: str | None, summaries: list[SweepStockSummary]
    ) -> None:
        self._summaries.setdefault(commodity_id, []).extend(
            (geography, summary) for summary in summaries
        )

    def seed_facility_stats(self, stats: FacilityCallStats) -> None:
        self._facility_stats[stats.facility_id] = stats

    def seed_confidences(self, facility_id: UUID, confidences: list[float]) -> None:
        self._facility_confidences[facility_id] = confidences

    async def list_sweep_stock_summaries(
        self,
        commodity_id: UUID,
        *,
        geography: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[SweepStockSummary]:
        rows = self._summaries.get(commodity_id, [])
        result = []
        for row_geography, summary in rows:
            if geography is not None and row_geography != geography:
                continue
            if date_from is not None and summary.created_at < date_from:
                continue
            if date_to is not None and summary.created_at > date_to:
                continue
            result.append(summary)
        return result

    async def facility_call_stats(self, facility_id: UUID) -> FacilityCallStats:
        empty = FacilityCallStats(facility_id=facility_id, total_calls=0, completed_calls=0)
        return self._facility_stats.get(facility_id, empty)

    async def facility_result_confidences(self, facility_id: UUID) -> list[float]:
        return self._facility_confidences.get(facility_id, [])

    async def list_facility_ids_with_calls(self) -> list[UUID]:
        return list(self._facility_stats.keys())


class FakeNotifier:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict[str, Any]] = []

    async def send(
        self,
        *,
        channel: NotificationChannel,
        recipient: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        if self.fail:
            raise RuntimeError("simulated notifier failure")
        self.sent.append(
            {"channel": channel, "recipient": recipient, "message": message, "metadata": metadata}
        )
        return NotificationResult(channel=channel, recipient=recipient, success=True)


class FakeCallGate:
    def __init__(self, *, enabled: bool = True) -> None:
        self.enabled = enabled

    async def is_enabled(self) -> bool:
        return self.enabled

    async def status(self) -> CallEngineState:
        return CallEngineState(enabled=self.enabled, expires_at=None, default_enabled=False)

    async def enable(self, ttl_seconds: int | None = None) -> CallEngineState:
        self.enabled = True
        return await self.status()

    async def disable(self) -> CallEngineState:
        self.enabled = False
        return await self.status()
