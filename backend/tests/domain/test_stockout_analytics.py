from datetime import UTC, date, datetime
from uuid import uuid4

from app.domain.services.stockout_analytics import bucket_stockout_rate, compute_stockout_streak
from app.domain.value_objects.analytics import SweepStockSummary


def _summary(when: datetime, checked: int, with_stock: int) -> SweepStockSummary:
    return SweepStockSummary(
        sweep_id=uuid4(),
        created_at=when,
        facilities_checked_count=checked,
        facilities_with_stock_count=with_stock,
    )


def test_sweep_stock_summary_pct_in_stock_defaults_full_when_nothing_checked() -> None:
    summary = _summary(datetime(2026, 1, 1, tzinfo=UTC), 0, 0)
    assert summary.pct_in_stock == 1.0


def test_bucket_stockout_rate_groups_by_week() -> None:
    summaries = [
        _summary(datetime(2026, 1, 5, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 7, tzinfo=UTC), 10, 8),
        _summary(datetime(2026, 1, 12, tzinfo=UTC), 10, 2),
    ]

    buckets = bucket_stockout_rate(summaries, threshold_pct=0.5, granularity="week")

    assert len(buckets) == 2
    assert buckets[0].period_start == date(2026, 1, 5)
    assert buckets[0].sweep_count == 2
    assert buckets[0].stockout_sweep_count == 1
    assert buckets[0].stockout_rate == 0.5
    assert buckets[1].period_start == date(2026, 1, 12)
    assert buckets[1].sweep_count == 1
    assert buckets[1].stockout_sweep_count == 1


def test_bucket_stockout_rate_groups_by_month() -> None:
    summaries = [
        _summary(datetime(2026, 1, 5, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 25, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 2, 3, tzinfo=UTC), 10, 10),
    ]

    buckets = bucket_stockout_rate(summaries, threshold_pct=0.5, granularity="month")

    assert len(buckets) == 2
    assert buckets[0].period_start == date(2026, 1, 1)
    assert buckets[0].sweep_count == 2
    assert buckets[0].stockout_sweep_count == 2
    assert buckets[1].period_start == date(2026, 2, 1)
    assert buckets[1].stockout_sweep_count == 0


def test_bucket_stockout_rate_empty_input_yields_no_buckets() -> None:
    assert bucket_stockout_rate([], threshold_pct=0.5, granularity="week") == []


def test_streak_computed_from_unordered_input() -> None:
    oldest = _summary(datetime(2026, 1, 1, tzinfo=UTC), 10, 10)
    middle = _summary(datetime(2026, 1, 8, tzinfo=UTC), 10, 0)
    newest = _summary(datetime(2026, 1, 15, tzinfo=UTC), 10, 0)

    streak = compute_stockout_streak([newest, oldest, middle], threshold_pct=0.5)

    assert streak.current_streak == 2
    assert streak.longest_streak == 2


def test_current_streak_zero_when_most_recent_sweep_has_stock() -> None:
    summaries = [
        _summary(datetime(2026, 1, 1, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 8, tzinfo=UTC), 10, 10),
    ]

    streak = compute_stockout_streak(summaries, threshold_pct=0.5)

    assert streak.current_streak == 0
    assert streak.longest_streak == 1


def test_longest_streak_is_not_broken_by_current_streak_position() -> None:
    summaries = [
        _summary(datetime(2026, 1, 1, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 8, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 15, tzinfo=UTC), 10, 0),
        _summary(datetime(2026, 1, 22, tzinfo=UTC), 10, 10),
        _summary(datetime(2026, 1, 29, tzinfo=UTC), 10, 0),
    ]

    streak = compute_stockout_streak(summaries, threshold_pct=0.5)

    assert streak.current_streak == 1
    assert streak.longest_streak == 3
