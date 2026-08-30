from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.commodity import Commodity
from app.domain.entities.user import User
from app.domain.enums import CommodityCategory, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_commodities_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/commodities")
    assert response.status_code == 401


async def test_viewer_can_list_and_get_commodity(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    _, token = await make_user_token(UserRole.VIEWER)

    list_response = await client.get(
        "/v1/commodities", headers=_auth(token), params={"search": "carbetocin"}
    )
    assert list_response.status_code == 200
    assert any(c["id"] == str(commodity.id) for c in list_response.json()["items"])

    get_response = await client.get(f"/v1/commodities/{commodity.id}", headers=_auth(token))
    assert get_response.status_code == 200


async def test_analyst_cannot_create_commodity(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)
    response = await client.post(
        "/v1/commodities",
        headers=_auth(token),
        json={"name": "Insulin", "category": "essential_medicine"},
    )
    assert response.status_code == 403


async def test_admin_can_create_edit_and_watchlist_commodity(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ADMIN)

    create_response = await client.post(
        "/v1/commodities",
        headers=_auth(token),
        json={"name": "Insulin", "category": "essential_medicine", "aliases": ["human insulin"]},
    )
    assert create_response.status_code == 201
    commodity_id = create_response.json()["id"]

    edit_response = await client.patch(
        f"/v1/commodities/{commodity_id}", headers=_auth(token), json={"keml_code": "KEML-9"}
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["keml_code"] == "KEML-9"

    watchlist_response = await client.patch(
        f"/v1/commodities/{commodity_id}/watchlist",
        headers=_auth(token),
        json={"is_priority_watchlist": True},
    )
    assert watchlist_response.status_code == 200
    assert watchlist_response.json()["is_priority_watchlist"] is True
