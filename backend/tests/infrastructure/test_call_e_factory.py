from app.core.config import Settings
from app.infrastructure.call_e.calle_adapter import CallEAdapter
from app.infrastructure.call_e.factory import build_call_provider
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter


def test_mock_mode_returns_mock_adapter() -> None:
    provider = build_call_provider(Settings(CALL_E_MODE="mock"))
    assert isinstance(provider, MockCallEAdapter)


def test_mock_mode_returns_the_same_shared_instance() -> None:
    first = build_call_provider(Settings(CALL_E_MODE="mock"))
    second = build_call_provider(Settings(CALL_E_MODE="mock"))
    assert first is second


def test_live_mode_returns_real_adapter() -> None:
    provider = build_call_provider(
        Settings(CALL_E_MODE="live", CALLE_BASE_URL="https://api.heycall-e.com", CALLE_API_KEY="k")
    )
    assert isinstance(provider, CallEAdapter)
