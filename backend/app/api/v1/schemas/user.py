"""Auth + user-management schemas. Login is phone_number/password — the
`User` domain entity has no email field (see workflows/05)."""

from uuid import UUID

from pydantic import BaseModel

from app.domain.enums import UserRole


class LoginIn(BaseModel):
    phone_number: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    name: str
    role: UserRole
    org: str | None
    phone_number: str | None
    # Deliberately no password_hash field — never serialized to a client.


class UserCreateIn(BaseModel):
    name: str
    role: UserRole
    phone_number: str
    password: str
    org: str | None = None


class UserEditIn(BaseModel):
    name: str | None = None
    role: UserRole | None = None
    org: str | None = None
    phone_number: str | None = None
    password: str | None = None
