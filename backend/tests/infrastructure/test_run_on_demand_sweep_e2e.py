from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.run_on_demand_sweep import RunOnDemandSweepUseCase
from app.core.config import Settings
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.enums import CommodityCategory, FacilitySource, FacilityType, SweepStatus
from app.domain.value_objects.geography_scope import CountyScope
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.call_e.mock_calle_adapter import MockCallEAdapter
from app.infrastructure.call_e.redis_call_gate import RedisCallGate
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.geo.postgis_geography_resolver import PostGISGeographyResolver
from app.infrastructure.realtime.event_bus import RealtimeEventBus
from app.main import app


def _facility(n: int) -> Facility:
    return Facility(
        name=f"E2E Facility {n}",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number=f"+2547010{n:04d}",
        source=FacilitySource.KMHFL,
    )


async def test_sweep_completes_once_all_mock_webhooks_land(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility_repo = SqlAlchemyFacilityRepository(db_session)
    for i in range(3):
        await facility_repo.add(_facility(i))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        adapter = MockCallEAdapter(http_client=http_client, webhook_delay_seconds=0.01, seed=7)

        settings = Settings(MAX_RECIPIENTS_PER_TASK=50)
        use_case = RunOnDemandSweepUseCase(
            geography_resolver=PostGISGeographyResolver(db_session),
            call_repository=SqlAlchemyCallRepository(db_session),
            sweep_repository=SqlAlchemySweepRepository(db_session),
            commodity_repository=SqlAlchemyCommodityRepository(db_session),
            call_provider=adapter,
            call_gate=RedisCallGate(get_redis(), settings),
            settings=settings,
            realtime_event_bus=RealtimeEventBus(get_redis()),
        )

        sweep_id = await use_case.execute(
            commodity_id=commodity.id, geography=CountyScope(county="Kirinyaga")
        )

        call_repo = SqlAlchemyCallRepository(db_session)
        calls = await call_repo.list_by_sweep_id(sweep_id)
        assert len(calls) == 3

        for call in calls:
            assert call.provider_call_id is not None
            await adapter.wait_for_webhook(call.provider_call_id)

    db_session.expire_all()
    sweep_repo = SqlAlchemySweepRepository(db_session)
    sweep = await sweep_repo.get_by_id(sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.COMPLETED
