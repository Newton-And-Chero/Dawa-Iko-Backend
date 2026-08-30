from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import WebhookEventModel


class SqlAlchemyWebhookEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def was_processed(self, event_id: str) -> bool:
        stmt = select(WebhookEventModel.id).where(WebhookEventModel.id == event_id)
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def mark_processed(self, event_id: str) -> bool:
        stmt = (
            insert(WebhookEventModel)
            .values(id=event_id)
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(WebhookEventModel.id)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.first() is not None
