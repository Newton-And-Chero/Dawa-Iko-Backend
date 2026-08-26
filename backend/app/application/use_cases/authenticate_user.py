"""Login: phone_number + password -> User, for /auth/login to mint a JWT
from. The User entity has no email field, so phone_number is the login
identifier (per workflows/05's explicit allowance for this)."""

from app.application.ports.user_repository import UserRepositoryPort
from app.core.exceptions import InvalidCredentialsError
from app.core.security import verify_password
from app.domain.entities.user import User


class AuthenticateUserUseCase:
    def __init__(self, user_repository: UserRepositoryPort) -> None:
        self._users = user_repository

    async def execute(self, phone_number: str, password: str) -> User:
        user = await self._users.get_by_phone_number(phone_number)
        if user is None or user.password_hash is None:
            raise InvalidCredentialsError("invalid phone number or password")
        if not verify_password(password, user.password_hash):
            raise InvalidCredentialsError("invalid phone number or password")
        return user
