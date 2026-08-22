"""Repository round-trip integration tests. Requires a real Postgres+PostGIS instance."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.list_commodities import CommodityFilter
from app.application.use_cases.list_facilities import FacilityFilter
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber
from app.domain.entities.sweep import Sweep
from app.domain.entities.user import User
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    EscalationSeverity,
    EscalationStatus,
    FacilitySource,
    FacilityType,
    NotificationChannel,
    PhoneVerificationStatus,
    StockStatus,
    SweepStatus,
    SweepTrigger,
    UserRole,
)
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.stockout_alert_repository import (
    SqlAlchemyStockoutAlertRepository,
)
from app.infrastructure.db.repositories.subscriber_repository import (
    SqlAlchemySubscriberRepository,
)
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository


def _sample_facility() -> Facility:
    return Facility(
        name="Test Dispensary",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )


def _sample_commodity() -> Commodity:
    return Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)


async def test_facility_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyFacilityRepository(db_session)
    facility = _sample_facility()

    added = await repo.add(facility)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.id == facility.id
    assert fetched.name == facility.name
    assert fetched.gps_lat == pytest.approx(facility.gps_lat)
    assert fetched.gps_lng == pytest.approx(facility.gps_lng)


async def test_facility_update_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyFacilityRepository(db_session)
    facility = await repo.add(_sample_facility())

    facility.name = "Renamed Dispensary"
    facility.phone_verification_status = PhoneVerificationStatus.VERIFIED
    updated = await repo.update(facility)

    fetched = await repo.get_by_id(facility.id)
    assert fetched is not None
    assert fetched.name == "Renamed Dispensary"
    assert fetched.phone_verification_status == PhoneVerificationStatus.VERIFIED
    assert updated.name == "Renamed Dispensary"


async def test_facility_list_by_filter(db_session: AsyncSession) -> None:
    repo = SqlAlchemyFacilityRepository(db_session)
    await repo.add(_sample_facility())
    await repo.add(
        Facility(
            name="Westlands Dispensary",
            type=FacilityType.DISPENSARY,
            county="Nairobi",
            sub_county="Westlands",
            ward="Karura",
            gps_lat=-1.26,
            gps_lng=36.81,
            phone_number="+254700000099",
            source=FacilitySource.KMHFL,
        )
    )

    kirinyaga_only = await repo.list_by_filter(FacilityFilter(county="Kirinyaga"))
    assert [f.name for f in kirinyaga_only] == ["Test Dispensary"]

    dispensaries = await repo.list_by_filter(FacilityFilter(type=FacilityType.DISPENSARY))
    assert len(dispensaries) == 2


async def test_commodity_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyCommodityRepository(db_session)
    commodity = Commodity(
        name="Carbetocin",
        category=CommodityCategory.ESSENTIAL_MEDICINE,
        keml_code="KEML-001",
        aliases=["PPH drug"],
        is_priority_watchlist=True,
    )

    added = await repo.add(commodity)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.name == commodity.name
    assert fetched.aliases == commodity.aliases
    assert fetched.is_priority_watchlist is True


async def test_commodity_update_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyCommodityRepository(db_session)
    commodity = await repo.add(_sample_commodity())

    commodity.is_priority_watchlist = True
    updated = await repo.update(commodity)

    fetched = await repo.get_by_id(commodity.id)
    assert fetched is not None
    assert fetched.is_priority_watchlist is True
    assert updated.is_priority_watchlist is True


async def test_commodity_list_by_filter_alias_search(db_session: AsyncSession) -> None:
    repo = SqlAlchemyCommodityRepository(db_session)
    await repo.add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            aliases=["PPH drug"],
            is_priority_watchlist=True,
        )
    )
    await repo.add(
        Commodity(
            name="Oxytocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            aliases=["Pitocin"],
            is_priority_watchlist=False,
        )
    )

    matches = await repo.list_by_filter(CommodityFilter(search="PPH"))
    assert [c.name for c in matches] == ["Carbetocin"]

    watchlist_only = await repo.list_by_filter(CommodityFilter(is_priority_watchlist=True))
    assert [c.name for c in watchlist_only] == ["Carbetocin"]


async def test_user_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(db_session)
    user = User(name="Ada Analyst", role=UserRole.ANALYST, org="MOH")

    added = await repo.add(user)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.role == UserRole.ANALYST


async def test_sweep_round_trip(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(_sample_commodity())

    repo = SqlAlchemySweepRepository(db_session)
    sweep = Sweep(
        commodity_id=commodity.id,
        geography_scope={"county": "Kirinyaga"},
        trigger_type=SweepTrigger.ON_DEMAND,
        status=SweepStatus.QUEUED,
    )

    added = await repo.add(sweep)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.geography_scope == {"county": "Kirinyaga"}
    assert fetched.status == SweepStatus.QUEUED


async def test_call_round_trip(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(_sample_commodity())
    facility = await SqlAlchemyFacilityRepository(db_session).add(_sample_facility())
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
            status=SweepStatus.QUEUED,
        )
    )

    repo = SqlAlchemyCallRepository(db_session)
    call = Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.QUEUED)

    added = await repo.add(call)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.sweep_id == sweep.id
    assert fetched.facility_id == facility.id


async def test_availability_result_round_trip(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(_sample_commodity())
    facility = await SqlAlchemyFacilityRepository(db_session).add(_sample_facility())
    sweep = await SqlAlchemySweepRepository(db_session).add(
        Sweep(
            commodity_id=commodity.id,
            geography_scope={"county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
            status=SweepStatus.QUEUED,
        )
    )
    call = await SqlAlchemyCallRepository(db_session).add(
        Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
    )

    repo = SqlAlchemyAvailabilityResultRepository(db_session)
    result = AvailabilityResult(
        call_id=call.id,
        facility_id=facility.id,
        commodity_id=commodity.id,
        in_stock=StockStatus.YES,
        price_kes=Decimal("120.50"),
        confidence=0.9,
    )

    added = await repo.add(result)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.price_kes == Decimal("120.50")
    assert fetched.in_stock == StockStatus.YES


async def test_stockout_alert_round_trip(db_session: AsyncSession) -> None:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(_sample_commodity())

    repo = SqlAlchemyStockoutAlertRepository(db_session)
    alert = StockoutAlert(
        commodity_id=commodity.id,
        geography={"county": "Kirinyaga"},
        severity=EscalationSeverity.HIGH,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
        status=EscalationStatus.OPEN,
    )

    added = await repo.add(alert)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.severity == EscalationSeverity.HIGH
    assert fetched.status == EscalationStatus.OPEN


async def test_subscriber_round_trip(db_session: AsyncSession) -> None:
    repo = SqlAlchemySubscriberRepository(db_session)
    subscriber = Subscriber(
        name="County Pharmacist",
        notification_channel=NotificationChannel.SMS,
        phone="+254700000002",
        watchlist_commodities=[uuid.uuid4()],
        watchlist_geography={"county": "Kirinyaga"},
    )

    added = await repo.add(subscriber)
    fetched = await repo.get_by_id(added.id)

    assert fetched is not None
    assert fetched.watchlist_commodities == subscriber.watchlist_commodities
    assert fetched.notification_channel == NotificationChannel.SMS
