import dataclasses
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_call_provider,
    get_realtime_event_bus,
    page_params,
    require_role,
)
from app.api.v1.rate_limit import rate_limit_public_query
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.api.v1.schemas.sweep import (
    PatientMatchOut,
    SweepAccepted,
    SweepOut,
    SweepQueryIn,
    SweepSummaryOut,
)
from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.build_patient_match_response import (
    BuildPatientMatchResponseUseCase,
    PatientMatch,
)
from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.application.use_cases.list_commodities import CommodityFilter, ListCommoditiesUseCase
from app.application.use_cases.list_sweeps import ListSweepsUseCase, SweepFilter
from app.application.use_cases.run_on_demand_sweep import RunOnDemandSweepUseCase
from app.application.use_cases.run_scheduled_sweep import RunScheduledSweepUseCase
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.domain.entities.sweep import Sweep
from app.domain.enums import SweepStatus, UserRole
from app.domain.value_objects.geography_scope import geography_scope_from_dict
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.geo.postgis_geography_resolver import PostGISGeographyResolver

router = APIRouter(prefix="/sweeps", tags=["sweeps"])

_analyst_up = [Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]


async def _resolve_commodity_id(
    commodity_field: str, commodity_repository: CommodityRepositoryPort
) -> UUID:
    try:
        return UUID(commodity_field)
    except ValueError:
        pass

    matches = await ListCommoditiesUseCase(commodity_repository).execute(
        CommodityFilter(search=commodity_field)
    )
    if not matches:
        raise NotFoundError(f"no commodity matching {commodity_field!r}")
    return matches[0].id


def _summary(sweep: Sweep) -> SweepSummaryOut:
    return SweepSummaryOut(**dataclasses.asdict(sweep))


def _match_out(match: PatientMatch) -> PatientMatchOut:
    return PatientMatchOut(**dataclasses.asdict(match))


@router.post("/query", response_model=SweepAccepted, status_code=202)
async def query(
    body: SweepQueryIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    call_provider: CallProviderPort = Depends(get_call_provider),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
    _rate_limit: None = Depends(rate_limit_public_query),
) -> SweepAccepted:
    commodity_repository = SqlAlchemyCommodityRepository(session)
    try:
        commodity_id = await _resolve_commodity_id(body.commodity, commodity_repository)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    geography = geography_scope_from_dict(body.geography.model_dump())

    use_case = RunOnDemandSweepUseCase(
        geography_resolver=PostGISGeographyResolver(session),
        call_repository=SqlAlchemyCallRepository(session),
        sweep_repository=SqlAlchemySweepRepository(session),
        commodity_repository=commodity_repository,
        call_provider=call_provider,
        settings=settings,
        realtime_event_bus=realtime_event_bus,
    )
    sweep_id = await use_case.execute(commodity_id=commodity_id, geography=geography)
    return SweepAccepted(sweep_id=sweep_id)


@router.get("/{sweep_id}", response_model=SweepOut)
async def get_sweep(sweep_id: UUID, session: AsyncSession = Depends(get_session)) -> SweepOut:
    call_repository = SqlAlchemyCallRepository(session)
    sweep_repository = SqlAlchemySweepRepository(session)
    use_case = GetSweepStatusUseCase(
        sweep_repository=sweep_repository, call_repository=call_repository
    )
    try:
        progress = await use_case.execute(sweep_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    matches = await BuildPatientMatchResponseUseCase(
        sweep_repository=sweep_repository,
        call_repository=call_repository,
        availability_result_repository=SqlAlchemyAvailabilityResultRepository(session),
        facility_repository=SqlAlchemyFacilityRepository(session),
    ).execute(sweep_id)

    return SweepOut(**dataclasses.asdict(progress), matches=[_match_out(m) for m in matches])


@router.get("", response_model=Page[SweepSummaryOut], dependencies=_analyst_up)
async def list_sweeps(
    commodity_id: UUID | None = None,
    geography: str | None = None,
    status: SweepStatus | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> Page[SweepSummaryOut]:
    use_case = ListSweepsUseCase(SqlAlchemySweepRepository(session))
    sweeps = await use_case.execute(
        SweepFilter(
            commodity_id=commodity_id,
            geography=geography,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    )
    return paginate([_summary(s) for s in sweeps], page)


@router.post("/scheduled", response_model=SweepAccepted, status_code=202, dependencies=_analyst_up)
async def create_scheduled_sweep(
    body: SweepQueryIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    call_provider: CallProviderPort = Depends(get_call_provider),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> SweepAccepted:
    commodity_repository = SqlAlchemyCommodityRepository(session)
    try:
        commodity_id = await _resolve_commodity_id(body.commodity, commodity_repository)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    geography = geography_scope_from_dict(body.geography.model_dump())

    use_case = RunScheduledSweepUseCase(
        geography_resolver=PostGISGeographyResolver(session),
        call_repository=SqlAlchemyCallRepository(session),
        sweep_repository=SqlAlchemySweepRepository(session),
        commodity_repository=commodity_repository,
        call_provider=call_provider,
        settings=settings,
        realtime_event_bus=realtime_event_bus,
    )
    sweep_id = await use_case.execute(commodity_id=commodity_id, geography=geography)
    return SweepAccepted(sweep_id=sweep_id)
