from dataclasses import dataclass
from uuid import UUID

from app.application.ports.user_repository import UserRepositoryPort
from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.domain.entities.user import User
from app.domain.enums import UserRole
from app.domain.services.phone import validate_phone


@dataclass
class NewUser:
    name: str
    role: UserRole
    phone_number: str
    password: str
    org: str | None = None


@dataclass
class UserEdit:
    name: str | None = None
    role: UserRole | None = None
    org: str | None = None
    phone_number: str | None = None
    password: str | None = None


class ManageUsersUseCase:
    def __init__(self, user_repository: UserRepositoryPort) -> None:
        self._users = user_repository

    async def add_user(self, new_user: NewUser) -> User:
        user = User(
            name=new_user.name,
            role=new_user.role,
            org=new_user.org,
            phone_number=validate_phone(new_user.phone_number),
            password_hash=hash_password(new_user.password),
        )
        return await self._users.add(user)

    async def get_user(self, user_id: UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(f"user {user_id} not found")
        return user

    async def list_users(self) -> list[User]:
        return await self._users.list_all()

    async def edit_user(self, user_id: UUID, edit: UserEdit) -> User:
        user = await self.get_user(user_id)

        if edit.name is not None:
            user.name = edit.name
        if edit.role is not None:
            user.role = edit.role
        if edit.org is not None:
            user.org = edit.org
        if edit.phone_number is not None:
            user.phone_number = validate_phone(edit.phone_number)
        if edit.password is not None:
            user.password_hash = hash_password(edit.password)

        return await self._users.update(user)
