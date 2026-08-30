from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from app.domain.value_objects.analytics import SweepStockSummary

BucketGranularity = Literal["week", "month"]


@dataclass(frozen=True)
class StockoutRateBucket:
    period_start: date
    sweep_count: int
    stockout_sweep_count: int

    @property
    def stockout_rate(self) -> float:
        if self.sweep_count == 0:
            return 0.0
        return self.stockout_sweep_count / self.sweep_count


@dataclass(frozen=True)
class StockoutStreak:
    current_streak: int
    longest_streak: int


def _bucket_start(when: datetime, granularity: BucketGranularity) -> date:
    day = when.date()
    if granularity == "month":
        return day.replace(day=1)
    return day - timedelta(days=day.weekday())


def bucket_stockout_rate(
    summaries: Sequence[SweepStockSummary],
    *,
    threshold_pct: float,
    granularity: BucketGranularity,
) -> list[StockoutRateBucket]:
    buckets: dict[date, list[SweepStockSummary]] = {}
    for summary in summaries:
        key = _bucket_start(summary.created_at, granularity)
        buckets.setdefault(key, []).append(summary)

    return [
        StockoutRateBucket(
            period_start=period_start,
            sweep_count=len(rows),
            stockout_sweep_count=sum(1 for r in rows if r.pct_in_stock <= threshold_pct),
        )
        for period_start, rows in sorted(buckets.items())
    ]


def compute_stockout_streak(
    summaries: Sequence[SweepStockSummary], *, threshold_pct: float
) -> StockoutStreak:
    ordered = sorted(summaries, key=lambda s: s.created_at)

    longest = 0
    running = 0
    for summary in ordered:
        if summary.pct_in_stock <= threshold_pct:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    current = 0
    for summary in reversed(ordered):
        if summary.pct_in_stock <= threshold_pct:
            current += 1
        else:
            break

    return StockoutStreak(current_streak=current, longest_streak=longest)
