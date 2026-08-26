"""Settings-driven NotifierPort selection per channel — same pattern as
`call_e/factory.py` and `facility_import/factory.py`. `MockSMSAdapter` is
stateful (records `.sent` for test assertions) so, like `MockCallEAdapter`,
it's a shared instance per process rather than fresh per call."""

from app.application.ports.notifier_port import NotifierPort
from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.infrastructure.notifications.africas_talking_adapter import AfricasTalkingAdapter
from app.infrastructure.notifications.email_notifier import EmailNotifier
from app.infrastructure.notifications.mock_sms_adapter import MockSMSAdapter
from app.infrastructure.notifications.webhook_notifier import WebhookNotifier

_shared_mock_sms_adapter: MockSMSAdapter | None = None
_shared_webhook_notifier: WebhookNotifier | None = None


def _build_sms_notifier(settings: Settings) -> NotifierPort:
    if settings.SMS_MODE == "mock":
        global _shared_mock_sms_adapter
        if _shared_mock_sms_adapter is None:
            _shared_mock_sms_adapter = MockSMSAdapter()
        return _shared_mock_sms_adapter
    return AfricasTalkingAdapter(settings)


def _build_webhook_notifier() -> NotifierPort:
    global _shared_webhook_notifier
    if _shared_webhook_notifier is None:
        _shared_webhook_notifier = WebhookNotifier()
    return _shared_webhook_notifier


def build_notifier(channel: NotificationChannel, settings: Settings) -> NotifierPort:
    if channel == NotificationChannel.SMS:
        return _build_sms_notifier(settings)
    if channel == NotificationChannel.EMAIL:
        return EmailNotifier(settings)
    return _build_webhook_notifier()
