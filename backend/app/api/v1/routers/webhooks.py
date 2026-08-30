import json
from functools import partial
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_realtime_event_bus
from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.application.use_cases.handle_calle_webhook import HandleCalleWebhookUseCase
from app.core.config import Settings, get_settings
from app.core.webhook_security import is_valid_webhook_token
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.stockout_alert_repository import (
    SqlAlchemyStockoutAlertRepository,
)
from app.infrastructure.db.repositories.subscriber_repository import SqlAlchemySubscriberRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.repositories.webhook_event_repository import (
    SqlAlchemyWebhookEventRepository,
)
from app.infrastructure.db.session import get_session
from app.infrastructure.notifications.factory import build_notifier

router = APIRouter(tags=["webhooks"])

_WEBHOOK_EVENT_TYPES = {
    "call.completed",
    "call.failed",
    "call.result_validation_failed",
}


@router.post("/webhooks/calle/{webhook_token}")
async def receive_calle_webhook(
    webhook_token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    realtime_event_bus: RealtimeEventBusPort = Depends(get_realtime_event_bus),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    if not is_valid_webhook_token(webhook_token):
        raise HTTPException(status_code=404)

    try:
        body: dict[str, Any] = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="webhook body must be a JSON object")

    event_id_header = request.headers.get("CALL-E-Event-Id")
    if not event_id_header or event_id_header != body.get("id"):
        raise HTTPException(status_code=400, detail="CALL-E-Event-Id header missing or mismatched")

    event_type = body.get("type")
    if event_type not in _WEBHOOK_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="unknown webhook event type")

    call_data = body.get("data")
    if not isinstance(call_data, dict) or not isinstance(call_data.get("id"), str):
        raise HTTPException(status_code=400, detail="webhook data.id missing")

    use_case = HandleCalleWebhookUseCase(
        call_repository=SqlAlchemyCallRepository(session),
        availability_result_repository=SqlAlchemyAvailabilityResultRepository(session),
        webhook_event_repository=SqlAlchemyWebhookEventRepository(session),
        sweep_repository=SqlAlchemySweepRepository(session),
        facility_repository=SqlAlchemyFacilityRepository(session),
        commodity_repository=SqlAlchemyCommodityRepository(session),
        stockout_alert_repository=SqlAlchemyStockoutAlertRepository(session),
        subscriber_repository=SqlAlchemySubscriberRepository(session),
        notifier_resolver=partial(build_notifier, settings=settings),
        realtime_event_bus=realtime_event_bus,
        settings=settings,
    )
    await use_case.handle(
        event_id=body["id"],
        event_type=event_type,
        call_data=call_data,
    )

    return {"ok": True}
