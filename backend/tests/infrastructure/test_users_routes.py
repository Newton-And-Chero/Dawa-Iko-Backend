from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.domain.entities.user import User
from app.domain.enums import UserRole


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_list_users_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/users")
    assert response.status_code == 401


async def test_list_users_denied_for_non_admin(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)
    response = await client.get("/v1/users", headers=_auth(token))
    assert response.status_code == 403


async def test_admin_can_create_and_list_and_edit_users(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, admin_token = await make_user_token(UserRole.ADMIN)

    create_response = await client.post(
        "/v1/users",
        headers=_auth(admin_token),
        json={
            "name": "New Analyst",
            "role": "analyst",
            "phone_number": "+254700111222",
            "password": "s3cret-password",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["role"] == "analyst"
    assert "password" not in created
    assert "password_hash" not in created

    list_response = await client.get("/v1/users", headers=_auth(admin_token))
    assert list_response.status_code == 200
    page = list_response.json()
    assert page["total"] >= 1
    assert any(u["id"] == created["id"] for u in page["items"])

    get_response = await client.get(f"/v1/users/{created['id']}", headers=_auth(admin_token))
    assert get_response.status_code == 200

    edit_response = await client.patch(
        f"/v1/users/{created['id']}", headers=_auth(admin_token), json={"role": "viewer"}
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["role"] == "viewer"


async def test_get_unknown_user_returns_404(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, admin_token = await make_user_token(UserRole.ADMIN)
    response = await client.get(
        "/v1/users/00000000-0000-0000-0000-000000000000", headers=_auth(admin_token)
    )
    assert response.status_code == 404
