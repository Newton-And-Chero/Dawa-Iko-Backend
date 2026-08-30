import httpx

from app.core.config import Settings
from app.domain.enums import NotificationChannel
from app.infrastructure.notifications.twilio_sms_adapter import TwilioSmsAdapter

_RECIPIENT = "+254711000111"


def _settings(**overrides) -> Settings:
    base = {
        "TWILIO_ACCOUNT_SID": "AC123",
        "TWILIO_AUTH_TOKEN": "test-token",
        "TWILIO_FROM_NUMBER": "+15005550006",
    }
    base.update(overrides)
    return Settings(**base)


def _adapter(handler, **settings_overrides) -> TwilioSmsAdapter:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return TwilioSmsAdapter(_settings(**settings_overrides), http_client=client)


async def _send(adapter: TwilioSmsAdapter):
    return await adapter.send(
        channel=NotificationChannel.SMS,
        recipient=_RECIPIENT,
        message="stockout alert",
    )


def _ok_body(status: str = "queued") -> dict:
    return {"sid": "SM123", "status": status, "error_code": None, "error_message": None}


async def test_accepted_message_is_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.twilio.com"
        assert "/Accounts/AC123/Messages.json" in request.url.path
        assert request.headers["Authorization"].startswith("Basic ")
        assert b"To=%2B254711000111" in request.content
        assert b"From=%2B15005550006" in request.content
        return httpx.Response(201, json=_ok_body())

    result = await _send(_adapter(handler))

    assert result.success is True
    assert result.error is None


async def test_api_error_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": 21211, "message": "The 'To' number is not valid"})

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "not valid" in result.error
    assert "21211" in result.error


async def test_failed_status_is_failure_despite_201():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"sid": "SM1", "status": "failed", "error_code": 30006})

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "failed" in result.error


async def test_non_json_body_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, text="<html>gateway error</html>")

    result = await _send(_adapter(handler))

    assert result.success is False
    assert "unparseable" in result.error


async def test_transport_error_is_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    result = await _send(_adapter(handler))

    assert result.success is False
    assert result.error is not None


async def test_messaging_service_sid_takes_precedence_over_from_number():
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"MessagingServiceSid=MG999" in request.content
        assert b"From=" not in request.content
        return httpx.Response(201, json=_ok_body())

    result = await _send(_adapter(handler, TWILIO_MESSAGING_SERVICE_SID="MG999"))

    assert result.success is True


async def test_demo_redirect_fans_out_to_every_demo_number_and_skips_recipient():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        to = dict(pair.split("=", 1) for pair in body.split("&"))["To"]
        seen.append(to)
        assert "for+%2B254711000111" in body
        return httpx.Response(201, json=_ok_body())

    adapter = _adapter(
        handler,
        SMS_DEMO_REDIRECT_NUMBERS=["+254792036343", "+254793586004", "+254720168641"],
    )
    result = await _send(adapter)

    assert result.success is True
    assert sorted(seen) == sorted(["%2B254792036343", "%2B254793586004", "%2B254720168641"])


async def test_demo_redirect_reports_failure_if_any_number_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        to = dict(pair.split("=", 1) for pair in request.content.decode().split("&"))["To"]
        if to == "%2B254793586004":
            return httpx.Response(400, json={"code": 21608, "message": "unverified"})
        return httpx.Response(201, json=_ok_body())

    adapter = _adapter(
        handler,
        SMS_DEMO_REDIRECT_NUMBERS=["+254792036343", "+254793586004"],
    )
    result = await _send(adapter)

    assert result.success is False
    assert "unverified" in result.error
    assert result.recipient == _RECIPIENT
