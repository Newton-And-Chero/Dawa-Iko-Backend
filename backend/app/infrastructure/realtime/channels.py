from uuid import UUID

ALERTS_CHANNEL = "alerts"


def sweep_channel(sweep_id: UUID) -> str:
    return f"sweep:{sweep_id}"


def geography_channel(county: str, commodity_id: UUID) -> str:
    return f"geo:{county}:{commodity_id}"
