from app.domain.enums import EscalationSeverity
from app.domain.services.severity import classify_severity


def test_zero_stock_priority_commodity_dense_area_is_high() -> None:
    severity = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
        facility_density=10,
    )
    assert severity == EscalationSeverity.HIGH


def test_zero_stock_priority_commodity_sparse_area_is_critical() -> None:
    severity = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=3,
        facilities_with_stock_count=0,
        facility_density=2,
    )
    assert severity == EscalationSeverity.CRITICAL


def test_partial_stock_is_lower_severity_than_zero_stock() -> None:
    zero_stock = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
        facility_density=10,
    )
    partial_stock = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=10,
        facilities_with_stock_count=4,
        facility_density=10,
    )
    severity_order = [
        EscalationSeverity.LOW,
        EscalationSeverity.MEDIUM,
        EscalationSeverity.HIGH,
        EscalationSeverity.CRITICAL,
    ]
    assert zero_stock is not None
    assert partial_stock is not None
    assert severity_order.index(partial_stock) < severity_order.index(zero_stock)


def test_stock_above_scarcity_threshold_is_not_an_alert() -> None:
    severity = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=10,
        facilities_with_stock_count=6,
        facility_density=10,
    )
    assert severity is None


def test_non_priority_commodity_is_lower_severity_than_priority() -> None:
    priority = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
        facility_density=10,
    )
    non_priority = classify_severity(
        is_priority_watchlist=False,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
        facility_density=10,
    )
    severity_order = [
        EscalationSeverity.LOW,
        EscalationSeverity.MEDIUM,
        EscalationSeverity.HIGH,
        EscalationSeverity.CRITICAL,
    ]
    assert priority is not None
    assert non_priority is not None
    assert severity_order.index(non_priority) < severity_order.index(priority)


def test_zero_facilities_checked_is_not_an_alert() -> None:
    severity = classify_severity(
        is_priority_watchlist=True,
        facilities_checked_count=0,
        facilities_with_stock_count=0,
        facility_density=10,
    )
    assert severity is None
