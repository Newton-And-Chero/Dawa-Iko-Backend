from collections.abc import Callable, Coroutine
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.page import PageParams
from app.application.ports.call_gate_port import CallGatePort
from app.application.ports.call_provider_port import CallProviderPort
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.domain.entities.user import User
from app.domain.enums import UserRole
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.call_e.factory import build_call_provider
from app.infrastructure.call_e.redis_call_gate import RedisCallGate
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.realtime.event_bus import RealtimeEventBus

_bearer_scheme = HTTPBearer(auto_error=False)

AUTHENTICATED_ROLES = (UserRole.ADMIN, UserRole.ANALYST, UserRole.VIEWER)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        token_payload = decode_access_token(credentials.credentials, settings)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc

    user = await SqlAlchemyUserRepository(session).get_by_id(token_payload.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user no longer exists")
    return user


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="insufficient role")
        return current_user

    return _check


def get_call_provider(settings: Settings = Depends(get_settings)) -> CallProviderPort:
    return build_call_provider(settings)


def get_call_gate(settings: Settings = Depends(get_settings)) -> CallGatePort:
    return RedisCallGate(get_redis(), settings)


def get_realtime_event_bus() -> RealtimeEventBusPort:
    return RealtimeEventBus(get_redis())


def page_params(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PageParams:
    return PageParams(limit=limit, offset=offset)
