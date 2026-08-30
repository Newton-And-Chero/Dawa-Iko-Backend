from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.commodity import Commodity
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.user import User
from app.domain.enums import CommodityCategory, EscalationSeverity, UserRole
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.stockout_alert_repository import (
    SqlAlchemyStockoutAlertRepository,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_alert(db_session: AsyncSession) -> StockoutAlert:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    return await SqlAlchemyStockoutAlertRepository(db_session).add(
        StockoutAlert(
            commodity_id=commodity.id,
            geography={"kind": "county", "county": "Kirinyaga"},
            severity=EscalationSeverity.HIGH,
            facilities_checked_count=10,
            facilities_with_stock_count=0,
        )
    )


async def test_list_escalations_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/escalations")
    assert response.status_code == 401


async def test_viewer_can_list_escalations(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    alert = await _seed_alert(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get("/v1/escalations", headers=_auth(token), params={"status": "open"})
    assert response.status_code == 200
    assert any(a["id"] == str(alert.id) for a in response.json()["items"])


async def test_viewer_cannot_acknowledge(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    alert = await _seed_alert(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.post(
        f"/v1/escalations/{alert.id}/acknowledge", headers=_auth(token), json={}
    )
    assert response.status_code == 403


async def test_analyst_can_acknowledge_then_resolve(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    alert = await _seed_alert(db_session)
    _, token = await make_user_token(UserRole.ANALYST)

    ack_response = await client.post(
        f"/v1/escalations/{alert.id}/acknowledge",
        headers=_auth(token),
        json={"note": "redistributing stock from Sagana"},
    )
    assert ack_response.status_code == 200
    assert ack_response.json()["status"] == "acknowledged"
    assert ack_response.json()["acknowledgment_note"] == "redistributing stock from Sagana"

    resolve_response = await client.post(
        f"/v1/escalations/{alert.id}/resolve", headers=_auth(token), json={}
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"


async def test_acknowledge_unknown_escalation_returns_404(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ADMIN)
    response = await client.post(
        "/v1/escalations/00000000-0000-0000-0000-000000000000/acknowledge",
        headers=_auth(token),
        json={},
    )
    assert response.status_code == 404
