"""Settings-driven selection of a FacilityImportPort implementation.

Same pattern as CALL_E_MODE: the use-case layer only ever depends on
FacilityImportPort and never knows whether it's talking to the mock or the
real adapter.
"""

from pathlib import Path

from app.application.ports.facility_import_port import FacilityImportPort
from app.core.config import Settings
from app.infrastructure.facility_import.mock_kmhfl_adapter import MockKMHFLAdapter
from app.infrastructure.facility_import.real_kmhfl_adapter import RealKMHFLAdapter

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
SEED_DATA_DIR = _BACKEND_ROOT / "data" / "seed"

DEFAULT_SEED_FILES = [
    SEED_DATA_DIR / "facilities_kirinyaga.json",
    SEED_DATA_DIR / "facilities_nairobi.json",
    SEED_DATA_DIR / "chemists_manual.json",
]


def build_facility_import_port(settings: Settings) -> FacilityImportPort:
    if settings.FACILITY_IMPORT_MODE == "mock":
        return MockKMHFLAdapter(seed_paths=DEFAULT_SEED_FILES)
    return RealKMHFLAdapter(base_url=settings.KMHFL_BASE_URL, api_key=settings.KMHFL_API_KEY)
