from app.domain.entities.stockout_alert import StockoutAlert
from app.domain.entities.subscriber import Subscriber


def match_subscribers(alert: StockoutAlert, subscribers: list[Subscriber]) -> list[Subscriber]:
    return [s for s in subscribers if _watches(s, alert)]


def _watches(subscriber: Subscriber, alert: StockoutAlert) -> bool:
    if alert.commodity_id not in subscriber.watchlist_commodities:
        return False
    return not subscriber.watchlist_geography or subscriber.watchlist_geography == alert.geography
