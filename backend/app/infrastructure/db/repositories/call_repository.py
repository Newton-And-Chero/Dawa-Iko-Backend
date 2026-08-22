"""SQLAlchemy implementation of CallRepositoryPort."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domain.entities.call import Call
from app.infrastructure.db.models import CallModel


def _to_domain(model: CallModel) -> Call:
    return Call(
        id=model.id,
        sweep_id=model.sweep_id,
        facility_id=model.facility_id,
        status=model.status,
        attempt_number=model.attempt_number,
        started_at=model.started_at,
        ended_at=model.ended_at,
        transcript_url=model.transcript_url,
        recording_url=model.recording_url,
        provider_call_id=model.provider_call_id,
        provider_recipient_id=model.provider_recipient_id,
    )


def _to_model(call: Call) -> CallModel:
    return CallModel(
        id=call.id,
        sweep_id=call.sweep_id,
        facility_id=call.facility_id,
        status=call.status,
        attempt_number=call.attempt_number,
        started_at=call.started_at,
        ended_at=call.ended_at,
        transcript_url=call.transcript_url,
        recording_url=call.recording_url,
        provider_call_id=call.provider_call_id,
        provider_recipient_id=call.provider_recipient_id,
    )


class SqlAlchemyCallRepository:
    """Implements CallRepositoryPort."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, call_id: UUID) -> Call | None:
        model = await self._session.get(CallModel, call_id)
        return _to_domain(model) if model is not None else None

    async def add(self, call: Call) -> Call:
        model = _to_model(call)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, call: Call) -> Call:
        model = await self._session.get(CallModel, call.id)
        if model is None:
            raise NotFoundError(f"call {call.id} not found")
        updated = _to_model(call)
        for column in CallModel.__table__.columns:
            if column.name == "id":
                continue
            setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()
        await self._session.refresh(model)
        return _to_domain(model)

    async def bulk_update(self, calls: list[Call]) -> None:
        """Update multiple Call rows in a single commit.

        Used to link a whole chunk's provider_call_id/provider_recipient_id
        atomically after `place_call()` returns: a real (or mock) webhook can
        arrive the instant CALL-E accepts the task, so linking rows one at a
        time — each with its own commit — leaves a window where the webhook
        finds some rows still unlinked and silently skips them forever. A
        single commit means the webhook either sees every row linked or none
        of them (an explicit UnknownCallError to retry), never a partial set.
        """
        for call in calls:
            model = await self._session.get(CallModel, call.id)
            if model is None:
                raise NotFoundError(f"call {call.id} not found")
            updated = _to_model(call)
            for column in CallModel.__table__.columns:
                if column.name == "id":
                    continue
                setattr(model, column.name, getattr(updated, column.name))
        await self._session.commit()

    async def list_all(self) -> list[Call]:
        result = await self._session.execute(select(CallModel))
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_provider_call_id(self, provider_call_id: str) -> list[Call]:
        stmt = select(CallModel).where(CallModel.provider_call_id == provider_call_id)
        result = await self._session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def list_by_sweep_id(self, sweep_id: UUID) -> list[Call]:
        stmt = select(CallModel).where(CallModel.sweep_id == sweep_id)
        result = await self._session.execute(stmt)
        return [_to_domain(m) for m in result.scalars().all()]

    async def get_last_call_for_facility(self, facility_id: UUID) -> Call | None:
        stmt = (
            select(CallModel)
            .where(CallModel.facility_id == facility_id)
            .order_by(CallModel.started_at.desc().nullslast())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalars().first()
        return _to_domain(model) if model is not None else None
