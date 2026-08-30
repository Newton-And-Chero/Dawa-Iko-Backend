from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import AUTHENTICATED_ROLES, require_role
from app.api.v1.schemas.analytics import (
    FacilityReliabilityOut,
    StockoutAnalyticsOut,
    WatchlistTrendsOut,
)
from app.application.use_cases.compute_facility_reliability import (
    ComputeFacilityReliabilityUseCase,
)
from app.application.use_cases.compute_stockout_analytics import ComputeStockoutAnalyticsUseCase
from app.application.use_cases.compute_watchlist_trends import ComputeWatchlistTrendsUseCase
from app.application.use_cases.export_report import ExportFormat, ExportReportUseCase, ReportName
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.services.stockout_analytics import BucketGranularity
from app.infrastructure.db.repositories.analytics_repository import SqlAlchemyAnalyticsRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)


@router.get("/stockout-rate", response_model=StockoutAnalyticsOut)
async def stockout_rate(
    commodity_id: UUID,
    geography: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    granularity: BucketGranularity = "week",
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StockoutAnalyticsOut:
    use_case = ComputeStockoutAnalyticsUseCase(
        SqlAlchemyAnalyticsRepository(session),
        SqlAlchemyCommodityRepository(session),
        stockout_threshold_pct=settings.STOCKOUT_THRESHOLD_PCT,
    )
    try:
        result = await use_case.execute(
            commodity_id,
            geography=geography,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StockoutAnalyticsOut.from_result(result)


@router.get("/facility-reliability", response_model=list[FacilityReliabilityOut])
async def facility_reliability(
    facility_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[FacilityReliabilityOut]:
    use_case = ComputeFacilityReliabilityUseCase(
        SqlAlchemyAnalyticsRepository(session), SqlAlchemyFacilityRepository(session)
    )
    results = (
        [await use_case.compute_for_facility(facility_id)]
        if facility_id is not None
        else await use_case.compute_for_all()
    )
    return [FacilityReliabilityOut.from_result(r) for r in results]


@router.get("/watchlist-trends", response_model=WatchlistTrendsOut)
async def watchlist_trends(
    county: list[str] = Query(
        ..., description="Counties to compare, e.g. ?county=Kirinyaga&county=Nairobi"
    ),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> WatchlistTrendsOut:
    use_case = ComputeWatchlistTrendsUseCase(
        SqlAlchemyAnalyticsRepository(session),
        SqlAlchemyCommodityRepository(session),
        stockout_threshold_pct=settings.STOCKOUT_THRESHOLD_PCT,
    )
    result = await use_case.execute(county)
    return WatchlistTrendsOut.from_result(result)


@router.get("/export")
async def export(
    report: ReportName,
    format: ExportFormat = "csv",
    commodity_id: UUID | None = None,
    geography: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    granularity: BucketGranularity = "week",
    county: list[str] | None = Query(default=None),
    facility_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> Response:
    use_case = ExportReportUseCase(
        SqlAlchemyAnalyticsRepository(session),
        SqlAlchemyCommodityRepository(session),
        SqlAlchemyFacilityRepository(session),
        stockout_threshold_pct=settings.STOCKOUT_THRESHOLD_PCT,
    )
    try:
        exported = await use_case.execute(
            report,
            format,
            commodity_id=commodity_id,
            geography=geography,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
            counties=county,
            facility_id=facility_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename="{exported.filename}"'},
    )
