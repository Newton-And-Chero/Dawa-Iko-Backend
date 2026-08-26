"""Escalations router: `GET /escalations` (filter by status/severity/geography/
commodity), `POST /escalations/{id}/acknowledge`, `POST /escalations/{id}/resolve`.

Every route requires at least `viewer` (RULES.md's data-minimization
default); acknowledge/resolve are analyst/admin actions — a `Subscriber` has
no login of its own (PROJECT.md's data model keeps Subscriber and User
distinct), so a logged-in analyst relays the subscriber's action.
"""

import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    AUTHENTICATED_ROLES,
    get_realtime_event_bus,
    page_params,
    require_role,
)
from app.api.v1.schemas.escalation import EscalationNoteIn, StockoutAlertOut
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.acknowledge_escalation import AcknowledgeEscalationUseCase
from app.application.use_cases.list_escalations import EscalationFilter, ListEscalationsUseCase
from app.application.use_cases.resolve_escalation import ResolveEscalationUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.enums import EscalationSeverity, EscalationStatus, UserRole
from app.infrastructure.db.repositories.stockout_alert_repository import (
    SqlAlchemyStockoutAlertRepository,
)
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/escalations",
    tags=["escalations"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)

_write_roles = [Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]


def _out(alert: StockoutAlert) -> StockoutAlertOut:
    return StockoutAlertOut(**dataclasses.asdict(alert))


@router.get("", response_model=Page[StockoutAlertOut])
async def list_escalations(
    commodity_id: UUID | None = None,
    status: EscalationStatus | None = None,
    severity: EscalationSeverity | None = None,
    geography: str | None = None,
    page: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> Page[StockoutAlertOut]:
    use_case = ListEscalationsUseCase(SqlAlchemyStockoutAlertRepository(session))
    alerts = await use_case.execute(
        EscalationFilter(
            commodity_id=commodity_id, status=status, severity=severity, geography=geography
        )
    )
    return paginate([_out(a) for a in alerts], page)


@router.post(
    "/{escalation_id}/acknowledge", response_model=StockoutAlertOut, dependencies=_write_roles
)
async def acknowledge_escalation(
    escalation_id: UUID,
    body: EscalationNoteIn = EscalationNoteIn(),
    session: AsyncSession = Depends(get_session),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> StockoutAlertOut:
    use_case = AcknowledgeEscalationUseCase(
        stockout_alert_repository=SqlAlchemyStockoutAlertRepository(session),
        realtime_event_bus=realtime_event_bus,
    )
    try:
        alert = await use_case.execute(escalation_id, note=body.note)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(alert)


@router.post("/{escalation_id}/resolve", response_model=StockoutAlertOut, dependencies=_write_roles)
async def resolve_escalation(
    escalation_id: UUID,
    body: EscalationNoteIn = EscalationNoteIn(),
    session: AsyncSession = Depends(get_session),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> StockoutAlertOut:
    use_case = ResolveEscalationUseCase(
        stockout_alert_repository=SqlAlchemyStockoutAlertRepository(session),
        realtime_event_bus=realtime_event_bus,
    )
    try:
        alert = await use_case.execute(escalation_id, note=body.note)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(alert)
