from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx
from datetime import datetime, timedelta
from app.core.config import settings

router = APIRouter()

GAMMA_BASE = "https://gamma-api.polymarket.com"


async def _fetch_history_for_market(market: dict, start: str, end: str) -> list[dict]:
    market_id = str(market.get("id", ""))

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{GAMMA_BASE}/markets/{market_id}/prices-history",
            params={"interval": "1d", "startTs": start, "endTs": end},
        )
        print(f"Prices history status: {r.status_code} — {r.text[:200]}")
        if r.status_code != 200:
            return _synthesize_history(market, start, end)
        data = r.json()

    history = data.get("history", data if isinstance(data, list) else [])
    print(f"Got {len(history)} probability points")

    result = []
    for point in history:
        ts = point.get("t") or point.get("timestamp")
        price = point.get("p") or point.get("price")
        if ts and price is not None:
            try:
                result.append({
                    "date": datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d"),
                    "probability": round(float(price) * 100, 2),
                    "market_question": market.get("question") or market.get("title"),
                })
            except Exception:
                pass

    if not result:
        print("No history points — using synthesized history")
        return _synthesize_history(market, start, end)

    return result


async def fetch_polymarket_history(keyword: str, start: str, end: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Use the search endpoint instead of sorting by volume
            r = await client.get(
                f"{GAMMA_BASE}/markets/keyset",
                params={
                    "limit": 100,
                    "order": "volume24hr",
                    "ascending": "false",
                    "active": "true",
                },
            )
            r.raise_for_status()
            all_markets = r.json().get("markets", [])

        print(f"Gamma returned {len(all_markets)} markets")

        # Search across question, title, description, and slug
        keywords = keyword.lower().split()
        matched = []
        for m in all_markets:
            searchable = " ".join([
                m.get("question") or "",
                m.get("title") or "",
                m.get("description") or "",
                m.get("slug") or "",
            ]).lower()
            if any(kw in searchable for kw in keywords):
                matched.append(m)

        print(f"Matched {len(matched)} markets for keyword '{keyword}'")

        if not matched:
            raise Exception(f"No markets found matching '{keyword}'")

        market = matched[0]
        print(f"Using market: {market.get('question') or market.get('title')}")

        return await _fetch_history_for_market(market, start, end)

    except Exception as e:
        print(f"Polymarket history fetch error: {e}")
        return []


async def fetch_polymarket_history_by_id(market_id: str, start: str, end: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{GAMMA_BASE}/markets/{market_id}")
            r.raise_for_status()
            market = r.json()

        return await _fetch_history_for_market(market, start, end)

    except Exception as e:
        print(f"Polymarket history-by-id fetch error: {e}")
        return []


def _synthesize_history(market: dict, start: str, end: str) -> list[dict]:
    try:
        import json
        prices = market.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        prob = round(float(prices[0]) * 100, 2) if prices else 50.0
    except Exception:
        prob = 50.0

    question = market.get("question") or market.get("title", "Unknown")
    start_dt = datetime.strptime(start[:10], "%Y-%m-%d")
    end_dt = datetime.strptime(end[:10], "%Y-%m-%d")
    result = []
    current = start_dt
    while current <= end_dt:
        result.append({
            "date": current.strftime("%Y-%m-%d"),
            "probability": prob,
            "market_question": question,
        })
        current += timedelta(days=1)
    return result


async def fetch_stock_history(ticker: str, start: str, end: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"https://data.alpaca.markets/v2/stocks/{ticker.upper()}/bars",
                headers={
                    "APCA-API-KEY-ID": settings.alpaca_api_key,
                    "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
                },
                params={
                    "timeframe": "1Day",
                    "start": start[:10],
                    "end": end[:10],
                    "limit": 1000,
                    "feed": "iex",
                },
            )
            print(f"Alpaca data response: {r.status_code}")
            if r.status_code != 200:
                print(f"Alpaca error: {r.text}")
                return []

            data = r.json()
            bars = data.get("bars", [])
            result = []
            for bar in bars:
                try:
                    result.append({
                        "date": bar["t"][:10],
                        "close": round(float(bar["c"]), 2),
                        "open": round(float(bar["o"]), 2),
                        "high": round(float(bar["h"]), 2),
                        "low": round(float(bar["l"]), 2),
                    })
                except Exception as e:
                    print(f"Bar parse error: {e}")
                    continue

            print(f"Got {len(result)} bars for {ticker}")
            return result

    except Exception as e:
        print(f"Stock history fetch error: {e}")
        return []


def simulate_backtest(
    prob_series: list[dict],
    price_series: list[dict],
    threshold: float,
    action: str,
    qty: float = 1.0,
) -> dict:
    price_by_date = {p["date"]: p for p in price_series}

    trades = []
    chart_data = []
    position = None
    prev_prob = None
    realized_pnl = []

    for point in prob_series:
        date = point["date"]
        prob = point["probability"]
        price_bar = price_by_date.get(date)

        if not price_bar:
            prev_prob = prob
            continue

        close = price_bar["close"]
        crossed_above = prev_prob is not None and prev_prob < threshold and prob >= threshold
        crossed_below = prev_prob is not None and prev_prob >= threshold and prob < threshold

        trade_marker = None

        if action == "buy":
            if crossed_above and position is None:
                position = {"entry_price": close, "entry_date": date}
                trade_marker = {
                    "date": date, "type": "BUY", "price": close,
                    "probability": prob, "market_question": point.get("market_question"),
                }
                trades.append(trade_marker)
            elif crossed_below and position is not None:
                pnl = round((close - position["entry_price"]) * qty, 2)
                realized_pnl.append(pnl)
                trade_marker = {
                    "date": date, "type": "SELL (close)", "price": close,
                    "probability": prob, "pnl": pnl,
                    "entry_price": position["entry_price"],
                    "market_question": point.get("market_question"),
                }
                trades.append(trade_marker)
                position = None

        elif action == "sell":
            if crossed_above and position is None:
                position = {"entry_price": close, "entry_date": date}
                trade_marker = {
                    "date": date, "type": "SELL (short)", "price": close,
                    "probability": prob, "market_question": point.get("market_question"),
                }
                trades.append(trade_marker)
            elif crossed_below and position is not None:
                pnl = round((position["entry_price"] - close) * qty, 2)
                realized_pnl.append(pnl)
                trade_marker = {
                    "date": date, "type": "BUY (cover)", "price": close,
                    "probability": prob, "pnl": pnl,
                    "entry_price": position["entry_price"],
                    "market_question": point.get("market_question"),
                }
                trades.append(trade_marker)
                position = None

        chart_data.append({
            "date": date, "price": close, "probability": prob,
            "trade": trade_marker, "in_position": position is not None,
        })

        prev_prob = prob

    if position and price_series:
        last = price_series[-1]
        pnl = round((last["close"] - position["entry_price"]) * qty, 2) if action == "buy" \
              else round((position["entry_price"] - last["close"]) * qty, 2)
        realized_pnl.append(pnl)
        trades.append({
            "date": last["date"], "type": "CLOSE (end of period)",
            "price": last["close"], "pnl": pnl,
            "entry_price": position["entry_price"],
        })

    total_pnl = round(sum(realized_pnl), 2)
    wins = [p for p in realized_pnl if p > 0]
    losses = [p for p in realized_pnl if p <= 0]
    win_rate = round(len(wins) / len(realized_pnl) * 100, 1) if realized_pnl else 0

    return {
        "trades": trades,
        "chart_data": chart_data,
        "summary": {
            "total_trades": len([t for t in trades if t["type"] in ("BUY", "SELL (short)")]),
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "wins": len(wins),
            "losses": len(losses),
            "best_trade": max(realized_pnl) if realized_pnl else 0,
            "worst_trade": min(realized_pnl) if realized_pnl else 0,
            "avg_trade": round(sum(realized_pnl) / len(realized_pnl), 2) if realized_pnl else 0,
        },
    }


@router.get("/backtest")
async def run_backtest(
    keyword: Optional[str] = Query(None),
    market_id: Optional[str] = Query(None),
    threshold: float = Query(60.0),
    ticker: str = Query("SPY"),
    action: str = Query("buy"),
    start: str = Query(...),
    end: str = Query(...),
    qty: float = Query(1.0),
):
    if not keyword and not market_id:
        raise HTTPException(400, "Provide either keyword or market_id")
    if action not in ("buy", "sell"):
        raise HTTPException(400, "action must be buy or sell")

    import asyncio
    prob_series, price_series = await asyncio.gather(
        fetch_polymarket_history_by_id(market_id, start, end) if market_id
        else fetch_polymarket_history(keyword, start, end),
        fetch_stock_history(ticker, start, end),
    )

    if not price_series:
        raise HTTPException(404, f"No price data found for {ticker} in that date range")
    if not prob_series:
        raise HTTPException(404, f"No Polymarket market found for '{market_id or keyword}'")

    result = simulate_backtest(prob_series, price_series, threshold, action, qty)

    return {
        **result,
        "meta": {
            "keyword": keyword,
            "market_id": market_id,
            "ticker": ticker.upper(),
            "threshold": threshold,
            "action": action,
            "start": start,
            "end": end,
            "qty": qty,
            "market_question": prob_series[0].get("market_question") if prob_series else None,
            "prob_points": len(prob_series),
            "price_points": len(price_series),
        },
    }