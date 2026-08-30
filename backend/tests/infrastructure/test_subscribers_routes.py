from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.domain.entities.user import User
from app.domain.enums import UserRole


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_subscribers_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/subscribers")
    assert response.status_code == 401


async def test_analyst_cannot_create_subscriber(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)
    response = await client.post(
        "/v1/subscribers",
        headers=_auth(token),
        json={"name": "County Pharmacist", "notification_channel": "sms", "phone": "+254700000020"},
    )
    assert response.status_code == 403


async def test_admin_can_create_edit_and_list_subscriber(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ADMIN)

    create_response = await client.post(
        "/v1/subscribers",
        headers=_auth(token),
        json={
            "name": "NGO Partner",
            "notification_channel": "webhook",
            "webhook_url": "https://ngo.example/hooks/calle",
            "watchlist_geography": {"kind": "county", "county": "Kirinyaga"},
        },
    )
    assert create_response.status_code == 201
    subscriber_id = create_response.json()["id"]

    edit_response = await client.patch(
        f"/v1/subscribers/{subscriber_id}",
        headers=_auth(token),
        json={"webhook_url": "https://ngo.example/hooks/v2"},
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["webhook_url"] == "https://ngo.example/hooks/v2"

    get_response = await client.get(f"/v1/subscribers/{subscriber_id}", headers=_auth(token))
    assert get_response.status_code == 200

    list_response = await client.get("/v1/subscribers", headers=_auth(token))
    assert list_response.status_code == 200
    assert any(s["id"] == subscriber_id for s in list_response.json()["items"])


async def test_get_unknown_subscriber_returns_404(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get(
        "/v1/subscribers/00000000-0000-0000-0000-000000000000", headers=_auth(token)
    )
    assert response.status_code == 404
