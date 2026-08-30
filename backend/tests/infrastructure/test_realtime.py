import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator, Awaitable, Callable

import httpx_ws
import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.websocket.connection_manager import get_connection_manager
from app.core.webhook_security import get_webhook_token
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.entities.user import User
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepTrigger,
    UserRole,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.realtime.channels import sweep_channel
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


async def _seed_pending_call(
    db_session: AsyncSession, *, provider_call_id: str, county: str = "Kirinyaga"
) -> tuple[Call, Commodity, Facility]:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility = await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Realtime Test Dispensary",
            type=FacilityType.DISPENSARY,
            county=county,
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number=f"+2547{abs(hash(provider_call_id)) % 10**8:08d}",
            source=FacilitySource.KMHFL,
        )
    )
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": county},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    call = await SqlAlchemyCallRepository(db_session).add(
        Call(
            sweep_id=sweep.id,
            facility_id=facility.id,
            status=CallStatus.QUEUED,
            provider_call_id=provider_call_id,
            provider_recipient_id="recip_realtime",
        )
    )
    return call, commodity, facility


def _webhook_body(event_id: str, call_id: str, recipient_id: str) -> dict:
    return {
        "id": event_id,
        "type": "call.completed",
        "created_at": "2026-08-23T12:00:00+00:00",
        "data": {
            "id": call_id,
            "completion_confidence": {"score": 0.9, "label": "high"},
            "recipients": [
                {
                    "id": recipient_id,
                    "status": "completed",
                    "summary": "In stock.",
                    "structured_result": {
                        "in_stock": "yes",
                        "quantity_band": "medium",
                        "price_kes": 100,
                        "last_restock_date": None,
                        "can_hold": True,
                        "hold_duration_hours": 24,
                        "notes": None,
                    },
                    "attempts": [{"failure_code": None}],
                }
            ],
        },
    }


async def _trigger_webhook(client: AsyncClient, event_id: str, call: Call) -> None:
    response = await client.post(
        f"/webhooks/calle/{get_webhook_token()}",
        json=_webhook_body(event_id, call.provider_call_id, call.provider_recipient_id),
        headers={"CALL-E-Event-Id": event_id},
    )
    assert response.status_code == 200


async def test_sweep_ws_sends_snapshot_then_live_events_matching_rest_state(
    client: AsyncClient, ws_client: AsyncClient, db_session: AsyncSession
) -> None:
    call, _commodity, _facility = await _seed_pending_call(
        db_session, provider_call_id="call_ws_happy"
    )

    async with aconnect_ws(f"/ws/sweeps/{call.sweep_id}", ws_client) as ws:
        snapshot = await ws.receive_json()
        assert snapshot["v"] == 1
        assert snapshot["type"] == "sweep.snapshot"
        assert snapshot["sweep_id"] == str(call.sweep_id)
        assert snapshot["data"]["sweep_id"] == str(call.sweep_id)
        assert snapshot["data"]["total_calls"] == 1

        await _trigger_webhook(client, "evt_ws_happy", call)

        call_event = await ws.receive_json()
        assert call_event["type"] == "call.status_changed"
        assert call_event["v"] == 1
        assert call_event["sweep_id"] == str(call.sweep_id)
        assert call_event["data"]["call_id"] == str(call.id)
        assert call_event["data"]["status"] == "completed"

        result_event = await ws.receive_json()
        assert result_event["type"] == "availability_result.created"
        assert result_event["data"]["in_stock"] == "yes"
        assert result_event["data"]["price_kes"] == "100.00"

        completed_event = await ws.receive_json()
        assert completed_event["type"] == "sweep.completed"
        assert completed_event["data"]["status"] == "completed"

    rest_response = await client.get(f"/v1/sweeps/{call.sweep_id}")
    assert rest_response.json()["status"] == "completed"


async def test_sweep_ws_disconnect_leaves_no_leaked_subscription(
    client: AsyncClient, ws_client: AsyncClient, db_session: AsyncSession
) -> None:
    call, _commodity, _facility = await _seed_pending_call(
        db_session, provider_call_id="call_ws_disconnect"
    )
    manager = get_connection_manager()
    channel = sweep_channel(call.sweep_id)
    baseline = manager.subscriber_count(channel)

    async with aconnect_ws(f"/ws/sweeps/{call.sweep_id}", ws_client) as ws:
        await ws.receive_json()
        assert manager.subscriber_count(channel) == baseline + 1

    for _ in range(20):
        if manager.subscriber_count(channel) == baseline:
            break
        await asyncio.sleep(0.05)
    assert manager.subscriber_count(channel) == baseline

    rest_response = await client.get(f"/v1/sweeps/{call.sweep_id}")
    assert rest_response.status_code == 200


async def test_sweep_ws_unknown_sweep_closes_with_404_code(ws_client: AsyncClient) -> None:
    with pytest.raises(httpx_ws.HTTPXWSException):
        async with aconnect_ws("/ws/sweeps/00000000-0000-0000-0000-000000000000", ws_client) as ws:
            await ws.receive_json()


