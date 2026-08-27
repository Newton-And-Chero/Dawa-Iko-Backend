"""AfricasTalkingAdapter response handling.

No real API is hit: a `httpx.MockTransport` stands in for Africa's Talking so
every wire shape — accepted, per-recipient rejection (HTTP still 201), empty
recipient list, transport error, non-JSON body — can be asserted.
"""

import httpx
import pytest

from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.infrastructure.notifications.africas_talking_adapter import AfricasTalkingAdapter

_RECIPIENT = "+254711000111"


def _settings(**overrides: str) -> Settings:
    base = {
        "AFRICAS_TALKING_USERNAME": "sandbox",
        "AFRICAS_TALKING_API_KEY": "test-key",
        "AFRICAS_TALKING_SENDER_ID": "41756",
    }
    base.update(overrides)
    return Settings(**base)


def _adapter(handler) -> AfricasTalkingAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return AfricasTalkingAdapter(_settings(), http_client=client)


async def _send(adapter: AfricasTalkingAdapter):
    return await adapter.send(
        channel=NotificationChannel.SMS,
        recipient=_RECIPIENT,
        message="stockout alert",
    )


def _at_body(status: str, status_code: int, *, number: str = _RECIPIENT) -> dict:
    return {
        "SMSMessageData": {
            "Message": "Sent to 1/1 Total Cost: KES 0.8000",
            "Recipients": [
                {
                    "statusCode": status_code,
                    "number": number,
                    "cost": "KES 0.8000",
                    "status": status,
                    "messageId": "ATPid_sample",
                }
            ],
        }
    }


async def test_accepted_recipient_is_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.sandbox.africastalking.com"
        assert b"from=41756" in request.content
        return httpx.Response(201, json=_at_body("Success", 101))

    result = await _send(_adapter(handler))

    assert result.success is True
    assert result.error is None


async def test_rejected_recipient_is_failure_despite_201():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=_at_body("UserInBlacklist", 406))

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "UserInBlacklist" in result.error
    assert "406" in result.error


async def test_empty_recipient_list_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"SMSMessageData": {"Message": "Sent to 0/1", "Recipients": []}},
        )

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "no recipients" in result.error


async def test_non_json_body_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, text="<html>gateway error</html>")

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "unparseable" in result.error


async def test_http_error_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "invalid credentials"})

    result = await _send(_adapter(handler))

    assert result.success is False
    assert result.error is not None


async def test_live_username_routes_to_production_host():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.africastalking.com"
        return httpx.Response(201, json=_at_body("Success", 101))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AfricasTalkingAdapter(
        _settings(AFRICAS_TALKING_USERNAME="calledocs"), http_client=client
    )

    result = await _send(adapter)

    assert result.success is True


async def test_blank_sender_id_omits_from_field():
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"from=" not in request.content
        return httpx.Response(201, json=_at_body("Success", 101))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = AfricasTalkingAdapter(
        _settings(AFRICAS_TALKING_SENDER_ID=""), http_client=client
    )

    result = await _send(adapter)

    assert result.success is True


@pytest.mark.parametrize("status_code", [100, 101, 102])
async def test_all_accepted_status_codes(status_code: int):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json=_at_body("Queued", status_code))

    result = await _send(_adapter(handler))

    assert result.success is True
