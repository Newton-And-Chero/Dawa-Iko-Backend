from uuid import uuid4

from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber
from app.domain.enums import EscalationSeverity, NotificationChannel
from app.domain.services.subscriber_matching import match_subscribers


def _alert(*, commodity_id, geography) -> StockoutAlert:
    return StockoutAlert(
        commodity_id=commodity_id,
        geography=geography,
        severity=EscalationSeverity.HIGH,
        facilities_checked_count=10,
        facilities_with_stock_count=0,
    )


def test_subscriber_watching_commodity_and_exact_geography_matches() -> None:
    commodity_id = uuid4()
    geography = {"kind": "county", "county": "Kirinyaga"}
    alert = _alert(commodity_id=commodity_id, geography=geography)
    subscriber = Subscriber(
        name="County Pharmacist",
        notification_channel=NotificationChannel.SMS,
        phone="+254700000001",
        watchlist_commodities=[commodity_id],
        watchlist_geography=geography,
    )

    assert match_subscribers(alert, [subscriber]) == [subscriber]


def test_subscriber_not_watching_commodity_does_not_match() -> None:
    geography = {"kind": "county", "county": "Kirinyaga"}
    alert = _alert(commodity_id=uuid4(), geography=geography)
    subscriber = Subscriber(
        name="County Pharmacist",
        notification_channel=NotificationChannel.SMS,
        phone="+254700000001",
        watchlist_commodities=[uuid4()],
        watchlist_geography=geography,
    )

    assert match_subscribers(alert, [subscriber]) == []


def test_subscriber_watching_different_geography_does_not_match() -> None:
    commodity_id = uuid4()
    alert = _alert(commodity_id=commodity_id, geography={"kind": "county", "county": "Kirinyaga"})
    subscriber = Subscriber(
        name="County Pharmacist",
        notification_channel=NotificationChannel.SMS,
        phone="+254700000001",
        watchlist_commodities=[commodity_id],
        watchlist_geography={"kind": "county", "county": "Nairobi"},
    )

    assert match_subscribers(alert, [subscriber]) == []


def test_subscriber_with_empty_geography_watches_everywhere() -> None:
    commodity_id = uuid4()
    alert = _alert(commodity_id=commodity_id, geography={"kind": "ward", "ward": "Wamumu"})
    subscriber = Subscriber(
        name="NGO Partner",
        notification_channel=NotificationChannel.EMAIL,
        email="partner@example.org",
        watchlist_commodities=[commodity_id],
        watchlist_geography={},
    )

    assert match_subscribers(alert, [subscriber]) == [subscriber]
