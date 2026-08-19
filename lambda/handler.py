import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Rule
from settings import get_setting
from polymarket import fetch_markets_raw, fetch_specific_markets, enrich_markets
from rule_evaluator import evaluate_rules
from watchlist_checker import check_watchlist_alerts

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _get_active_rule_market_ids(db) -> set:
    rows = (
        db.query(Rule.market_id, Rule.market_ids)
        .filter(Rule.active == True)
        .filter((Rule.market_id.isnot(None)) | (Rule.market_ids.isnot(None)))
        .all()
    )
    ids = set()
    for market_id, market_ids_json in rows:
        if market_id:
            ids.add(str(market_id))
        if market_ids_json:
            try:
                for x in json.loads(market_ids_json):
                    ids.add(str(x["id"]))
            except Exception:
                pass
    return ids


def handler(event, context):
    db = SessionLocal()
    try:
        markets_limit = int(get_setting("markets_limit", db))

        markets_raw = fetch_markets_raw(markets_limit)
        print(f"Fetched {len(markets_raw)} markets from Polymarket")

        rule_market_ids = _get_active_rule_market_ids(db)
        if rule_market_ids:
            present_ids = {str(m.get("id", "")) for m in markets_raw}
            missing_ids = rule_market_ids - present_ids
            if missing_ids:
                topped_up = fetch_specific_markets(missing_ids)
                if topped_up:
                    print(f"Topped up {len(topped_up)} rule-pinned market(s) outside top {markets_limit}")
                markets_raw = markets_raw + topped_up

        enriched = enrich_markets(markets_raw)
        triggers = evaluate_rules(enriched, db)

        watchlist_alerts = check_watchlist_alerts(db)

        result = {
            "markets_evaluated": len(enriched),
            "triggers": len(triggers),
            "trigger_details": triggers,
            "watchlist_alerts": len(watchlist_alerts),
            "watchlist_alert_details": watchlist_alerts,
        }
        print(json.dumps(result, default=str))
        return result
    finally:
        db.close()
