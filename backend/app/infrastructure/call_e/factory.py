import httpx

from app.application.ports.call_provider_port import CallProviderPort
from app.core.config import Settings
from app.infrastructure.call_e.calle_adapter import CallEAdapter
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter

_shared_mock_adapter: MockCallEAdapter | None = None


def build_call_provider(settings: Settings) -> CallProviderPort:
    if settings.CALL_E_MODE == "mock":
        global _shared_mock_adapter
        if _shared_mock_adapter is None:
            _shared_mock_adapter = MockCallEAdapter(http_client=httpx.AsyncClient())
        return _shared_mock_adapter
    return CallEAdapter(base_url=settings.CALLE_BASE_URL, api_key=settings.CALLE_API_KEY)
