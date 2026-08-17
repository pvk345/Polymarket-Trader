from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.models.watchlist import WatchlistItem

router = APIRouter()


class WatchlistCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=20)
    label: Optional[str] = None
    alert_above: Optional[float] = None
    alert_below: Optional[float] = None
    notes: Optional[str] = None


def _get_price(ticker: str) -> float | None:
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestTradeRequest, StockLatestQuoteRequest
        from app.core.config import settings

        client = StockHistoricalDataClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
        )

        # Try latest trade price first — most reliable, not affected by zero bid/ask after hours
        try:
            trade_req = StockLatestTradeRequest(symbol_or_symbols=ticker)
            trade = client.get_stock_latest_trade(trade_req)
            if ticker in trade and trade[ticker].price:
                return float(trade[ticker].price)
        except Exception:
            pass

        # Fall back to mid-quote but only if both bid and ask are non-zero
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
        # Final fallback to yfinance
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="1d", interval="1m")
            if not hist.empty:
                return float(hist["Close"].iloc[-1])
            return None
        except Exception:
            return None


@router.get("/watchlist")
def get_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc()).all()
    return {
        "items": [
            {
                "id": i.id,
                "ticker": i.ticker,
                "label": i.label,
                "alert_above": i.alert_above,
                "alert_below": i.alert_below,
                "active": i.active,
                "last_price": i.last_price,
                "last_checked": (i.last_checked.isoformat() + "Z") if i.last_checked else None,
                "created_at": (i.created_at.isoformat() + "Z") if i.created_at else None,
                "alert_triggered": i.alert_triggered or False,
                "alert_triggered_at": (i.alert_triggered_at.isoformat() + "Z") if i.alert_triggered_at else None,
                "notes": i.notes,
            }
            for i in items
        ]
    }


@router.post("/watchlist")
def add_to_watchlist(item: WatchlistCreate, db: Session = Depends(get_db)):
    price = _get_price(item.ticker.upper())

    db_item = WatchlistItem(
        ticker=item.ticker.upper(),
        label=item.label or item.ticker.upper(),
        alert_above=item.alert_above,
        alert_below=item.alert_below,
        notes=item.notes,
        active=True,
        last_price=price,
        last_checked=datetime.utcnow() if price else None,
        alert_triggered=False,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    print(f"✅ Watchlist: added {db_item.ticker} @ ${price:.2f}" if price else f"✅ Watchlist: added {db_item.ticker} (price unavailable)")
    return {"message": "Added to watchlist", "id": db_item.id, "current_price": price}


@router.delete("/watchlist/{item_id}")
def remove_from_watchlist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return {"message": "Removed from watchlist"}


@router.patch("/watchlist/{item_id}/reset-alert")
def reset_alert(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    item.alert_triggered = False
    item.alert_triggered_at = None
    db.commit()
    return {"message": "Alert reset"}


@router.post("/watchlist/refresh")
def refresh_prices(db: Session = Depends(get_db)):
    """Fetch latest prices for all watchlist items and check alert thresholds."""
    items = db.query(WatchlistItem).filter(WatchlistItem.active == True).all()
    alerts_fired = []

    for item in items:
        price = _get_price(item.ticker)
        if price is None:
            continue

        item.last_price = price
        item.last_checked = datetime.utcnow()

        if not item.alert_triggered:
            if item.alert_above is not None and price >= item.alert_above:
                item.alert_triggered = True
                item.alert_triggered_at = datetime.utcnow()
                alerts_fired.append({
                    "ticker": item.ticker,
                    "label": item.label,
                    "price": price,
                    "trigger": "above",
                    "threshold": item.alert_above,
                })
                print(f"🔔 PRICE ALERT: {item.ticker} hit ${price:.2f} (above ${item.alert_above:.2f})", flush=True)

            elif item.alert_below is not None and price <= item.alert_below:
                item.alert_triggered = True
                item.alert_triggered_at = datetime.utcnow()
                alerts_fired.append({
                    "ticker": item.ticker,
                    "label": item.label,
                    "price": price,
                    "trigger": "below",
                    "threshold": item.alert_below,
                })
                print(f"🔔 PRICE ALERT: {item.ticker} hit ${price:.2f} (below ${item.alert_below:.2f})", flush=True)

    db.commit()
    return {
        "refreshed": len(items),
        "alerts_fired": alerts_fired,
    }