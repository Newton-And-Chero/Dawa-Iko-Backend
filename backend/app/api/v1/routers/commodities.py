"""Commodity CRUD — thin wrappers over Sprint 02's use cases."""

import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import AUTHENTICATED_ROLES, page_params, require_role
from app.api.v1.schemas.commodity import CommodityEditIn, CommodityIn, CommodityOut, WatchlistIn
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.application.use_cases.list_commodities import CommodityFilter, ListCommoditiesUseCase
from app.application.use_cases.manage_commodities import (
    CommodityEdit,
    ManageCommoditiesUseCase,
    NewCommodity,
)
from app.core.exceptions import NotFoundError
from app.domain.entities.commodity import Commodity
from app.domain.enums import CommodityCategory, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/commodities",
    tags=["commodities"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)

_admin_only = [Depends(require_role(UserRole.ADMIN))]


def _out(commodity: Commodity) -> CommodityOut:
    return CommodityOut(**dataclasses.asdict(commodity))


@router.get("", response_model=Page[CommodityOut])
async def list_commodities(
    category: CommodityCategory | None = None,
    is_priority_watchlist: bool | None = None,
    search: str | None = None,
    page: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> Page[CommodityOut]:
    use_case = ListCommoditiesUseCase(SqlAlchemyCommodityRepository(session))
    commodities = await use_case.execute(
        CommodityFilter(
            category=category, is_priority_watchlist=is_priority_watchlist, search=search
        )
    )
    return paginate([_out(c) for c in commodities], page)


@router.get("/{commodity_id}", response_model=CommodityOut)
async def get_commodity(
    commodity_id: UUID, session: AsyncSession = Depends(get_session)
) -> CommodityOut:
    use_case = ListCommoditiesUseCase(SqlAlchemyCommodityRepository(session))
    try:
        commodity = await use_case.get(commodity_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(commodity)


@router.post("", response_model=CommodityOut, status_code=201, dependencies=_admin_only)
async def create_commodity(
    body: CommodityIn, session: AsyncSession = Depends(get_session)
) -> CommodityOut:
    use_case = ManageCommoditiesUseCase(SqlAlchemyCommodityRepository(session))
    commodity = await use_case.add_commodity(NewCommodity(**body.model_dump()))
    return _out(commodity)


@router.patch("/{commodity_id}", response_model=CommodityOut, dependencies=_admin_only)
async def edit_commodity(
    commodity_id: UUID, body: CommodityEditIn, session: AsyncSession = Depends(get_session)
) -> CommodityOut:
    use_case = ManageCommoditiesUseCase(SqlAlchemyCommodityRepository(session))
    try:
        commodity = await use_case.edit_commodity(commodity_id, CommodityEdit(**body.model_dump()))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(commodity)


@router.patch("/{commodity_id}/watchlist", response_model=CommodityOut, dependencies=_admin_only)
async def set_commodity_watchlist(
    commodity_id: UUID, body: WatchlistIn, session: AsyncSession = Depends(get_session)
) -> CommodityOut:
    use_case = ManageCommoditiesUseCase(SqlAlchemyCommodityRepository(session))
    try:
        commodity = await use_case.set_priority_watchlist(commodity_id, body.is_priority_watchlist)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(commodity)
