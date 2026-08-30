import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from httpx_ws import AsyncWebSocketSession, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_call_provider
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.user import User
from app.domain.enums import CommodityCategory, FacilitySource, FacilityType, UserRole
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.main import app


@pytest_asyncio.fixture
async def ws_client() -> AsyncGenerator[AsyncClient, None]:
    ac = AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")
    await ac.__aenter__()
    try:
        yield ac
    finally:
        with contextlib.suppress(RuntimeError):
            await ac.__aexit__(None, None, None)


async def _seed_commodity_and_facilities(db_session: AsyncSession) -> Commodity:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility_repo = SqlAlchemyFacilityRepository(db_session)
    for i in range(2):
        await facility_repo.add(
            Facility(
                name=f"Full Flow Dispensary {i}",
                type=FacilityType.DISPENSARY,
                county="Kirinyaga",
                sub_county="Mwea",
                ward="Wamumu",
                gps_lat=-0.6849,
                gps_lng=37.3667,
                phone_number=f"+254700000{80 + i}",
                source=FacilitySource.KMHFL,
            )
        )
    return commodity


async def test_query_to_analytics_end_to_end(
    client: AsyncClient,
    ws_client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    commodity = await _seed_commodity_and_facilities(db_session)

    webhook_http_client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    adapter = MockCallEAdapter(http_client=webhook_http_client, webhook_delay_seconds=0.3, seed=11)
    app.dependency_overrides[get_call_provider] = lambda: adapter

    try:
        query_response = await client.post(
            "/v1/sweeps/query",
            json={
                "commodity": str(commodity.id),
                "geography": {"kind": "county", "county": "Kirinyaga"},
            },
        )
        assert query_response.status_code == 202
        sweep_id = query_response.json()["sweep_id"]

        ws: AsyncWebSocketSession
        async with aconnect_ws(f"/ws/sweeps/{sweep_id}", ws_client) as ws:
            snapshot = await ws.receive_json()
            assert snapshot["type"] == "sweep.snapshot"
            assert snapshot["data"]["total_calls"] == 2

            events = [await ws.receive_json() for _ in range(5)]
            assert events[-1]["type"] == "sweep.completed"
            assert events[-1]["data"]["status"] == "completed"
            result_events = [e for e in events if e["type"] == "availability_result.created"]
            assert len(result_events) == 2
    finally:
        app.dependency_overrides.pop(get_call_provider, None)
        await webhook_http_client.aclose()

    status_response = await client.get(f"/v1/sweeps/{sweep_id}")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["status"] == "completed"
    assert status_body["total_calls"] == 2
    assert sum(status_body["counts_by_status"].values()) == 2

    _, viewer_token = await make_user_token(UserRole.VIEWER)
    analytics_response = await client.get(
        "/v1/analytics/stockout-rate",
        params={"commodity_id": str(commodity.id), "geography": "Kirinyaga"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert analytics_response.status_code == 200
    analytics_body = analytics_response.json()
    assert sum(bucket["sweep_count"] for bucket in analytics_body["buckets"]) >= 1
