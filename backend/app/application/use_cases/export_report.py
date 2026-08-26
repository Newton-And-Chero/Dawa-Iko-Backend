"""Ties one Sprint 08 analytics use case's structured output to a CSV/PDF
renderer — the `GET /analytics/export` route's use case. `report` + `format`
select which compute-then-render pair runs; everything else is that
report's own parameters, forwarded straight through."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.application.ports.analytics_repository_port import AnalyticsRepositoryPort
from app.application.ports.commodity_repository import CommodityRepositoryPort
from app.application.ports.facility_repository import FacilityRepositoryPort
from app.application.use_cases.compute_facility_reliability import (
    ComputeFacilityReliabilityUseCase,
)
from app.application.use_cases.compute_stockout_analytics import ComputeStockoutAnalyticsUseCase
from app.application.use_cases.compute_watchlist_trends import ComputeWatchlistTrendsUseCase
from app.core.exceptions import ValidationError
from app.domain.services.stockout_analytics import BucketGranularity
from app.infrastructure.reporting import csv_exporter, pdf_exporter

ReportName = Literal["stockout-rate", "facility-reliability", "watchlist-trends"]
ExportFormat = Literal["csv", "pdf"]


@dataclass(frozen=True)
class ExportedReport:
    content: bytes
    media_type: str
    filename: str


class ExportReportUseCase:
    def __init__(
        self,
        analytics_repository: AnalyticsRepositoryPort,
        commodity_repository: CommodityRepositoryPort,
        facility_repository: FacilityRepositoryPort,
        *,
        stockout_threshold_pct: float,
    ) -> None:
        self._analytics = analytics_repository
        self._commodities = commodity_repository
        self._facilities = facility_repository
        self._threshold = stockout_threshold_pct

    async def execute(
        self,
        report: ReportName,
        export_format: ExportFormat,
        *,
        commodity_id: UUID | None = None,
        geography: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        granularity: BucketGranularity = "week",
        counties: list[str] | None = None,
        facility_id: UUID | None = None,
    ) -> ExportedReport:
        if report == "stockout-rate":
            return await self._export_stockout_rate(
                export_format, commodity_id, geography, date_from, date_to, granularity
            )
        if report == "facility-reliability":
            return await self._export_facility_reliability(export_format, facility_id)
        return await self._export_watchlist_trends(export_format, counties)

    async def _export_stockout_rate(
        self,
        export_format: ExportFormat,
        commodity_id: UUID | None,
        geography: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        granularity: BucketGranularity,
    ) -> ExportedReport:
        if commodity_id is None:
            raise ValidationError("commodity_id is required to export the stockout-rate report")
        result = await ComputeStockoutAnalyticsUseCase(
            self._analytics, self._commodities, stockout_threshold_pct=self._threshold
        ).execute(
            commodity_id,
            geography=geography,
            date_from=date_from,
            date_to=date_to,
            granularity=granularity,
        )
        if export_format == "csv":
            return ExportedReport(
                csv_exporter.export_stockout_analytics_csv(result), "text/csv", "stockout-rate.csv"
            )
        return ExportedReport(
            pdf_exporter.export_stockout_analytics_pdf(result),
            "application/pdf",
            "stockout-rate.pdf",
        )

    async def _export_facility_reliability(
        self, export_format: ExportFormat, facility_id: UUID | None
    ) -> ExportedReport:
        use_case = ComputeFacilityReliabilityUseCase(self._analytics, self._facilities)
        results = (
            [await use_case.compute_for_facility(facility_id)]
            if facility_id is not None
            else await use_case.compute_for_all()
        )
        if export_format == "csv":
            return ExportedReport(
                csv_exporter.export_facility_reliability_csv(results),
                "text/csv",
                "facility-reliability.csv",
            )
        return ExportedReport(
            pdf_exporter.export_facility_reliability_pdf(results),
            "application/pdf",
            "facility-reliability.pdf",
        )

    async def _export_watchlist_trends(
        self, export_format: ExportFormat, counties: list[str] | None
    ) -> ExportedReport:
        if not counties:
            raise ValidationError("counties is required to export the watchlist-trends report")
        result = await ComputeWatchlistTrendsUseCase(
            self._analytics, self._commodities, stockout_threshold_pct=self._threshold
        ).execute(counties)
        if export_format == "csv":
            return ExportedReport(
                csv_exporter.export_watchlist_trends_csv(result),
                "text/csv",
                "watchlist-trends.csv",
            )
        return ExportedReport(
            pdf_exporter.export_watchlist_trends_pdf(result),
            "application/pdf",
            "watchlist-trends.pdf",
        )
