"""GET /sweeps/{sweep_id}/stream — SSE fallback for `WS /ws/sweeps/{sweep_id}`
(Sprint 06): the same `sweep:{sweep_id}` event source, for clients that only
need one-directional streaming (PROJECT.md 2.6 lists both WS and SSE as
acceptable).

Public, mirroring `POST /sweeps/query`'s own access and the sweep WS route's
(RULES.md/workflows/06) — it only ever exposes the one `sweep_id` in the URL.
"""

import dataclasses
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_realtime_event_bus
from app.api.v1.schemas.sweep import PatientMatchOut, SweepOut
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.build_patient_match_response import BuildPatientMatchResponseUseCase
from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.core.exceptions import NotFoundError
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import get_session
from app.infrastructure.realtime.channels import sweep_channel

router = APIRouter(prefix="/sweeps", tags=["sweeps"])


def _sse_frame(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"


async def _event_stream(
    sweep_id: UUID, snapshot: dict[str, Any], bus: RealtimeEventBusPort
) -> AsyncIterator[str]:
    yield _sse_frame(
        {
            "v": 1,
            "type": "sweep.snapshot",
            "sweep_id": str(sweep_id),
            "data": snapshot,
            "ts": datetime.now(UTC).isoformat(),
        }
    )
    async for event in bus.subscribe(sweep_channel(sweep_id)):
        yield _sse_frame(event)


@router.get("/{sweep_id}/stream")
async def stream_sweep(
    sweep_id: UUID,
    session: AsyncSession = Depends(get_session),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> StreamingResponse:
    call_repository = SqlAlchemyCallRepository(session)
    sweep_repository = SqlAlchemySweepRepository(session)
    use_case = GetSweepStatusUseCase(
        sweep_repository=sweep_repository, call_repository=call_repository
    )
    try:
        progress = await use_case.execute(sweep_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    matches = await BuildPatientMatchResponseUseCase(
        sweep_repository=sweep_repository,
        call_repository=call_repository,
        availability_result_repository=SqlAlchemyAvailabilityResultRepository(session),
        facility_repository=SqlAlchemyFacilityRepository(session),
    ).execute(sweep_id)
    matches_out = [PatientMatchOut(**dataclasses.asdict(m)) for m in matches]
    snapshot = SweepOut(**dataclasses.asdict(progress), matches=matches_out).model_dump(mode="json")

    return StreamingResponse(
        _event_stream(sweep_id, snapshot, realtime_event_bus),
        media_type="text/event-stream",
    )
