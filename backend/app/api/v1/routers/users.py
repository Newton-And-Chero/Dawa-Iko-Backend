"""Admin-only user management."""

import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import page_params, require_role
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.api.v1.schemas.user import UserCreateIn, UserEditIn, UserOut
from app.application.use_cases.manage_users import ManageUsersUseCase, NewUser, UserEdit
from app.core.exceptions import NotFoundError
from app.domain.entities.user import User
from app.domain.enums import UserRole
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/users", tags=["users"], dependencies=[Depends(require_role(UserRole.ADMIN))]
)


def _out(user: User) -> UserOut:
    return UserOut(**dataclasses.asdict(user))


@router.get("", response_model=Page[UserOut])
async def list_users(
    page: PageParams = Depends(page_params), session: AsyncSession = Depends(get_session)
) -> Page[UserOut]:
    use_case = ManageUsersUseCase(SqlAlchemyUserRepository(session))
    users = await use_case.list_users()
    return paginate([_out(u) for u in users], page)


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreateIn, session: AsyncSession = Depends(get_session)) -> UserOut:
    use_case = ManageUsersUseCase(SqlAlchemyUserRepository(session))
    user = await use_case.add_user(NewUser(**body.model_dump()))
    return _out(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: UUID, session: AsyncSession = Depends(get_session)) -> UserOut:
    use_case = ManageUsersUseCase(SqlAlchemyUserRepository(session))
    try:
        user = await use_case.get_user(user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def edit_user(
    user_id: UUID, body: UserEditIn, session: AsyncSession = Depends(get_session)
) -> UserOut:
    use_case = ManageUsersUseCase(SqlAlchemyUserRepository(session))
    try:
        user = await use_case.edit_user(user_id, UserEdit(**body.model_dump()))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(user)
