"""WS /ws/live?county=&commodity_id=&token= — live geography/commodity feed
behind the dashboard's availability map (PROJECT.md 2.7). On connect, sends a
`geography.snapshot` of the current ranked availability results for that
county+commodity, then streams the same `call.status_changed` /
`availability_result.created` events the matching sweep(s) publish (Sprint
06), fanned out to this channel by `app.application.realtime_events`.

Auth: JWT passed as the `token` query param, not a header or WS subprotocol.
A browser's native WebSocket API can't set custom headers on the handshake
request, and encoding the token into `Sec-WebSocket-Protocol` only trades
that problem for subprotocol-negotiation complexity with no real benefit
here — a query param is the simplest of the two documented options
(workflows/06). Unlike the public per-sweep stream, this channel aggregates
availability data county-wide, so it requires at least a `viewer` token
(RULES.md's data-minimization default), not just a valid one.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.dependencies import AUTHENTICATED_ROLES
from app.api.v1.schemas.availability_result import AvailabilityResultOut
from app.api.v1.websocket.connection_manager import get_connection_manager
from app.application.use_cases.list_availability_results import (
    AvailabilityResultFilter,
    ListAvailabilityResultsUseCase,
)
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import async_session_factory
from app.infrastructure.realtime.channels import geography_channel

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/live")
async def geography_ws(
    websocket: WebSocket, county: str, commodity_id: UUID, token: str = ""
) -> None:
    settings = get_settings()
    try:
        token_payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError:
        await websocket.close(code=4401)
        return

    async with async_session_factory() as session:
        user = await SqlAlchemyUserRepository(session).get_by_id(token_payload.user_id)
        if user is None:
            await websocket.close(code=4401)
            return
        if user.role not in AUTHENTICATED_ROLES:
            await websocket.close(code=4403)
            return

        results = await ListAvailabilityResultsUseCase(
            SqlAlchemyAvailabilityResultRepository(session)
        ).execute(AvailabilityResultFilter(commodity_id=commodity_id, county=county))
        snapshot_results = [
            AvailabilityResultOut(**dataclasses.asdict(r)).model_dump(mode="json") for r in results
        ]

    channel = geography_channel(county, commodity_id)
    manager = get_connection_manager()
    await manager.connect(channel, websocket)
    try:
        await websocket.send_json(
            {
                "v": 1,
                "type": "geography.snapshot",
                "sweep_id": None,
                "data": {
                    "county": county,
                    "commodity_id": str(commodity_id),
                    "results": snapshot_results,
                },
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)
