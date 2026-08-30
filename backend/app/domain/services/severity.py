from app.domain.enums import EscalationSeverity

_SCARCITY_THRESHOLD = 0.5

_SPARSE_DENSITY = 3


def classify_severity(
    is_priority_watchlist: bool,
    facilities_checked_count: int,
    facilities_with_stock_count: int,
    facility_density: int,
) -> EscalationSeverity | None:
    if facilities_checked_count == 0:
        return None

    pct_in_stock = facilities_with_stock_count / facilities_checked_count
    if pct_in_stock >= _SCARCITY_THRESHOLD:
        return None

    sparse = facility_density <= _SPARSE_DENSITY

    if pct_in_stock == 0.0:
        if is_priority_watchlist:
            return EscalationSeverity.CRITICAL if sparse else EscalationSeverity.HIGH
        return EscalationSeverity.HIGH if sparse else EscalationSeverity.MEDIUM

    if is_priority_watchlist:
        return EscalationSeverity.HIGH if sparse else EscalationSeverity.MEDIUM

    return EscalationSeverity.MEDIUM if sparse else EscalationSeverity.LOW
