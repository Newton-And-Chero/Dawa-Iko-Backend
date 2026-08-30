from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.webhook_security import get_webhook_token
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepTrigger,
)
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _webhook_path(token: str | None = None) -> str:
    return f"/webhooks/calle/{token if token is not None else get_webhook_token()}"


def _body(event_id: str, call_id: str, recipient_id: str) -> dict[str, Any]:
    return {
        "id": event_id,
        "type": "call.completed",
        "created_at": "2026-08-26T12:00:00+00:00",
        "data": {
            "id": call_id,
            "completion_confidence": {"score": 0.8, "label": "high"},
            "recipients": [
                {
                    "id": recipient_id,
                    "status": "completed",
                    "summary": "In stock.",
                    "structured_result": {
                        "in_stock": "yes",
                        "quantity_band": "low",
                        "price_kes": 90,
                        "last_restock_date": None,
                        "can_hold": False,
                        "hold_duration_hours": None,
                        "notes": None,
                    },
                    "attempts": [{"failure_code": None}],
                }
            ],
        },
    }


async def _seed_pending_call(db_session: AsyncSession, *, provider_call_id: str) -> Call:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility = await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Forgery Test Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000060",
            source=FacilitySource.KMHFL,
        )
    )
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    return await SqlAlchemyCallRepository(db_session).add(
        Call(
            sweep_id=sweep.id,
            facility_id=facility.id,
            status=CallStatus.QUEUED,
            provider_call_id=provider_call_id,
            provider_recipient_id="recip_forgery",
        )
    )


async def test_wrong_webhook_token_path_segment_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        _webhook_path("not-the-real-token"),
        json=_body("evt_forge_token", "call_forge_token", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_forge_token"},
    )
    assert response.status_code == 404


async def test_event_id_header_not_matching_body_id_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        _webhook_path(),
        json=_body("evt_forge_body", "call_forge_body", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_forge_header_mismatch"},
    )
    assert response.status_code == 400


async def test_missing_event_id_header_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        _webhook_path(), json=_body("evt_forge_missing", "call_forge_missing", "recip_x")
    )
    assert response.status_code == 400


async def test_call_id_never_dispatched_by_us_is_acknowledged_without_side_effects(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post(
        _webhook_path(),
        json=_body("evt_forge_spoofed", "call_never_dispatched_by_us", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_forge_spoofed"},
    )
    assert response.status_code == 200

    results = await SqlAlchemyAvailabilityResultRepository(db_session).list_all()
    assert results == []


async def test_replayed_already_processed_event_id_is_a_safe_noop(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    call = await _seed_pending_call(db_session, provider_call_id="call_forge_replay")
    body = _body("evt_forge_replay", "call_forge_replay", "recip_forgery")

    first = await client.post(
        _webhook_path(), json=body, headers={"CALL-E-Event-Id": "evt_forge_replay"}
    )
    assert first.status_code == 200

    results_repo = SqlAlchemyAvailabilityResultRepository(db_session)
    first_result = await results_repo.get_by_call_id(call.id)
    assert first_result is not None

    replay = await client.post(
        _webhook_path(), json=body, headers={"CALL-E-Event-Id": "evt_forge_replay"}
    )
    assert replay.status_code == 200

    all_results = [r for r in await results_repo.list_all() if r.call_id == call.id]
    assert len(all_results) == 1
