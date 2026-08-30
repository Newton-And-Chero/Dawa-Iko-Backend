import dataclasses
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import AUTHENTICATED_ROLES, page_params, require_role
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.api.v1.schemas.subscriber import SubscriberEditIn, SubscriberIn, SubscriberOut
from app.application.use_cases.list_subscribers import ListSubscribersUseCase
from app.application.use_cases.manage_subscribers import (
    ManageSubscribersUseCase,
    NewSubscriber,
    SubscriberEdit,
)
from app.core.exceptions import NotFoundError
from app.domain.entities.subscriber import Subscriber
from app.domain.enums import UserRole
from app.infrastructure.db.repositories.subscriber_repository import SqlAlchemySubscriberRepository
from app.infrastructure.db.session import get_session

router = APIRouter(
    prefix="/subscribers",
    tags=["subscribers"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)

_admin_only = [Depends(require_role(UserRole.ADMIN))]


def _out(subscriber: Subscriber) -> SubscriberOut:
    return SubscriberOut(**dataclasses.asdict(subscriber))


@router.get("", response_model=Page[SubscriberOut])
async def list_subscribers(
    page: PageParams = Depends(page_params), session: AsyncSession = Depends(get_session)
) -> Page[SubscriberOut]:
    use_case = ListSubscribersUseCase(SqlAlchemySubscriberRepository(session))
    subscribers = await use_case.execute()
    return paginate([_out(s) for s in subscribers], page)


@router.get("/{subscriber_id}", response_model=SubscriberOut)
async def get_subscriber(
    subscriber_id: UUID, session: AsyncSession = Depends(get_session)
) -> SubscriberOut:
    use_case = ListSubscribersUseCase(SqlAlchemySubscriberRepository(session))
    try:
        subscriber = await use_case.get(subscriber_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(subscriber)


@router.post("", response_model=SubscriberOut, status_code=201, dependencies=_admin_only)
async def create_subscriber(
    body: SubscriberIn, session: AsyncSession = Depends(get_session)
) -> SubscriberOut:
    use_case = ManageSubscribersUseCase(SqlAlchemySubscriberRepository(session))
    subscriber = await use_case.add_subscriber(NewSubscriber(**body.model_dump()))
    return _out(subscriber)


@router.patch("/{subscriber_id}", response_model=SubscriberOut, dependencies=_admin_only)
async def edit_subscriber(
    subscriber_id: UUID, body: SubscriberEditIn, session: AsyncSession = Depends(get_session)
) -> SubscriberOut:
    use_case = ManageSubscribersUseCase(SqlAlchemySubscriberRepository(session))
    try:
        subscriber = await use_case.edit_subscriber(
            subscriber_id, SubscriberEdit(**body.model_dump())
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _out(subscriber)
