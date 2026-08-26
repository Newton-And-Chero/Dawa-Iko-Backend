"""CSV rendering for Sprint 08 analytics reports. Each `export_*_csv`
function shapes one report's rows into a flat table; `_write_csv` is the one
shared plumbing bit (stdlib `csv.DictWriter` over an in-memory buffer)."""

import csv
import io
from collections.abc import Iterable, Mapping
from typing import Any

from app.application.use_cases.compute_facility_reliability import FacilityReliabilityResult
from app.application.use_cases.compute_stockout_analytics import StockoutAnalyticsResult
from app.application.use_cases.compute_watchlist_trends import WatchlistTrendsResult


def _write_csv(fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def export_stockout_analytics_csv(result: StockoutAnalyticsResult) -> bytes:
    fieldnames = ["period_start", "sweep_count", "stockout_sweep_count", "stockout_rate"]
    rows = [
        {
            "period_start": bucket.period_start.isoformat(),
            "sweep_count": bucket.sweep_count,
            "stockout_sweep_count": bucket.stockout_sweep_count,
            "stockout_rate": f"{bucket.stockout_rate:.4f}",
        }
        for bucket in result.buckets
    ]
    return _write_csv(fieldnames, rows)


def export_facility_reliability_csv(results: list[FacilityReliabilityResult]) -> bytes:
    fieldnames = [
        "facility_id",
        "total_calls",
        "completed_calls",
        "answer_rate",
        "avg_result_confidence",
        "reliability_score",
    ]
    rows = [
        {
            "facility_id": str(r.facility_id),
            "total_calls": r.total_calls,
            "completed_calls": r.completed_calls,
            "answer_rate": f"{r.answer_rate:.4f}",
            "avg_result_confidence": (
                f"{r.avg_result_confidence:.4f}" if r.avg_result_confidence is not None else ""
            ),
            "reliability_score": f"{r.reliability_score:.4f}",
        }
        for r in results
    ]
    return _write_csv(fieldnames, rows)


def export_watchlist_trends_csv(result: WatchlistTrendsResult) -> bytes:
    fieldnames = [
        "commodity_id",
        "commodity_name",
        "county",
        "sweep_count",
        "stockout_sweep_count",
        "stockout_rate",
    ]
    rows = [
        {
            "commodity_id": str(row.commodity_id),
            "commodity_name": row.commodity_name,
            "county": row.county,
            "sweep_count": row.sweep_count,
            "stockout_sweep_count": row.stockout_sweep_count,
            "stockout_rate": f"{row.stockout_rate:.4f}",
        }
        for row in result.rows
    ]
    return _write_csv(fieldnames, rows)
