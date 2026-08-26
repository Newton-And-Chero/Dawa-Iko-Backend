"""WS /ws/sweeps/{sweep_id} — live sweep progress (Sprint 06). On connect,
sends a `sweep.snapshot` of the sweep's current state (so a client joining
mid-sweep isn't stuck waiting for the next event), then streams
`call.status_changed` / `availability_result.created` / `sweep.progress` /
`sweep.completed` events as they're published.

Deliberately unauthenticated, mirroring `POST /sweeps/query`'s own public
access (RULES.md/workflows/06): it only ever exposes the one `sweep_id`
already in the URL, never the full sweep list or the live geography feed.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.schemas.sweep import SweepOut
from app.api.v1.websocket.connection_manager import get_connection_manager
from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.core.exceptions import NotFoundError
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.realtime.channels import sweep_channel

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/sweeps/{sweep_id}")
async def sweep_ws(websocket: WebSocket, sweep_id: UUID) -> None:
    async with async_session_factory() as session:
        use_case = GetSweepStatusUseCase(
            SqlAlchemySweepRepository(session), SqlAlchemyCallRepository(session)
        )
        try:
            progress = await use_case.execute(sweep_id)
        except NotFoundError:
            await websocket.close(code=4404)
            return
        snapshot = SweepOut(**dataclasses.asdict(progress))

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
            # This route only pushes; nothing meaningful for a client to send.
            # Awaiting a receive is just how a FastAPI WS handler detects the
            # client disconnecting (raises WebSocketDisconnect below).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)