async def test_n_concurrent_ws_connections_each_receive_the_event_exactly_once(
    client: AsyncClient, ws_client: AsyncClient, db_session: AsyncSession
) -> None:
    call, _commodity, _facility = await _seed_pending_call(
        db_session, provider_call_id="call_ws_fanout"
    )
    path = f"/ws/sweeps/{call.sweep_id}"

    async with (
        aconnect_ws(path, ws_client) as ws_a,
        aconnect_ws(path, ws_client) as ws_b,
        aconnect_ws(path, ws_client) as ws_c,
    ):
        for ws in (ws_a, ws_b, ws_c):
            snapshot = await ws.receive_json()
            assert snapshot["type"] == "sweep.snapshot"

        await _trigger_webhook(client, "evt_ws_fanout", call)

        for ws in (ws_a, ws_b, ws_c):
            received_types = [(await ws.receive_json())["type"] for _ in range(3)]
            assert received_types == [
                "call.status_changed",
                "availability_result.created",
                "sweep.completed",
            ]
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.2):
                    await ws.receive_json()


async def test_geography_ws_rejects_missing_token(ws_client: AsyncClient) -> None:
    with pytest.raises(httpx_ws.HTTPXWSException):
        async with aconnect_ws(
            "/ws/live?county=Kirinyaga&commodity_id=00000000-0000-0000-0000-000000000000",
            ws_client,
        ) as ws:
            await ws.receive_json()


async def test_geography_ws_snapshot_then_live_event(
    client: AsyncClient,
    ws_client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    call, commodity, facility = await _seed_pending_call(
        db_session, provider_call_id="call_geo_ws", county="Kirinyaga"
    )
    _, token = await make_user_token(UserRole.VIEWER)
    url = f"/ws/live?county={facility.county}&commodity_id={commodity.id}&token={token}"

    async with aconnect_ws(url, ws_client) as ws:
        snapshot = await ws.receive_json()
        assert snapshot["type"] == "geography.snapshot"
        assert snapshot["sweep_id"] is None
        assert snapshot["data"]["county"] == "Kirinyaga"
        assert snapshot["data"]["commodity_id"] == str(commodity.id)
        assert snapshot["data"]["results"] == []

        await _trigger_webhook(client, "evt_geo_ws", call)

        event = await ws.receive_json()
        assert event["type"] == "call.status_changed"
        assert event["data"]["call_id"] == str(call.id)

        result_event = await ws.receive_json()
        assert result_event["type"] == "availability_result.created"
        assert result_event["data"]["commodity_id"] == str(commodity.id)


class _SSEStream:
    def __init__(self, path: str) -> None:
        self._path = path
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self.status_code: int | None = None
        self.headers: dict[str, str] = {}

    async def __aenter__(self) -> "_SSEStream":
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "headers": [],
            "scheme": "http",
            "path": self._path,
            "raw_path": self._path.encode(),
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 123),
            "root_path": "",
        }
        request_complete = False

        async def receive() -> dict:
            nonlocal request_complete
            if not request_complete:
                request_complete = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.Future()
            raise AssertionError("unreachable")

        async def send(message: dict) -> None:
            await self._queue.put(message)

        self._task = asyncio.create_task(app(scope, receive, send))
        start = await self._queue.get()
        assert start["type"] == "http.response.start"
        self.status_code = start["status"]
        self.headers = {k.decode(): v.decode() for k, v in start.get("headers", [])}
        return self

    async def next_chunk(self) -> str:
        message = await self._queue.get()
        assert message["type"] == "http.response.body"
        return message.get("body", b"").decode()

    async def __aexit__(self, *exc_info: object) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


async def test_sweep_sse_stream_delivers_snapshot_then_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    call, _commodity, _facility = await _seed_pending_call(
        db_session, provider_call_id="call_sse_happy"
    )

    async with _SSEStream(f"/v1/sweeps/{call.sweep_id}/stream") as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")

        first_frame = await asyncio.wait_for(stream.next_chunk(), timeout=5)
        assert first_frame.startswith("event: sweep.snapshot\n")
        snapshot = json.loads(
            next(
                line[len("data: ") :]
                for line in first_frame.splitlines()
                if line.startswith("data: ")
            )
        )
        assert snapshot["type"] == "sweep.snapshot"
        assert snapshot["sweep_id"] == str(call.sweep_id)

        await _trigger_webhook(client, "evt_sse_happy", call)

        second_frame = await asyncio.wait_for(stream.next_chunk(), timeout=5)
        assert second_frame.startswith("event: call.status_changed\n")
        event = json.loads(
            next(
                line[len("data: ") :]
                for line in second_frame.splitlines()
                if line.startswith("data: ")
            )
        )
        assert event["data"]["call_id"] == str(call.id)
