from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    StockStatus,
    SweepTrigger,
)
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


async def _seed_result(
    db_session: AsyncSession, *, in_stock: StockStatus, confidence: float | None
) -> AvailabilityResult:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility = await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Results Route Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000096",
            source=FacilitySource.KMHFL,
        )
    )
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    call = await SqlAlchemyCallRepository(db_session).add(
        Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
    )
    return await SqlAlchemyAvailabilityResultRepository(db_session).add(
        AvailabilityResult(
            call_id=call.id,
            facility_id=facility.id,
            commodity_id=commodity.id,
            in_stock=in_stock,
            confidence=confidence,
        )
    )


async def test_availability_results_is_public_and_ranks_in_stock_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    out_of_stock = await _seed_result(db_session, in_stock=StockStatus.NO, confidence=0.9)
    in_stock = await _seed_result(db_session, in_stock=StockStatus.YES, confidence=0.5)

    response = await client.get("/v1/availability-results")

    assert response.status_code == 200
    items = response.json()["items"]
    ids = [item["id"] for item in items]
    assert str(in_stock.id) in ids
    assert str(out_of_stock.id) in ids
    assert ids.index(str(in_stock.id)) < ids.index(str(out_of_stock.id))


async def test_availability_results_filters_by_stock_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_result(db_session, in_stock=StockStatus.NO, confidence=0.9)
    in_stock = await _seed_result(db_session, in_stock=StockStatus.YES, confidence=0.5)

    response = await client.get("/v1/availability-results", params={"in_stock": "yes"})

    assert response.status_code == 200
    items = response.json()["items"]
    assert all(item["in_stock"] == "yes" for item in items)
    assert any(item["id"] == str(in_stock.id) for item in items)
