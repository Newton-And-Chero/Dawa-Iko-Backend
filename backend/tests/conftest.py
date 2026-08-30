from collections.abc import AsyncGenerator, Awaitable, Callable
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.manage_users import ManageUsersUseCase, NewUser
from app.core.config import get_settings
from app.core.security import create_access_token
from app.domain.entities.user import User
from app.domain.enums import UserRole
from app.infrastructure.db.models import Base
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import async_session_factory, engine
from app.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _dispose_engine_at_session_end() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def make_user_token(
    db_session: AsyncSession,
) -> Callable[[UserRole], Awaitable[tuple[User, str]]]:
    async def _make(role: UserRole) -> tuple[User, str]:
        use_case = ManageUsersUseCase(SqlAlchemyUserRepository(db_session))
        user = await use_case.add_user(
            NewUser(
                name=f"Test {role.value}",
                role=role,
                phone_number=f"+2547{uuid4().int % 10**8:08d}",
                password="testpass123",
            )
        )
        token = create_access_token(user, get_settings())
        return user, token

    return _make
