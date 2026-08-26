"""Analytics response schemas (Sprint 08). Field names mirror the use-case
result dataclasses in `application/use_cases/compute_*.py` exactly; each
`from_result` classmethod is the one place that mapping is written."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.application.use_cases.compute_facility_reliability import FacilityReliabilityResult
from app.application.use_cases.compute_stockout_analytics import StockoutAnalyticsResult
from app.application.use_cases.compute_watchlist_trends import WatchlistTrendsResult
from app.domain.services.stockout_analytics import BucketGranularity, StockoutRateBucket


class StockoutRateBucketOut(BaseModel):
    period_start: date
    sweep_count: int
    stockout_sweep_count: int
    stockout_rate: float

    @classmethod
    def from_bucket(cls, bucket: StockoutRateBucket) -> "StockoutRateBucketOut":
        return cls(
            period_start=bucket.period_start,
            sweep_count=bucket.sweep_count,
            stockout_sweep_count=bucket.stockout_sweep_count,
            stockout_rate=bucket.stockout_rate,
        )


class StockoutAnalyticsOut(BaseModel):
    commodity_id: UUID
    commodity_name: str
    geography: str | None
    granularity: BucketGranularity
    buckets: list[StockoutRateBucketOut]
    current_streak: int
    longest_streak: int
    summary: str

    @classmethod
    def from_result(cls, result: StockoutAnalyticsResult) -> "StockoutAnalyticsOut":
        return cls(
            commodity_id=result.commodity_id,
            commodity_name=result.commodity_name,
            geography=result.geography,
            granularity=result.granularity,
            buckets=[StockoutRateBucketOut.from_bucket(b) for b in result.buckets],
            current_streak=result.streak.current_streak,
            longest_streak=result.streak.longest_streak,
            summary=result.summary,
        )


class FacilityReliabilityOut(BaseModel):
    facility_id: UUID
    total_calls: int
    completed_calls: int
    answer_rate: float
    avg_result_confidence: float | None
    reliability_score: float

    @classmethod
    def from_result(cls, result: FacilityReliabilityResult) -> "FacilityReliabilityOut":
        return cls(
            facility_id=result.facility_id,
            total_calls=result.total_calls,
            completed_calls=result.completed_calls,
            answer_rate=result.answer_rate,
            avg_result_confidence=result.avg_result_confidence,
            reliability_score=result.reliability_score,
        )


class WatchlistTrendRowOut(BaseModel):
    commodity_id: UUID
    commodity_name: str
    county: str
    sweep_count: int
    stockout_sweep_count: int
    stockout_rate: float


class WatchlistTrendsOut(BaseModel):
    rows: list[WatchlistTrendRowOut]
    ranked_commodity_ids: list[UUID]

    @classmethod
    def from_result(cls, result: WatchlistTrendsResult) -> "WatchlistTrendsOut":
        return cls(
            rows=[
                WatchlistTrendRowOut(
                    commodity_id=row.commodity_id,
                    commodity_name=row.commodity_name,
                    county=row.county,
                    sweep_count=row.sweep_count,
                    stockout_sweep_count=row.stockout_sweep_count,
                    stockout_rate=row.stockout_rate,
                )
                for row in result.rows
            ],
            ranked_commodity_ids=result.ranked_commodity_ids,
        )
