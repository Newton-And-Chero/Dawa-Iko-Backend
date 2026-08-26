"""Redis pub/sub channel naming (Sprint 06). Every publisher and every
WS/SSE subscriber builds channel names through these so the string format
only lives in one place.
"""

from uuid import UUID

# Reserved for Sprint 07's escalation/alert events — not published to yet.
ALERTS_CHANNEL = "alerts"


def sweep_channel(sweep_id: UUID) -> str:
    return f"sweep:{sweep_id}"


def geography_channel(county: str, commodity_id: UUID) -> str:
    return f"geo:{county}:{commodity_id}"
