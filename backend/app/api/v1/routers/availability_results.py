import dataclasses
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import page_params
from app.api.v1.schemas.availability_result import AvailabilityResultOut
from app.api.v1.schemas.page import Page, PageParams, paginate
from app.application.use_cases.list_availability_results import (
    AvailabilityResultFilter,
    ListAvailabilityResultsUseCase,
)
from app.domain.entities.availability_result import AvailabilityResult
from app.domain.enums import StockStatus
from app.infrastructure.db.repositories.availability_result_repository import (
    SqlAlchemyAvailabilityResultRepository,
)
from app.infrastructure.db.session import get_session

router = APIRouter(prefix="/availability-results", tags=["availability-results"])


def _out(result: AvailabilityResult) -> AvailabilityResultOut:
    return AvailabilityResultOut(**dataclasses.asdict(result))


@router.get("", response_model=Page[AvailabilityResultOut])
async def list_availability_results(
    commodity_id: UUID | None = None,
    county: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    in_stock: StockStatus | None = None,
    page: PageParams = Depends(page_params),
    session: AsyncSession = Depends(get_session),
) -> Page[AvailabilityResultOut]:
    use_case = ListAvailabilityResultsUseCase(SqlAlchemyAvailabilityResultRepository(session))
    results = await use_case.execute(
        AvailabilityResultFilter(
            commodity_id=commodity_id,
            county=county,
            date_from=date_from,
            date_to=date_to,
            in_stock=in_stock,
        )
    )
    return paginate([_out(r) for r in results], page)
