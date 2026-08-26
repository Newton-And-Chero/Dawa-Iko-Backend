"""SQLAlchemy implementation of `AnalyticsRepositoryPort` — Sprint 08's one
place aggregate SQL against multiple tables lives (RULES.md: "one place to
review query correctness and add indexes against"). Read-only: never writes
to `Sweep`/`Call`/`AvailabilityResult` (workflows/08's rule)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CallStatus, StockStatus
from app.domain.value_objects.analytics import FacilityCallStats, SweepStockSummary
from app.infrastructure.db.models import AvailabilityResultModel, CallModel, SweepModel


class SqlAlchemyAnalyticsRepository:
    """Implements AnalyticsRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_sweep_stock_summaries(
        self,
        commodity_id: UUID,
        *,
        geography: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[SweepStockSummary]:
        # Grouping by SweepModel.id (its primary key) lets Postgres select
        # SweepModel.created_at un-aggregated (functional dependency), so
        # each sweep contributes exactly one row alongside its call/result
        # counts rather than needing a second query per sweep.
        stmt = (
            select(
                SweepModel.id,
                SweepModel.created_at,
                func.count(CallModel.id).label("facilities_checked_count"),
                func.count(AvailabilityResultModel.id)
                .filter(AvailabilityResultModel.in_stock == StockStatus.YES)
                .label("facilities_with_stock_count"),
            )
            .select_from(SweepModel)
            .join(CallModel, CallModel.sweep_id == SweepModel.id)
            .join(
                AvailabilityResultModel,
                AvailabilityResultModel.call_id == CallModel.id,
                isouter=True,
            )
            .where(SweepModel.commodity_id == commodity_id)
            .group_by(SweepModel.id)
            .order_by(SweepModel.created_at)
        )
        if geography is not None:
            stmt = stmt.where(cast(SweepModel.geography_scope, Text).ilike(f"%{geography}%"))
        if date_from is not None:
            stmt = stmt.where(SweepModel.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(SweepModel.created_at <= date_to)

        result = await self._session.execute(stmt)
        return [
            SweepStockSummary(
                sweep_id=row.id,
                created_at=row.created_at,
                facilities_checked_count=row.facilities_checked_count,
                facilities_with_stock_count=row.facilities_with_stock_count,
            )
            for row in result.all()
        ]

    async def facility_call_stats(self, facility_id: UUID) -> FacilityCallStats:
        stmt = select(
            func.count(CallModel.id).label("total_calls"),
            func.count(CallModel.id)
            .filter(CallModel.status == CallStatus.COMPLETED)
            .label("completed_calls"),
        ).where(CallModel.facility_id == facility_id)
        row = (await self._session.execute(stmt)).one()
        return FacilityCallStats(
            facility_id=facility_id,
            total_calls=row.total_calls,
            completed_calls=row.completed_calls,
        )

    async def facility_result_confidences(self, facility_id: UUID) -> list[float]:
        stmt = select(AvailabilityResultModel.confidence).where(
            AvailabilityResultModel.facility_id == facility_id,
            AvailabilityResultModel.confidence.is_not(None),
        )
        result = await self._session.execute(stmt)
        return [c for c in result.scalars().all() if c is not None]

    async def list_facility_ids_with_calls(self) -> list[UUID]:
        stmt = select(CallModel.facility_id).distinct()
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
