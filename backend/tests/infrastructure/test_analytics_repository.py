"""SqlAlchemyAnalyticsRepository — the one place Sprint 08's hand-written
aggregate SQL lives. Seeds a small multi-sweep history against a real
Postgres instance and asserts the aggregate numbers directly, not just
"doesn't crash" (workflows/08's testing requirement)."""

from datetime import UTC, datetime
from decimal import Decimal

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
from app.infrastructure.db.repositories.analytics_repository import SqlAlchemyAnalyticsRepository
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _facility(name: str, county: str = "Kirinyaga") -> Facility:
    return Facility(
        name=name,
        type=FacilityType.DISPENSARY,
        county=county,
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number=f"+2547{abs(hash(name)) % 10**8:08d}",
        source=FacilitySource.KMHFL,
    )


async def _seed_sweep_with_results(
    session: AsyncSession,
    *,
    commodity_id,
    geography: dict,
    created_at: datetime,
    in_stock_flags: list[bool],
) -> None:
    """One sweep with one Call+AvailabilityResult per flag in `in_stock_flags`."""
    sweep = await SqlAlchemySweepRepository(session).add(
        Sweep(
            commodity_id=commodity_id,
            geography_scope=geography,
            trigger_type=SweepTrigger.ON_DEMAND,
            created_at=created_at,
        )
    )
    facility_repo = SqlAlchemyFacilityRepository(session)
    call_repo = SqlAlchemyCallRepository(session)
    result_repo = SqlAlchemyAvailabilityResultRepository(session)
    for i, in_stock in enumerate(in_stock_flags):
        facility = await facility_repo.add(_facility(f"Facility {created_at.date()}-{i}"))
        call = await call_repo.add(
            Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
        )
        await result_repo.add(
            AvailabilityResult(
                call_id=call.id,
                facility_id=facility.id,
                commodity_id=commodity_id,
                in_stock=StockStatus.YES if in_stock else StockStatus.NO,
            )
        )


async def test_list_sweep_stock_summaries_counts_checked_and_in_stock(
    db_session: AsyncSession,
) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    week1 = datetime(2026, 1, 5, tzinfo=UTC)
    week2 = datetime(2026, 1, 12, tzinfo=UTC)
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Kirinyaga"},
        created_at=week1,
        in_stock_flags=[False, False, True],  # 1/3 in stock
    )
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Kirinyaga"},
        created_at=week2,
        in_stock_flags=[True, True],  # 2/2 in stock
    )

    repo = SqlAlchemyAnalyticsRepository(db_session)
    summaries = await repo.list_sweep_stock_summaries(commodity.id)

    assert len(summaries) == 2
    assert summaries[0].created_at == week1
    assert summaries[0].facilities_checked_count == 3
    assert summaries[0].facilities_with_stock_count == 1
    assert summaries[1].created_at == week2
    assert summaries[1].facilities_checked_count == 2
    assert summaries[1].facilities_with_stock_count == 2


async def test_list_sweep_stock_summaries_filters_by_geography_substring(
    db_session: AsyncSession,
) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Kirinyaga"},
        created_at=datetime(2026, 1, 5, tzinfo=UTC),
        in_stock_flags=[False],
    )
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Nairobi"},
        created_at=datetime(2026, 1, 6, tzinfo=UTC),
        in_stock_flags=[True],
    )

    repo = SqlAlchemyAnalyticsRepository(db_session)
    kirinyaga_only = await repo.list_sweep_stock_summaries(commodity.id, geography="Kirinyaga")

    assert len(kirinyaga_only) == 1
    assert kirinyaga_only[0].facilities_with_stock_count == 0


async def test_list_sweep_stock_summaries_filters_by_date_range(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Kirinyaga"},
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        in_stock_flags=[True],
    )
    await _seed_sweep_with_results(
        db_session,
        commodity_id=commodity.id,
        geography={"kind": "county", "county": "Kirinyaga"},
        created_at=datetime(2026, 2, 1, tzinfo=UTC),
        in_stock_flags=[True],
    )

    repo = SqlAlchemyAnalyticsRepository(db_session)
    only_january = await repo.list_sweep_stock_summaries(
        commodity.id,
        date_from=datetime(2026, 1, 1, tzinfo=UTC),
        date_to=datetime(2026, 1, 31, tzinfo=UTC),
    )

    assert len(only_january) == 1
    assert only_january[0].created_at == datetime(2026, 1, 1, tzinfo=UTC)


async def test_facility_call_stats_counts_completed_vs_total(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility = await SqlAlchemyFacilityRepository(db_session).add(_facility("Reliable Chemist"))
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    call_repo = SqlAlchemyCallRepository(db_session)
    for status in [CallStatus.COMPLETED, CallStatus.COMPLETED, CallStatus.NO_ANSWER]:
        await call_repo.add(Call(sweep_id=sweep.id, facility_id=facility.id, status=status))

    repo = SqlAlchemyAnalyticsRepository(db_session)
    stats = await repo.facility_call_stats(facility.id)

    assert stats.total_calls == 3
    assert stats.completed_calls == 2
    assert stats.answer_rate == 2 / 3


async def test_facility_result_confidences_excludes_null_confidence(
    db_session: AsyncSession,
) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    facility = await SqlAlchemyFacilityRepository(db_session).add(_facility("Chemist"))
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    call_repo = SqlAlchemyCallRepository(db_session)
    result_repo = SqlAlchemyAvailabilityResultRepository(db_session)
    for confidence in [0.9, 0.5, None]:
        call = await call_repo.add(
            Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
        )
        await result_repo.add(
            AvailabilityResult(
                call_id=call.id,
                facility_id=facility.id,
                commodity_id=commodity.id,
                in_stock=StockStatus.YES,
                price_kes=Decimal("10.00"),
                confidence=confidence,
            )
        )

    repo = SqlAlchemyAnalyticsRepository(db_session)
    confidences = await repo.facility_result_confidences(facility.id)

    assert sorted(confidences) == [0.5, 0.9]


async def test_list_facility_ids_with_calls(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    called_facility = await SqlAlchemyFacilityRepository(db_session).add(_facility("Called"))
    await SqlAlchemyFacilityRepository(db_session).add(_facility("Never called"))
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
        )
    )
    await SqlAlchemyCallRepository(db_session).add(
        Call(sweep_id=sweep.id, facility_id=called_facility.id, status=CallStatus.COMPLETED)
    )

    repo = SqlAlchemyAnalyticsRepository(db_session)
    ids = await repo.list_facility_ids_with_calls()

    assert ids == [called_facility.id]
