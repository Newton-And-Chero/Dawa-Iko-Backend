import secrets

from app.core.config import get_settings

_generated_token: str | None = None


def get_webhook_token() -> str:
    settings = get_settings()
    if settings.CALLE_WEBHOOK_TOKEN:
        return settings.CALLE_WEBHOOK_TOKEN

    global _generated_token
    if _generated_token is None:
        _generated_token = secrets.token_urlsafe(32)
    return _generated_token


def build_webhook_url() -> str:
    settings = get_settings()
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/webhooks/calle/{get_webhook_token()}"


def is_valid_webhook_token(token: str) -> bool:
    return secrets.compare_digest(token, get_webhook_token())
