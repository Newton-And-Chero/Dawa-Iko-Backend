from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.enums import UserRole


@dataclass
class User:
    name: str
    role: UserRole
    id: UUID = field(default_factory=uuid4)
    org: str | None = None
    phone_number: str | None = None
    password_hash: str | None = None
