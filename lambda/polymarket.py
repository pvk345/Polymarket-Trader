import json
import httpx

GAMMA_BASE = "https://gamma-api.polymarket.com"


def fetch_markets_raw(limit: int) -> list:
    """Fetch up to `limit` active markets, sorted by 24hr volume, paginating
    via cursor since a single request caps at 100. No caching — each Lambda
    invocation is infrequent enough that a fresh fetch every time is fine."""
    markets_raw: list = []
    cursor = None
    with httpx.Client(timeout=15) as client:
        while len(markets_raw) < limit:
            params = {
                "limit": min(100, limit - len(markets_raw)),
                "active": "true",
                "closed": "false",
                "order": "volume24hr",
                "ascending": "false",
            }
            if cursor:
                params["after_cursor"] = cursor
            resp = client.get(f"{GAMMA_BASE}/markets/keyset", params=params)
            resp.raise_for_status()
            data = resp.json()
            page = data.get("markets", [])
            if not page:
                break
            markets_raw.extend(page)
            cursor = data.get("next_cursor")
            if not cursor:
                break
    return markets_raw


def fetch_specific_markets(ids: set) -> list:
    """Fetch individual markets by ID — for rule-pinned markets that fell
    outside the top-N-by-volume batch."""
    results = []
    with httpx.Client(timeout=15) as client:
        for market_id in ids:
            try:
                resp = client.get(f"{GAMMA_BASE}/markets/{market_id}")
                resp.raise_for_status()
                results.append(resp.json())
            except Exception as e:
                print(f"WARNING: could not top-up pinned rule market {market_id}: {e}")
    return results


def extract_probability(market: dict):
    try:
        prices = market.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        if prices and len(prices) > 0:
            return round(float(prices[0]) * 100, 1)
    except Exception:
        pass
    best_bid = market.get("bestBid")
    best_ask = market.get("bestAsk")
    if best_bid and best_ask:
        try:
            mid = (float(best_bid) + float(best_ask)) / 2
            return round(mid * 100, 1)
        except Exception:
            pass
    return None


def enrich_markets(markets_raw: list) -> list:
    """Trim raw Polymarket objects down to just id/question/probability,
    filtering out closed/archived/degenerate (0% or 100%) markets."""
    enriched = []
    for m in markets_raw:
        if m.get("closed") or m.get("archived"):
            continue
        market_id = str(m.get("id", ""))
        question = m.get("question") or m.get("title", "Unknown market")
        prob = extract_probability(m)
        if prob is None or prob <= 0 or prob >= 100:
            continue
        enriched.append({"id": market_id, "question": question, "probability": prob})
    return enriched
