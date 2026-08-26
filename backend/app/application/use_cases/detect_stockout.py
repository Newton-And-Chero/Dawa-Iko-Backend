"""Zero/below-threshold availability detection, hooked into the sweep
completion branch of `HandleCalleWebhookUseCase._maybe_complete_sweep`
(Sprint 04's real "sweep just completed" moment) — never a second,
independent trigger point (RULES.md).

`_sweep_dispatch.dispatch_sweep`'s other completion branch (a sweep whose
candidate list resolved to zero facilities) deliberately never calls this:
it completes with zero calls, and `classify_severity` treats
`facilities_checked_count == 0` as "nothing to detect" by contract — there is
nothing this use case could ever find on that path.
"""

from uuid import UUID

from app.application.ports.availability_result_repository import AvailabilityResultRepositoryPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.ports.stockout_alert_repository import StockoutAlertRepositoryPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.realtime_events import publish_alert_created_event
from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.enums import StockStatus
from app.domain.services.severity import classify_severity


class DetectStockoutUseCase:
    def __init__(
        self,
        sweep_repository: SweepRepositoryPort,
        call_repository: CallRepositoryPort,
        availability_result_repository: AvailabilityResultRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        stockout_alert_repository: StockoutAlertRepositoryPort,
        realtime_event_bus: RealtimeEventBusPort,
        settings: Settings,
    ) -> None:
        self._sweeps = sweep_repository
        self._calls = call_repository
        self._results = availability_result_repository
        self._commodities = commodity_repository
        self._alerts = stockout_alert_repository
        self._realtime_event_bus = realtime_event_bus
        self._settings = settings

    async def execute(self, sweep_id: UUID) -> StockoutAlert | None:
        sweep = await self._sweeps.get_by_id(sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {sweep_id} not found")

        calls = await self._calls.list_by_sweep_id(sweep_id)
        facilities_checked_count = len(calls)
        if facilities_checked_count == 0:
            return None  # nothing was actually checked — not a stockout

        facilities_with_stock_count = 0
        for call in calls:
            result = await self._results.get_by_call_id(call.id)
            if result is not None and result.in_stock == StockStatus.YES:
                facilities_with_stock_count += 1

        pct_in_stock = facilities_with_stock_count / facilities_checked_count
        if pct_in_stock > self._settings.STOCKOUT_THRESHOLD_PCT:
            return None  # plenty of stock — not scarce enough to classify

        commodity = await self._commodities.get_by_id(sweep.commodity_id)
        if commodity is None:
            raise NotFoundError(f"commodity {sweep.commodity_id} not found")

        severity = classify_severity(
            is_priority_watchlist=commodity.is_priority_watchlist,
            facilities_checked_count=facilities_checked_count,
            facilities_with_stock_count=facilities_with_stock_count,
            facility_density=facilities_checked_count,
        )
        if severity is None:
            return None

        alert = await self._alerts.add(
            StockoutAlert(
                commodity_id=sweep.commodity_id,
                geography=sweep.geography_scope,
                severity=severity,
                facilities_checked_count=facilities_checked_count,
                facilities_with_stock_count=facilities_with_stock_count,
            )
        )
        await publish_alert_created_event(self._realtime_event_bus, alert)
        return alert
