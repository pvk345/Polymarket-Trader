"""
Watchlist alert checking — ported from backend/app/api/watchlist.py's
refresh_prices endpoint, so it runs on the Lambda's own schedule (once a
minute via EventBridge) instead of only when someone has the /watchlist
page open in a browser. Previously nothing covered this gap at all — not
even the backend had independent scheduling for it.
"""

import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from models import WatchlistItem

ALPACA_API_KEY = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]


def _get_price(ticker: str):
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest

        client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

        try:
            trade_req = StockLatestTradeRequest(symbol_or_symbols=ticker)
            trade = client.get_stock_latest_trade(trade_req)
            if ticker in trade and trade[ticker].price:
                return float(trade[ticker].price)
        except Exception:
            pass

        try:
            quote_req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
            quote = client.get_stock_latest_quote(quote_req)
            if ticker in quote:
                q = quote[ticker]
                bid = float(q.bid_price or 0)
                ask = float(q.ask_price or 0)
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
                elif ask > 0:
                    return ask
                elif bid > 0:
                    return bid
        except Exception:
            pass

        return None

    except Exception:
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return None
        except Exception:
            return None


def check_watchlist_alerts(db: Session) -> list[dict]:
    """Fetch latest prices for all active watchlist items, concurrently, and
    fire any alerts whose threshold has been crossed. Returns the list of
    alerts fired this run."""
    items = db.query(WatchlistItem).filter(WatchlistItem.active == True).all()
    alerts_fired = []

    if not items:
        return alerts_fired

    with ThreadPoolExecutor(max_workers=min(len(items), 10)) as executor:
        prices = list(executor.map(_get_price, [item.ticker for item in items]))

    for item, price in zip(items, prices):
        if price is None:
            continue

        item.last_price = price
        item.last_checked = datetime.utcnow()

        if not item.alert_triggered:
            if item.alert_above is not None and price >= item.alert_above:
                item.alert_triggered = True
                item.alert_triggered_at = datetime.utcnow()
                alerts_fired.append({
                    "ticker": item.ticker, "label": item.label, "price": price,
                    "trigger": "above", "threshold": item.alert_above,
                })
            elif item.alert_below is not None and price <= item.alert_below:
                item.alert_triggered = True
                item.alert_triggered_at = datetime.utcnow()
                alerts_fired.append({
                    "ticker": item.ticker, "label": item.label, "price": price,
                    "trigger": "below", "threshold": item.alert_below,
                })

    db.commit()
    return alerts_fired
