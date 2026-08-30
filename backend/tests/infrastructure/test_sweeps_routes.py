from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.user import User
from app.domain.enums import CommodityCategory, FacilitySource, FacilityType, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_commodity_and_facility(db_session: AsyncSession) -> Commodity:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            aliases=["PPH drug"],
        )
    )
    await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Sweep Route Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000097",
            source=FacilitySource.KMHFL,
        )
    )
    return commodity


async def test_query_by_commodity_alias_returns_202_and_dispatches_calls(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_commodity_and_facility(db_session)

    response = await client.post(
        "/v1/sweeps/query",
        json={"commodity": "PPH drug", "geography": {"kind": "county", "county": "Kirinyaga"}},
    )

    assert response.status_code == 202
    sweep_id = response.json()["sweep_id"]

    sweep_repo = SqlAlchemySweepRepository(db_session)
    sweep = await sweep_repo.get_by_id(sweep_id)
    assert sweep is not None


async def test_query_unknown_commodity_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/sweeps/query",
        json={
            "commodity": "no-such-commodity-xyz",
            "geography": {"kind": "county", "county": "Kirinyaga"},
        },
    )
    assert response.status_code == 404


async def test_get_sweep_status_is_public_and_unknown_sweep_404s(client: AsyncClient) -> None:
    response = await client.get("/v1/sweeps/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_get_sweep_status_after_query(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_commodity_and_facility(db_session)
    query_response = await client.post(
        "/v1/sweeps/query",
        json={"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}},
    )
    sweep_id = query_response.json()["sweep_id"]

    status_response = await client.get(f"/v1/sweeps/{sweep_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["sweep_id"] == sweep_id
    assert body["total_calls"] >= 1


async def test_list_sweeps_denied_for_viewer(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get("/v1/sweeps", headers=_auth(token))
    assert response.status_code == 403


async def test_list_sweeps_allowed_for_analyst(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)
    response = await client.get("/v1/sweeps", headers=_auth(token))
    assert response.status_code == 200
    assert "items" in response.json()


async def test_scheduled_sweep_denied_for_viewer(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.post(
        "/v1/sweeps/scheduled",
        headers=_auth(token),
        json={"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}},
    )
    assert response.status_code == 403


async def test_scheduled_sweep_allowed_for_analyst(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    await _seed_commodity_and_facility(db_session)
    _, token = await make_user_token(UserRole.ANALYST)

    response = await client.post(
        "/v1/sweeps/scheduled",
        headers=_auth(token),
        json={"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}},
    )
    assert response.status_code == 202
