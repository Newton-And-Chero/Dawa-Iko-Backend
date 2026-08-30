from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.ports.availability_result_repository import AvailabilityResultRepositoryPort
from app.application.ports.call_repository import CallRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.application.ports.sweep_repository import SweepRepositoryPort
from app.core.exceptions import NotFoundError
from app.domain.enums import StockStatus
from app.domain.services.geo import haversine_meters
from app.domain.value_objects.geography_scope import (
    NearestNScope,
    RadiusScope,
    geography_scope_from_dict,
)


@dataclass
class PatientMatch:
    facility_id: UUID
    facility_name: str
    distance_meters: float | None
    price_kes: Decimal | None
    can_hold: bool | None
    hold_reference_code: str | None
    confidence: float | None


def _origin_point(geography_scope: dict[str, Any]) -> tuple[float, float] | None:
    scope = geography_scope_from_dict(geography_scope)
    if isinstance(scope, RadiusScope | NearestNScope):
        return (scope.lat, scope.lng)
    return None


def _rank_key(match: PatientMatch) -> tuple[float, float]:
    distance = match.distance_meters if match.distance_meters is not None else float("inf")
    return (distance, -(match.confidence or 0.0))


class BuildPatientMatchResponseUseCase:
    def __init__(
        self,
        sweep_repository: SweepRepositoryPort,
        call_repository: CallRepositoryPort,
        availability_result_repository: AvailabilityResultRepositoryPort,
        facility_repository: FacilityRepositoryPort,
    ) -> None:
        self._sweeps = sweep_repository
        self._calls = call_repository
        self._results = availability_result_repository
        self._facilities = facility_repository

    async def execute(self, sweep_id: UUID) -> list[PatientMatch]:
        sweep = await self._sweeps.get_by_id(sweep_id)
        if sweep is None:
            raise NotFoundError(f"sweep {sweep_id} not found")

        origin = _origin_point(sweep.geography_scope)
        calls = await self._calls.list_by_sweep_id(sweep_id)

        matches: list[PatientMatch] = []
        for call in calls:
            result = await self._results.get_by_call_id(call.id)
            if result is None or result.in_stock != StockStatus.YES:
                continue
            facility = await self._facilities.get_by_id(call.facility_id)
            if facility is None:
                continue
            distance = (
                haversine_meters(origin[0], origin[1], facility.gps_lat, facility.gps_lng)
                if origin is not None
                else None
            )
            matches.append(
                PatientMatch(
                    facility_id=facility.id,
                    facility_name=facility.name,
                    distance_meters=distance,
                    price_kes=result.price_kes,
                    can_hold=result.can_hold,
                    hold_reference_code=result.hold_reference_code,
                    confidence=result.confidence,
                )
            )

        return sorted(matches, key=_rank_key)
