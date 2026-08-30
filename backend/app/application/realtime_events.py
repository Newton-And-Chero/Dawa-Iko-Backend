from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.enums import SweepStatus
from app.infrastructure.realtime.channels import ALERTS_CHANNEL, geography_channel, sweep_channel

ENVELOPE_VERSION = 1


def _envelope(event_type: str, sweep_id: UUID | None, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "v": ENVELOPE_VERSION,
        "type": event_type,
        "sweep_id": str(sweep_id) if sweep_id is not None else None,
        "data": data,
        "ts": datetime.now(UTC).isoformat(),
    }


async def publish_call_status_changed(
    bus: RealtimeEventBusPort, call: Call, *, county: str, commodity_id: UUID
) -> None:
    data = {
        "call_id": str(call.id),
        "facility_id": str(call.facility_id),
        "status": call.status.value,
        "attempt_number": call.attempt_number,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
    }
    event = _envelope("call.status_changed", call.sweep_id, data)
    await bus.publish(sweep_channel(call.sweep_id), event)
    await bus.publish(geography_channel(county, commodity_id), event)


async def publish_availability_result_created(
    bus: RealtimeEventBusPort, sweep_id: UUID, result: AvailabilityResult, *, county: str
) -> None:
    data = {
        "id": str(result.id),
        "call_id": str(result.call_id),
        "facility_id": str(result.facility_id),
        "commodity_id": str(result.commodity_id),
        "in_stock": result.in_stock.value,
        "quantity_band": result.quantity_band,
        "price_kes": str(result.price_kes) if result.price_kes is not None else None,
        "last_restock_date": result.last_restock_date.isoformat()
        if result.last_restock_date
        else None,
        "can_hold": result.can_hold,
        "hold_duration_hours": result.hold_duration_hours,
        "confidence": result.confidence,
    }
    event = _envelope("availability_result.created", sweep_id, data)
    await bus.publish(sweep_channel(sweep_id), event)
    await bus.publish(geography_channel(county, result.commodity_id), event)


async def publish_sweep_status_event(
    bus: RealtimeEventBusPort,
    sweep_repository: SweepRepositoryPort,
    call_repository: CallRepositoryPort,
    sweep_id: UUID,
) -> None:
    progress = await GetSweepStatusUseCase(sweep_repository, call_repository).execute(sweep_id)
    event_type = "sweep.completed" if progress.status == SweepStatus.COMPLETED else "sweep.progress"
    data = {
        "status": progress.status.value,
        "total_calls": progress.total_calls,
        "counts_by_status": {k.value: v for k, v in progress.counts_by_status.items()},
    }
    await bus.publish(sweep_channel(sweep_id), _envelope(event_type, sweep_id, data))


def _alert_data(alert: StockoutAlert) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "commodity_id": str(alert.commodity_id),
        "geography": alert.geography,
        "severity": alert.severity.value,
        "facilities_checked_count": alert.facilities_checked_count,
        "facilities_with_stock_count": alert.facilities_with_stock_count,
        "status": alert.status.value,
        "triggered_at": alert.triggered_at.isoformat(),
    }


async def publish_alert_created_event(bus: RealtimeEventBusPort, alert: StockoutAlert) -> None:
    event = _envelope("alert.created", None, _alert_data(alert))
    await bus.publish(ALERTS_CHANNEL, event)


async def publish_alert_updated_event(bus: RealtimeEventBusPort, alert: StockoutAlert) -> None:
    event = _envelope("alert.updated", None, _alert_data(alert))
    await bus.publish(ALERTS_CHANNEL, event)
