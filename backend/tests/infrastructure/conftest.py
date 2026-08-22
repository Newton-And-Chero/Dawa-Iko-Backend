from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import Base
from app.infrastructure.db.session import async_session_factory, engine


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
