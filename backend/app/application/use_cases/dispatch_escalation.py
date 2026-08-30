import logging
from collections.abc import Callable

from app.application.ports.notifier_port import NotifierPort
from app.application.ports.subscriber_repository import SubscriberRepositoryPort
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber
from app.domain.enums import NotificationChannel
from app.domain.services.subscriber_matching import match_subscribers

logger = logging.getLogger(__name__)

NotifierResolver = Callable[[NotificationChannel], NotifierPort]


def _recipient_for(subscriber: Subscriber) -> str | None:
    if subscriber.notification_channel == NotificationChannel.SMS:
        return subscriber.phone
    if subscriber.notification_channel == NotificationChannel.EMAIL:
        return subscriber.email
    return subscriber.webhook_url


def _message_for(alert: StockoutAlert) -> str:
    pct_in_stock = (
        0
        if alert.facilities_checked_count == 0
        else round(100 * alert.facilities_with_stock_count / alert.facilities_checked_count)
    )
    return (
        f"CALL-E stockout alert ({alert.severity.value}): "
        f"{alert.facilities_with_stock_count}/{alert.facilities_checked_count} "
        f"facilities checked have stock ({pct_in_stock}%)."
    )


class DispatchEscalationUseCase:
    def __init__(
        self,
        subscriber_repository: SubscriberRepositoryPort,
        notifier_resolver: NotifierResolver,
    ) -> None:
        self._subscribers = subscriber_repository
        self._resolve_notifier = notifier_resolver

    async def execute(self, alert: StockoutAlert) -> None:
        subscribers = await self._subscribers.list_all()
        matched = match_subscribers(alert, subscribers)
        message = _message_for(alert)

        for subscriber in matched:
            recipient = _recipient_for(subscriber)
            if not recipient:
                logger.warning(
                    "subscriber %s has no %s recipient configured, skipping alert %s",
                    subscriber.id,
                    subscriber.notification_channel.value,
                    alert.id,
                )
                continue
            try:
                notifier = self._resolve_notifier(subscriber.notification_channel)
                await notifier.send(
                    channel=subscriber.notification_channel,
                    recipient=recipient,
                    message=message,
                    metadata={"alert_id": str(alert.id), "commodity_id": str(alert.commodity_id)},
                )
            except Exception:
                logger.exception(
                    "failed to notify subscriber %s for alert %s", subscriber.id, alert.id
                )
