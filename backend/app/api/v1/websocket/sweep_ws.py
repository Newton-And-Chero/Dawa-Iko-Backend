import dataclasses
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.schemas.sweep import PatientMatchOut, SweepOut
from app.api.v1.websocket.connection_manager import get_connection_manager
from app.application.use_cases.build_patient_match_response import BuildPatientMatchResponseUseCase
from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.core.exceptions import NotFoundError
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.realtime.channels import sweep_channel

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/sweeps/{sweep_id}")
async def sweep_ws(websocket: WebSocket, sweep_id: UUID) -> None:
    async with async_session_factory() as session:
        call_repository = SqlAlchemyCallRepository(session)
        sweep_repository = SqlAlchemySweepRepository(session)
        use_case = GetSweepStatusUseCase(
            sweep_repository=sweep_repository, call_repository=call_repository
        )
        try:
            progress = await use_case.execute(sweep_id)
        except NotFoundError:
            await websocket.close(code=4404)
            return

        matches = await BuildPatientMatchResponseUseCase(
            sweep_repository=sweep_repository,
            call_repository=call_repository,
            availability_result_repository=SqlAlchemyAvailabilityResultRepository(session),
            facility_repository=SqlAlchemyFacilityRepository(session),
        ).execute(sweep_id)
        matches_out = [PatientMatchOut(**dataclasses.asdict(m)) for m in matches]
        snapshot = SweepOut(**dataclasses.asdict(progress), matches=matches_out)

    channel = sweep_channel(sweep_id)
    manager = get_connection_manager()
    await manager.connect(channel, websocket)
    try:
        await websocket.send_json(
            {
                "v": 1,
                "type": "sweep.snapshot",
                "sweep_id": str(sweep_id),
                "data": snapshot.model_dump(mode="json"),
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)
