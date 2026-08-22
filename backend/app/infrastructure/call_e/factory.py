"""Settings-driven selection of a CallProviderPort implementation.

Same pattern as FACILITY_IMPORT_MODE (see
infrastructure/facility_import/factory.py): use-case-layer code only ever
depends on CallProviderPort and never knows whether it's talking to the mock
or the real adapter.

MockCallEAdapter is stateful (it remembers calls it placed, for `get_call`/
`list_call_events`/`wait_for_webhook`), so — unlike the stateless facility
import mock — this factory hands back one shared instance per process rather
than a fresh one per call.
"""

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
