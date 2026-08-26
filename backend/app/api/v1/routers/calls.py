"""Calls read endpoints, plus the manual "call this facility now" retry
action. Responses include transcript/recording URLs, so every route
requires at least `viewer` (RULES.md's data-minimization default)."""

import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    AUTHENTICATED_ROLES,
    get_call_provider,
    get_current_user,
    get_realtime_event_bus,
    page_params,
    require_role,
)
from app.api.v1.schemas.call import CallOut
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.api.v1.schemas.sweep import SweepAccepted
from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.list_calls import ListCallsUseCase
from app.application.use_cases.request_manual_call import RequestManualCallUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.call import Call
from app.domain.entities.user import User
from app.domain.enums import UserRole
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/calls", tags=["calls"], dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))]
)

_write_roles = [Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]


def _out(call: Call) -> CallOut:
    return CallOut(**dataclasses.asdict(call))


@router.get("", response_model=Page[CallOut])
async def list_calls(
    page: PageParams = Depends(page_params), session: AsyncSession = Depends(get_session)
) -> Page[CallOut]:
    use_case = ListCallsUseCase(SqlAlchemyCallRepository(session))
    calls = await use_case.execute()
    return paginate([_out(c) for c in calls], page)


@router.get("/{call_id}", response_model=CallOut)
async def get_call(call_id: UUID, session: AsyncSession = Depends(get_session)) -> CallOut:
    use_case = ListCallsUseCase(SqlAlchemyCallRepository(session))
    try:
        call = await use_case.get(call_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(call)


@router.post(
    "/{call_id}/retry", response_model=SweepAccepted, status_code=202, dependencies=_write_roles
)
async def retry_call(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    call_provider: CallProviderPort = Depends(get_call_provider),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> SweepAccepted:
    use_case = RequestManualCallUseCase(
        call_repository=SqlAlchemyCallRepository(session),
        facility_repository=SqlAlchemyFacilityRepository(session),
        sweep_repository=SqlAlchemySweepRepository(session),
        commodity_repository=SqlAlchemyCommodityRepository(session),
        call_provider=call_provider,
        realtime_event_bus=realtime_event_bus,
    )
    try:
        sweep_id = await use_case.execute_from_call(call_id, requester_id=current_user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SweepAccepted(sweep_id=sweep_id)
