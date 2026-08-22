"""SQLAlchemy implementation of UserRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.infrastructure.db.models import UserModel


def _to_domain(model: UserModel) -> User:
    return User(
        id=model.id,
        name=model.name,
        role=model.role,
        org=model.org,
        phone_number=model.phone_number,
    )


def _to_model(user: User) -> UserModel:
    return UserModel(
        id=user.id,
        name=user.name,
        role=user.role,
        org=user.org,
        phone_number=user.phone_number,
    )


class SqlAlchemyUserRepository:
    """Implements UserRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_domain(model) if model is not None else None

    async def add(self, user: User) -> User:
        model = _to_model(user)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def list_all(self) -> list[User]:
        result = await self._session.execute(select(UserModel))
        return [_to_domain(m) for m in result.scalars().all()]
