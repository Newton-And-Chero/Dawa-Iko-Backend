import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import AUTHENTICATED_ROLES, page_params, require_role
from app.api.v1.schemas.facility import FacilityEditIn, FacilityIn, FacilityOut, VerifyPhoneIn
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.application.use_cases.list_facilities import FacilityFilter, ListFacilitiesUseCase
from app.application.use_cases.manage_facilities import (
    FacilityEdit,
    ManageFacilitiesUseCase,
    NewFacility,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.domain.entities.facility import Facility
from app.domain.enums import FacilitySource, FacilityType, UserRole
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/facilities",
    tags=["facilities"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)

_write_roles = [Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]


def _out(facility: Facility) -> FacilityOut:
    return FacilityOut(**dataclasses.asdict(facility))


@router.get("", response_model=Page[FacilityOut])
async def list_facilities(
    county: str | None = None,
    sub_county: str | None = None,
    ward: str | None = None,
    type: FacilityType | None = None,
    source: FacilitySource | None = None,
    page: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> Page[FacilityOut]:
    use_case = ListFacilitiesUseCase(SqlAlchemyFacilityRepository(session))
    facilities = await use_case.execute(
        FacilityFilter(county=county, sub_county=sub_county, ward=ward, type=type, source=source)
    )
    return paginate([_out(f) for f in facilities], page)


@router.get("/{facility_id}", response_model=FacilityOut)
async def get_facility(
    facility_id: UUID, session: AsyncSession = Depends(get_session)
) -> FacilityOut:
    use_case = ListFacilitiesUseCase(SqlAlchemyFacilityRepository(session))
    try:
        facility = await use_case.get(facility_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(facility)


@router.post("", response_model=FacilityOut, status_code=201, dependencies=_write_roles)
async def create_facility(
    body: FacilityIn, session: AsyncSession = Depends(get_session)
) -> FacilityOut:
    use_case = ManageFacilitiesUseCase(SqlAlchemyFacilityRepository(session))
    try:
        facility = await use_case.add_facility(NewFacility(**body.model_dump()))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(facility)


@router.patch("/{facility_id}", response_model=FacilityOut, dependencies=_write_roles)
async def edit_facility(
    facility_id: UUID, body: FacilityEditIn, session: AsyncSession = Depends(get_session)
) -> FacilityOut:
    use_case = ManageFacilitiesUseCase(SqlAlchemyFacilityRepository(session))
    try:
        facility = await use_case.edit_facility(facility_id, FacilityEdit(**body.model_dump()))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _out(facility)


@router.post("/{facility_id}/verify-phone", response_model=FacilityOut, dependencies=_write_roles)
async def verify_facility_phone(
    facility_id: UUID, body: VerifyPhoneIn, session: AsyncSession = Depends(get_session)
) -> FacilityOut:
    use_case = ManageFacilitiesUseCase(SqlAlchemyFacilityRepository(session))
    try:
        facility = await use_case.set_phone_verification_status(facility_id, body.status)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(facility)
