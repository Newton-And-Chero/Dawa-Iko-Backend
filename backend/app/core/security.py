"""Authentication/authorization primitives (Sprint 05): JWT issuance and
verification, and argon2 password hashing. `User` authenticates by
`phone_number` (no email field on the entity — see workflows/05).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import Settings
from app.domain.entities.user import User

_hasher = PasswordHasher()


@dataclass
class TokenPayload:
    user_id: UUID


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    return TokenPayload(user_id=UUID(payload["sub"]))
