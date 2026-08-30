from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.entities.user import User
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepTrigger,
    UserRole,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_call(db_session: AsyncSession) -> Call:
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
            phone_number="+254700000098",
            source=FacilitySource.KMHFL,
        )
    )
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    return await SqlAlchemyCallRepository(db_session).add(
        Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
    )


async def test_list_calls_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/calls")
    assert response.status_code == 401


async def test_viewer_can_list_and_get_call(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    call = await _seed_call(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    list_response = await client.get("/v1/calls", headers=_auth(token))
    assert list_response.status_code == 200
    assert any(c["id"] == str(call.id) for c in list_response.json()["items"])

    get_response = await client.get(f"/v1/calls/{call.id}", headers=_auth(token))
    assert get_response.status_code == 200


async def test_viewer_cannot_retry_call(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    call = await _seed_call(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.post(f"/v1/calls/{call.id}/retry", headers=_auth(token))
    assert response.status_code == 403


async def test_analyst_can_retry_call(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    call = await _seed_call(db_session)
    _, token = await make_user_token(UserRole.ANALYST)

    response = await client.post(f"/v1/calls/{call.id}/retry", headers=_auth(token))
    assert response.status_code == 202
    assert "sweep_id" in response.json()
