import csv
import io
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.availability_result import AvailabilityResult
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
    StockStatus,
    SweepTrigger,
    UserRole,
)
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.repositories.call_repository import SqlAlchemyCallRepository
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.infrastructure.db.repositories.sweep_repository import SqlAlchemySweepRepository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_sweep_history(db_session: AsyncSession) -> Commodity:
    commodity = await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(
            name="Carbetocin",
            category=CommodityCategory.ESSENTIAL_MEDICINE,
            is_priority_watchlist=True,
        )
    )
    facility_repo = SqlAlchemyFacilityRepository(db_session)
    sweep_repo = SqlAlchemySweepRepository(db_session)
    call_repo = SqlAlchemyCallRepository(db_session)
    result_repo = SqlAlchemyAvailabilityResultRepository(db_session)

    for week, flags in [
        (datetime(2026, 1, 5, tzinfo=UTC), [False, False, True]),
        (datetime(2026, 1, 12, tzinfo=UTC), [True, True]),
    ]:
        sweep = await sweep_repo.add(
            Sweep(
                commodity_id=commodity.id,
                geography_scope={"kind": "county", "county": "Kirinyaga"},
                trigger_type=SweepTrigger.ON_DEMAND,
                created_at=week,
            )
        )
        for i, in_stock in enumerate(flags):
            facility = await facility_repo.add(
                Facility(
                    name=f"Facility {week.date()}-{i}",
                    type=FacilityType.DISPENSARY,
                    county="Kirinyaga",
                    sub_county="Mwea",
                    ward="Wamumu",
                    gps_lat=-0.6849,
                    gps_lng=37.3667,
                    phone_number=f"+2547{abs(hash((week, i))) % 10**8:08d}",
                    source=FacilitySource.KMHFL,
                )
            )
            call = await call_repo.add(
                Call(sweep_id=sweep.id, facility_id=facility.id, status=CallStatus.COMPLETED)
            )
            await result_repo.add(
                AvailabilityResult(
                    call_id=call.id,
                    facility_id=facility.id,
                    commodity_id=commodity.id,
                    in_stock=StockStatus.YES if in_stock else StockStatus.NO,
                    confidence=0.8,
                )
            )
    return commodity


async def test_stockout_rate_denied_without_token(client: AsyncClient) -> None:
    response = await client.get(
        "/v1/analytics/stockout-rate",
        params={"commodity_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


async def test_viewer_can_get_stockout_rate(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    commodity = await _seed_sweep_history(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get(
        "/v1/analytics/stockout-rate",
        headers=_auth(token),
        params={"commodity_id": str(commodity.id), "geography": "Kirinyaga"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["commodity_name"] == "Carbetocin"
    assert len(body["buckets"]) == 2
    assert "Carbetocin unavailable in Kirinyaga" in body["summary"]


async def test_stockout_rate_unknown_commodity_returns_404(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get(
        "/v1/analytics/stockout-rate",
        headers=_auth(token),
        params={"commodity_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


async def test_facility_reliability_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    commodity = await _seed_sweep_history(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get("/v1/analytics/facility-reliability", headers=_auth(token))

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 5
    assert all(row["reliability_score"] is not None for row in rows)
    assert commodity is not None


async def test_watchlist_trends_endpoint(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    await _seed_sweep_history(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get(
        "/v1/analytics/watchlist-trends",
        headers=_auth(token),
        params={"county": ["Kirinyaga", "Nairobi"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 2
    assert len(body["ranked_commodity_ids"]) == 1


async def test_export_stockout_rate_csv_is_parseable(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    commodity = await _seed_sweep_history(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get(
        "/v1/analytics/export",
        headers=_auth(token),
        params={"report": "stockout-rate", "format": "csv", "commodity_id": str(commodity.id)},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    reader = csv.reader(io.StringIO(response.text))
    header, *rows = list(reader)
    assert header == ["period_start", "sweep_count", "stockout_sweep_count", "stockout_rate"]
    assert len(rows) == 2


async def test_export_facility_reliability_pdf_produces_valid_bytes(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]],
) -> None:
    await _seed_sweep_history(db_session)
    _, token = await make_user_token(UserRole.VIEWER)

    response = await client.get(
        "/v1/analytics/export",
        headers=_auth(token),
        params={"report": "facility-reliability", "format": "pdf"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 500


async def test_export_stockout_rate_without_commodity_id_returns_422(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get(
        "/v1/analytics/export",
        headers=_auth(token),
        params={"report": "stockout-rate", "format": "csv"},
    )
    assert response.status_code == 422


async def test_export_watchlist_trends_without_counties_returns_422(
    client: AsyncClient, make_user_token: Callable[[UserRole], Awaitable[tuple[User, str]]]
) -> None:
    _, token = await make_user_token(UserRole.VIEWER)
    response = await client.get(
        "/v1/analytics/export",
        headers=_auth(token),
        params={"report": "watchlist-trends", "format": "csv"},
    )
    assert response.status_code == 422
