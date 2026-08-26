"""POST /v1/auth/login, GET /v1/auth/me."""

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from app.domain.entities.user import User
from app.domain.enums import UserRole


async def test_login_with_correct_password_returns_token(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    user, _ = await make_user_token(UserRole.ANALYST)

    response = await client.post(
        "/v1/auth/login",
        json={"phone_number": user.phone_number, "password": "testpass123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_with_wrong_password_returns_401(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    user, _ = await make_user_token(UserRole.ANALYST)

    response = await client.post(
        "/v1/auth/login",
        json={"phone_number": user.phone_number, "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_login_with_unknown_phone_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/auth/login", json={"phone_number": "+254700999999", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_me_without_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_token_returns_current_user(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    user, token = await make_user_token(UserRole.VIEWER)

    response = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["role"] == "viewer"
    assert "password_hash" not in body
