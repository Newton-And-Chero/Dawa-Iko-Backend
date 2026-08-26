"""GET /openapi.json renders without error and documents every router."""

from httpx import AsyncClient

_EXPECTED_PATHS = {
    "/v1/auth/login",
    "/v1/auth/me",
    "/v1/users",
    "/v1/users/{user_id}",
    "/v1/facilities",
    "/v1/facilities/{facility_id}",
    "/v1/facilities/{facility_id}/verify-phone",
    "/v1/commodities",
    "/v1/commodities/{commodity_id}",
    "/v1/sweeps/query",
    "/v1/sweeps/{sweep_id}",
    "/v1/sweeps/{sweep_id}/stream",
    "/v1/sweeps",
    "/v1/sweeps/scheduled",
    "/v1/calls",
    "/v1/calls/{call_id}",
    "/v1/calls/{call_id}/retry",
    "/v1/availability-results",
}


async def test_openapi_json_includes_every_router(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = set(response.json()["paths"].keys())
    assert paths >= _EXPECTED_PATHS


async def test_docs_ui_renders(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
