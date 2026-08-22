"""Per-deployment webhook token: gates our CALL-E webhook receiver.

CALL-E signs nothing (no HMAC, no `CALL-E-Signature` header — see RULES.md),
so the unguessable path segment embedded in `webhook_url` is the only thing
standing between the receiver and the open internet.
"""

import secrets

from app.core.config import get_settings

_generated_token: str | None = None


def get_webhook_token() -> str:
    """The token gating the webhook path.

    Read from `Settings.CALLE_WEBHOOK_TOKEN` when set; otherwise generated
    once per process, so a bare local run still has a working, unguessable
    webhook path without requiring `.env` setup first.
    """
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
