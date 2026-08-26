"""POST /auth/login, GET /auth/me."""

import dataclasses

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.api.v1.schemas.user import LoginIn, TokenOut, UserOut
from app.application.use_cases.authenticate_user import AuthenticateUserUseCase
from app.core.config import Settings, get_settings
from app.core.exceptions import InvalidCredentialsError
from app.core.security import create_access_token
from app.domain.entities.user import User
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    use_case = AuthenticateUserUseCase(SqlAlchemyUserRepository(session))
    try:
        user = await use_case.execute(body.phone_number, body.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return TokenOut(access_token=create_access_token(user, settings))


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut(**dataclasses.asdict(current_user))
