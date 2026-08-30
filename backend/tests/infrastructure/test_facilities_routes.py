from collections.abc import Awaitable, Callable

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.facility import Facility
from app.domain.entities.user import User
from app.domain.enums import FacilitySource, FacilityType, UserRole
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_facility(db_session: AsyncSession) -> Facility:
    return await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Route Test Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000099",
            source=FacilitySource.KMHFL,
        )
    )


async def test_list_facilities_denied_without_token(client: AsyncClient) -> None:
    response = await client.get("/v1/facilities")
    assert response.status_code == 401


async def test_list_facilities_denied_for_public_role(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.PUBLIC)
    response = await client.get("/v1/facilities", headers=_auth(token))
    assert response.status_code == 403


async def test_viewer_can_list_and_get_facility(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    facility = await _seed_facility(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    list_response = await client.get(
        "/v1/facilities", headers=_auth(token), params={"county": "Kirinyaga"}
    )
    assert list_response.status_code == 200
    page = list_response.json()
    assert any(f["id"] == str(facility.id) for f in page["items"])

    get_response = await client.get(f"/v1/facilities/{facility.id}", headers=_auth(token))
    assert get_response.status_code == 200
    assert get_response.json()["phone_number"] == "+254700000099"


async def test_viewer_cannot_create_facility(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.post(
        "/v1/facilities",
        headers=_auth(token),
        json={
            "name": "New Chemist",
            "type": "private_chemist",
            "county": "Nairobi",
            "sub_county": "Westlands",
            "ward": "Parklands",
            "gps_lat": -1.2634,
            "gps_lng": 36.8047,
            "phone_number": "+254711222333",
        },
    )
    assert response.status_code == 403


async def test_analyst_can_create_and_edit_and_verify_facility(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.ANALYST)

    create_response = await client.post(
        "/v1/facilities",
        headers=_auth(token),
        json={
            "name": "New Chemist",
            "type": "private_chemist",
            "county": "Nairobi",
            "sub_county": "Westlands",
            "ward": "Parklands",
            "gps_lat": -1.2634,
            "gps_lng": 36.8047,
            "phone_number": "+254711222333",
        },
    )
    assert create_response.status_code == 201
    facility_id = create_response.json()["id"]

    edit_response = await client.patch(
        f"/v1/facilities/{facility_id}", headers=_auth(token), json={"operational_status": False}
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["operational_status"] is False

    verify_response = await client.post(
        f"/v1/facilities/{facility_id}/verify-phone",
        headers=_auth(token),
        json={"status": "verified"},
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["phone_verification_status"] == "verified"


async def test_get_unknown_facility_returns_404(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get(
        "/v1/facilities/00000000-0000-0000-0000-000000000000", headers=_auth(token)
    )
    assert response.status_code == 404
