"""MockCallEAdapter round trip: place_call() with N recipients -> webhook fires
-> AvailabilityResult rows exist for all N facilities.

Uses a real `httpx.AsyncClient` bound to the running FastAPI app via ASGI
transport (no real sockets, no separate server process), so the actual
webhook route and `handle_calle_webhook` use case are exercised end-to-end,
not bypassed — per workflows/03's "not an in-process function call" rule.
"""

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.webhook_security import build_webhook_url
from app.domain.call_schemas import (
    CALLE_RECIPIENT_LOCALE,
    CALLE_RECIPIENT_REGION,
    STOCK_CHECK_RESULT_SCHEMA,
    build_stock_check_task,
)
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    SweepTrigger,
)
from app.domain.value_objects.call_task_ref import CallRecipient
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.main import app


def _facility(n: int) -> Facility:
    return Facility(
        name=f"Facility {n}",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number=f"+2547000000{n:02d}",
        source=FacilitySource.KMHFL,
    )


async def test_mock_calle_adapter_round_trip(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility_repo = SqlAlchemyFacilityRepository(db_session)
    facilities = [await facility_repo.add(_facility(i)) for i in range(3)]

    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )

    call_repo = SqlAlchemyCallRepository(db_session)
    calls = [
        await call_repo.add(Call(sweep_id=sweep.id, facility_id=f.id, status=CallStatus.QUEUED))
        for f in facilities
    ]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        adapter = MockCallEAdapter(http_client=http_client, webhook_delay_seconds=0.01, seed=42)

        recipients = [
            CallRecipient(
                phones=[f.phone_number],
                region=CALLE_RECIPIENT_REGION,
                locale=CALLE_RECIPIENT_LOCALE,
            )
            for f in facilities
        ]
        call_task = await adapter.place_call(
            task=build_stock_check_task(commodity.name),
            recipients=recipients,
            result_schema=None,
            recipient_result_schema=STOCK_CHECK_RESULT_SCHEMA,
            webhook_url=build_webhook_url(),
            idempotency_key=f"{sweep.id}:0",
            metadata={"sweep_id": str(sweep.id)},
        )

        # Simulates what Sprint 04's dispatch will do: link the ids CALL-E
        # just returned back onto our Call rows (matched by phone number,
        # since CALL-E assigns its own opaque recipient ids) before the
        # deferred webhook lands.
        recipient_by_phone = {r.phones[0]: r for r in call_task.recipients}
        for call, facility in zip(calls, facilities, strict=True):
            recipient_ref = recipient_by_phone[facility.phone_number]
            call.provider_call_id = call_task.id
            call.provider_recipient_id = recipient_ref.id
            await call_repo.update(call)

        await adapter.wait_for_webhook(call_task.id)

    results_repo = SqlAlchemyAvailabilityResultRepository(db_session)
    for call in calls:
        result = await results_repo.get_by_call_id(call.id)
        assert result is not None
        assert result.facility_id == call.facility_id
        assert result.commodity_id == commodity.id

    updated_calls = [await call_repo.get_by_id(c.id) for c in calls]
    assert all(c is not None and c.status != CallStatus.QUEUED for c in updated_calls)
