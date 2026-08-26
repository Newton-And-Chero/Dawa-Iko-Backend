"""PDF rendering for Sprint 08 analytics reports, via reportlab (pure
Python — no system-level rendering dependency, unlike weasyprint's Pango/
Cairo requirement). `_render_table` is the one shared plumbing bit; each
`export_*_pdf` function shapes one report's rows into a title + header row +
data rows."""

import io
from collections.abc import Sequence
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.application.use_cases.compute_facility_reliability import FacilityReliabilityResult
from app.application.use_cases.compute_stockout_analytics import StockoutAnalyticsResult
from app.application.use_cases.compute_watchlist_trends import WatchlistTrendsResult


def _render_table(
    title: str, subtitle: str, headers: Sequence[str], rows: Sequence[Sequence[Any]]
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()

    table_data = [list(headers)] + [[str(cell) for cell in row] for row in rows]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ]
        )
    )

    doc.build(
        [
            Paragraph(title, styles["Title"]),
            Paragraph(subtitle, styles["Normal"]),
            Spacer(1, 12),
            table,
        ]
    )
    return buffer.getvalue()


def export_stockout_analytics_pdf(result: StockoutAnalyticsResult) -> bytes:
    headers = ["Period start", "Sweeps", "Stockout sweeps", "Stockout rate"]
    rows = [
        [
            bucket.period_start.isoformat(),
            bucket.sweep_count,
            bucket.stockout_sweep_count,
            f"{bucket.stockout_rate:.0%}",
        ]
        for bucket in result.buckets
    ]
    return _render_table(
        f"Stockout analytics — {result.commodity_name}", result.summary, headers, rows
    )


def export_facility_reliability_pdf(results: list[FacilityReliabilityResult]) -> bytes:
    headers = [
        "Facility ID",
        "Calls",
        "Completed",
        "Answer rate",
        "Avg confidence",
        "Reliability score",
    ]
    rows = [
        [
            str(r.facility_id),
            r.total_calls,
            r.completed_calls,
            f"{r.answer_rate:.0%}",
            f"{r.avg_result_confidence:.0%}" if r.avg_result_confidence is not None else "n/a",
            f"{r.reliability_score:.2f}",
        ]
        for r in results
    ]
    return _render_table("Facility reliability", f"{len(results)} facilities scored", headers, rows)


def export_watchlist_trends_pdf(result: WatchlistTrendsResult) -> bytes:
    headers = ["Commodity", "County", "Sweeps", "Stockout sweeps", "Stockout rate"]
    rows = [
        [
            row.commodity_name,
            row.county,
            row.sweep_count,
            row.stockout_sweep_count,
            f"{row.stockout_rate:.0%}",
        ]
        for row in result.rows
    ]
    subtitle = f"{len(result.ranked_commodity_ids)} priority-watchlist commodities compared"
    return _render_table("Priority watchlist trends", subtitle, headers, rows)
