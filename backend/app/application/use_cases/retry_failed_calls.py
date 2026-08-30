from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.application.use_cases._sweep_dispatch import dispatch_call_chunk
from app.core.config import Settings
from app.domain.enums import CallStatus, SweepStatus
from app.domain.services.call_list_policy import is_eligible_for_retry


@dataclass
class RetryResult:
    retried_count: int


class RetryFailedCallsUseCase:
    def __init__(
        self,
        call_repository: CallRepositoryPort,
        facility_repository: FacilityRepositoryPort,
        sweep_repository: SweepRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        call_provider: CallProviderPort,
        settings: Settings,
    ) -> None:
        self._calls = call_repository
        self._facilities = facility_repository
        self._sweeps = sweep_repository
        self._commodities = commodity_repository
        self._call_provider = call_provider
        self._settings = settings

    async def execute(self, now: datetime | None = None) -> RetryResult:
        now = now or datetime.now(UTC)
        all_calls = await self._calls.list_all()
        candidates = [c for c in all_calls if c.status in (CallStatus.NO_ANSWER, CallStatus.FAILED)]

        retried_count = 0
        for call in candidates:
            if not is_eligible_for_retry(
                call.status,
                call.attempt_number,
                call.ended_at,
                now,
                self._settings.RETRY_DELAY_HOURS,
                self._settings.MAX_CALL_ATTEMPTS,
            ):
                continue

            facility = await self._facilities.get_by_id(call.facility_id)
            sweep = await self._sweeps.get_by_id(call.sweep_id)
            if facility is None or sweep is None:
                continue
            commodity = await self._commodities.get_by_id(sweep.commodity_id)
            if commodity is None:
                continue

            next_attempt = call.attempt_number + 1
            await dispatch_call_chunk(
                self._calls,
                self._call_provider,
                commodity_name=commodity.name,
                facilities=[facility],
                sweep_id=sweep.id,
                idempotency_key=f"{sweep.id}:retry:{call.id}:{next_attempt}",
                attempt_number=next_attempt,
                demo_redirect_numbers=self._settings.CALL_DEMO_REDIRECT_NUMBERS,
            )
            await self._sweeps.update_status(sweep.id, SweepStatus.IN_PROGRESS)
            retried_count += 1

        return RetryResult(retried_count=retried_count)
