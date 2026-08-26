"""POST /webhooks/calle/{webhook_token} — inbound CALL-E webhook receiver.

Not part of the public API surface: deliberately mounted outside the `/v1`
prefix and never exposed in any future public OpenAPI spec. Every check here
is defensive input validation, not business logic — see RULES.md's CALL-E
section: CALL-E signs nothing, so this endpoint must never trust the request
on its own say-so.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_realtime_event_bus
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.handle_calle_webhook import HandleCalleWebhookUseCase
from app.core.exceptions import UnknownCallError
from app.core.webhook_security import is_valid_webhook_token
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.repositories.webhook_event_repository import (
    SqlAlchemyWebhookEventRepository,
)
from app.infrastructure.db.session import get_session

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/calle/{webhook_token}")
async def receive_calle_webhook(
    webhook_token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),  # noqa: B008 (standard FastAPI DI pattern)
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
) -> dict[str, bool]:
    if not is_valid_webhook_token(webhook_token):
        # 404, not 403/401 — don't confirm the endpoint exists to a guesser.
        raise HTTPException(status_code=404)

    try:
        body: dict[str, Any] = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    event_id_header = request.headers.get("CALL-E-Event-Id")
    if not event_id_header or event_id_header != body.get("id"):
        raise HTTPException(status_code=400, detail="CALL-E-Event-Id header missing or mismatched")

    use_case = HandleCalleWebhookUseCase(
        call_repository=SqlAlchemyCallRepository(session),
        availability_result_repository=SqlAlchemyAvailabilityResultRepository(session),
        webhook_event_repository=SqlAlchemyWebhookEventRepository(session),
        sweep_repository=SqlAlchemySweepRepository(session),
        facility_repository=SqlAlchemyFacilityRepository(session),
        realtime_event_bus=realtime_event_bus,
    )
    try:
        await use_case.handle(
            event_id=body["id"],
            event_type=body.get("type", ""),
            call_data=body.get("data") or {},
        )
    except UnknownCallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"ok": True}
