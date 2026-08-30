from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.dispatch_escalation import DispatchEscalationUseCase
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber
from app.domain.enums import EscalationSeverity, NotificationChannel
from app.infrastructure.notifications.mock_sms_adapter import MockSMSAdapter
from app.infrastructure.notifications.webhook_notifier import WebhookNotifier
from tests.application.fakes import InMemorySubscriberRepository


def _alert(commodity_id) -> StockoutAlert:
    return StockoutAlert(
        commodity_id=commodity_id,
        geography={"kind": "county", "county": "Kirinyaga"},
        severity=EscalationSeverity.HIGH,
        facilities_checked_count=5,
        facilities_with_stock_count=0,
    )


def _build_webhook_capture_app() -> tuple[FastAPI, list[dict[str, Any]]]:
    received: list[dict[str, Any]] = []
    app = FastAPI()

    @app.post("/hooks/{path:path}")
    async def _receive(path: str, request: Request) -> dict[str, bool]:
        if path == "dead":
            raise HTTPException(status_code=500, detail="simulated dead subscriber endpoint")
        received.append(await request.json())
        return {"ok": True}

    return app, received


async def test_matched_subscribers_are_notified_on_their_own_channel() -> None:
    commodity_id = uuid4()
    alert = _alert(commodity_id)
    geography = alert.geography

    subscribers = InMemorySubscriberRepository()
    sms_subscriber = await subscribers.add(
        Subscriber(
            name="County Pharmacist",
            notification_channel=NotificationChannel.SMS,
            phone="+254700000010",
            watchlist_commodities=[commodity_id],
            watchlist_geography=geography,
        )
    )

    webhook_app, received = _build_webhook_capture_app()
    async with AsyncClient(
        transport=ASGITransport(app=webhook_app), base_url="http://ngo.example"
    ) as http_client:
        webhook_subscriber = await subscribers.add(
            Subscriber(
                name="NGO Partner",
                notification_channel=NotificationChannel.WEBHOOK,
                webhook_url="http://ngo.example/hooks/ok",
                watchlist_commodities=[commodity_id],
                watchlist_geography=geography,
            )
        )
        mock_sms = MockSMSAdapter()
        webhook_notifier = WebhookNotifier(http_client=http_client)

        def resolve_notifier(channel: NotificationChannel):
            return mock_sms if channel == NotificationChannel.SMS else webhook_notifier

        use_case = DispatchEscalationUseCase(
            subscriber_repository=subscribers, notifier_resolver=resolve_notifier
        )
        await use_case.execute(alert)

    assert len(mock_sms.sent) == 1
    assert mock_sms.sent[0]["recipient"] == sms_subscriber.phone

    assert len(received) == 1
    assert received[0]["metadata"]["alert_id"] == str(alert.id)
    assert webhook_subscriber.webhook_url == "http://ngo.example/hooks/ok"


async def test_one_subscribers_dead_webhook_does_not_block_the_others_sms() -> None:
    commodity_id = uuid4()
    alert = _alert(commodity_id)
    geography = alert.geography

    subscribers = InMemorySubscriberRepository()
    await subscribers.add(
        Subscriber(
            name="Dead Webhook NGO",
            notification_channel=NotificationChannel.WEBHOOK,
            webhook_url="http://ngo.example/hooks/dead",
            watchlist_commodities=[commodity_id],
            watchlist_geography=geography,
        )
    )
    sms_subscriber = await subscribers.add(
        Subscriber(
            name="County Pharmacist",
            notification_channel=NotificationChannel.SMS,
            phone="+254700000011",
            watchlist_commodities=[commodity_id],
            watchlist_geography=geography,
        )
    )

    webhook_app, _ = _build_webhook_capture_app()
    async with AsyncClient(
        transport=ASGITransport(app=webhook_app), base_url="http://ngo.example"
    ) as http_client:
        mock_sms = MockSMSAdapter()
        webhook_notifier = WebhookNotifier(http_client=http_client)

        def resolve_notifier(channel: NotificationChannel):
            return mock_sms if channel == NotificationChannel.SMS else webhook_notifier

        use_case = DispatchEscalationUseCase(
            subscriber_repository=subscribers, notifier_resolver=resolve_notifier
        )
        await use_case.execute(alert)

    assert len(mock_sms.sent) == 1
    assert mock_sms.sent[0]["recipient"] == sms_subscriber.phone
