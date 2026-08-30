from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.user import User
from app.domain.enums import CommodityCategory, FacilitySource, FacilityType, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository

TokenFactory = Callable[[UserRole], Awaitable[tuple[User, str]]]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_get_call_engine_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/v1/call-engine")
    assert response.status_code == 401


async def test_viewer_can_read_state_but_not_toggle(
    client: AsyncClient, make_user_token: TokenFactory
) -> None:
    _, viewer_token = await make_user_token(UserRole.VIEWER)

    read = await client.get("/v1/call-engine", headers=_auth(viewer_token))
    assert read.status_code == 200
    assert set(read.json()) == {"enabled", "expires_at", "default_enabled"}

    denied = await client.post("/v1/call-engine/enable", headers=_auth(viewer_token))
    assert denied.status_code == 403


async def test_analyst_can_disable_and_enable_the_engine(
    client: AsyncClient, make_user_token: TokenFactory
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)

    disabled = await client.post("/v1/call-engine/disable", headers=_auth(token))
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["expires_at"] is None

    read = await client.get("/v1/call-engine", headers=_auth(token))
    assert read.json()["enabled"] is False

    enabled = await client.post(
        "/v1/call-engine/enable", json={"ttl_seconds": 900}, headers=_auth(token)
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert enabled.json()["expires_at"] is not None


async def test_enable_rejects_an_out_of_range_ttl(
    client: AsyncClient, make_user_token: TokenFactory
) -> None:
    _, token = await make_user_token(UserRole.ADMIN)

    response = await client.post(
        "/v1/call-engine/enable", json={"ttl_seconds": 0}, headers=_auth(token)
    )
    assert response.status_code == 422


async def test_query_while_disabled_completes_the_sweep_with_no_calls(
    client: AsyncClient, db_session: AsyncSession, make_user_token: TokenFactory
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)
    await client.post("/v1/call-engine/disable", headers=_auth(token))

    await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Gated Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000042",
            source=FacilitySource.KMHFL,
        )
    )

    response = await client.post(
        "/v1/sweeps/query",
        json={"commodity": "carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}},
    )
    assert response.status_code == 202
    sweep_id = response.json()["sweep_id"]

    status = await client.get(f"/v1/sweeps/{sweep_id}")
    assert status.json()["status"] == "completed"
    assert status.json()["total_calls"] == 0
    assert status.json()["matches"] == []
