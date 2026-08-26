"""Facility reliability scoring (PROJECT.md 2.8) — `compute_for_facility`/
`compute_for_all` are plain reads used by the `GET /analytics/facility-
reliability` route; `recompute_and_persist_all` is the scheduled batch write
(a Celery Beat task per workflows/08's rule) that caches the result onto
`Facility.reliability_score`. Never called from the webhook/call-handling
hot path."""

from dataclasses import dataclass
from uuid import UUID

from app.application.ports.analytics_repository_port import AnalyticsRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.domain.services.reliability import compute_reliability_score


@dataclass(frozen=True)
class FacilityReliabilityResult:
    facility_id: UUID
    total_calls: int
    completed_calls: int
    answer_rate: float
    avg_result_confidence: float | None
    reliability_score: float


class ComputeFacilityReliabilityUseCase:
    def __init__(
        self,
        analytics_repository: AnalyticsRepositoryPort,
        facility_repository: FacilityRepositoryPort,
    ) -> None:
        self._analytics = analytics_repository
        self._facilities = facility_repository

    async def compute_for_facility(self, facility_id: UUID) -> FacilityReliabilityResult:
        stats = await self._analytics.facility_call_stats(facility_id)
        confidences = await self._analytics.facility_result_confidences(facility_id)
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        score = compute_reliability_score(
            answer_rate=stats.answer_rate, avg_result_confidence=avg_confidence
        )
        return FacilityReliabilityResult(
            facility_id=facility_id,
            total_calls=stats.total_calls,
            completed_calls=stats.completed_calls,
            answer_rate=stats.answer_rate,
            avg_result_confidence=avg_confidence,
            reliability_score=score,
        )

    async def compute_for_all(
        self, facility_ids: list[UUID] | None = None
    ) -> list[FacilityReliabilityResult]:
        ids = (
            facility_ids
            if facility_ids is not None
            else await self._analytics.list_facility_ids_with_calls()
        )
        return [await self.compute_for_facility(facility_id) for facility_id in ids]

    async def recompute_and_persist_all(self) -> list[FacilityReliabilityResult]:
        results = await self.compute_for_all()
        for result in results:
            facility = await self._facilities.get_by_id(result.facility_id)
            if facility is None:
                continue
            facility.reliability_score = result.reliability_score
            await self._facilities.update(facility)
        return results
