from sqlalchemy.orm import Session
from models import AppSettings

DEFAULTS = {
    "poll_interval_seconds": {"value": "30"},
    "signal_threshold_pct": {"value": "5.0"},
    "max_trade_size_usd": {"value": "1000"},
    "max_open_positions": {"value": "10"},
    "cooldown_minutes": {"value": "60"},
    "paper_trading": {"value": "true"},
    "markets_limit": {"value": "500"},
    "notifications_enabled": {"value": "false"},
}


def get_setting(key: str, db: Session) -> str:
    row = db.query(AppSettings).filter(AppSettings.key == key).first()
    if row:
        return row.value
    return DEFAULTS.get(key, {}).get("value", "")
