"""POST /webhooks/calle/{webhook_token} — every rejection path, plus the
happy path and its replay-is-a-no-op behavior, through the real ASGI app."""

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
    StockStatus,
    SweepTrigger,
)
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _webhook_path() -> str:
    return f"/webhooks/calle/{get_webhook_token()}"


def _body(event_id: str, call_id: str, recipient_id: str) -> dict:
    return {
        "id": event_id,
        "type": "call.completed",
        "created_at": "2026-08-20T12:00:00+00:00",
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
            name="Route Test Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000050",
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
            provider_recipient_id="recip_route",
        )
    )


async def test_wrong_token_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/webhooks/calle/not-the-real-token",
        json=_body("evt_x", "call_x", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_x"},
    )
    assert response.status_code == 404


async def test_missing_event_id_header_returns_400(client: AsyncClient) -> None:
    response = await client.post(_webhook_path(), json=_body("evt_x", "call_x", "recip_x"))
    assert response.status_code == 400


async def test_mismatched_event_id_header_returns_400(client: AsyncClient) -> None:
    response = await client.post(
        _webhook_path(),
        json=_body("evt_x", "call_x", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_different"},
    )
    assert response.status_code == 400


async def test_unknown_call_id_returns_409(client: AsyncClient) -> None:
    response = await client.post(
        _webhook_path(),
        json=_body("evt_unknown_call", "call_never_dispatched", "recip_x"),
        headers={"CALL-E-Event-Id": "evt_unknown_call"},
    )
    assert response.status_code == 409


async def test_happy_path_then_replay_is_a_noop(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    call = await _seed_pending_call(db_session, provider_call_id="call_route_ok")
    body = _body("evt_route_ok", "call_route_ok", "recip_route")

    first = await client.post(
        _webhook_path(), json=body, headers={"CALL-E-Event-Id": "evt_route_ok"}
    )
    assert first.status_code == 200
    assert first.json() == {"ok": True}

    results_repo = SqlAlchemyAvailabilityResultRepository(db_session)
    result = await results_repo.get_by_call_id(call.id)
    assert result is not None
    assert result.in_stock == StockStatus.YES

    replay = await client.post(
        _webhook_path(), json=body, headers={"CALL-E-Event-Id": "evt_route_ok"}
    )
    assert replay.status_code == 200

    all_results = [r for r in await results_repo.list_all() if r.call_id == call.id]
    assert len(all_results) == 1
