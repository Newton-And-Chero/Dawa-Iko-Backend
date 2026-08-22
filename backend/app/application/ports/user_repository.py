"""Repository port for User."""

from typing import Protocol
from uuid import UUID

from app.domain.entities.user import User


class UserRepositoryPort(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def add(self, user: User) -> User: ...

    async def list_all(self) -> list[User]: ...
