from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any
from app.core.database import get_db
from app.models.settings import AppSettings

router = APIRouter()

# Default values — used if not set in DB yet
DEFAULTS = {
    "poll_interval_seconds": {
        "value": "30",
        "description": "How often to poll Polymarket for new data (seconds). Min 10, Max 300.",
    },
    "signal_threshold_pct": {
        "value": "5.0",
        "description": "Minimum probability shift % to flag as a signal on the dashboard.",
    },
    "max_trade_size_usd": {
        "value": "1000",
        "description": "Maximum dollar value of any single trade. Prevents oversized positions.",
    },
    "max_open_positions": {
        "value": "10",
        "description": "Maximum number of open positions at one time.",
    },
    "cooldown_minutes": {
        "value": "60",
        "description": "Minutes to wait before the same rule can fire again on the same ticker.",
    },
    "paper_trading": {
        "value": "true",
        "description": "Run in paper trading mode (no real money). Set to false for live trading.",
    },
    "markets_limit": {
        "value": "50",
        "description": "Number of Polymarket markets to fetch and watch per poll.",
    },
    "notifications_enabled": {
        "value": "false",
        "description": "Enable browser notifications when signals fire or trades execute.",
    },
}


def get_setting(key: str, db: Session) -> str:
    """Get a setting value from DB, falling back to default."""
    row = db.query(AppSettings).filter(AppSettings.key == key).first()
    if row:
        return row.value
    return DEFAULTS.get(key, {}).get("value", "")


def get_all_settings(db: Session) -> dict:
    """Get all settings merged with defaults."""
    db_settings = {
        s.key: s.value
        for s in db.query(AppSettings).all()
    }
    result = {}
    for key, meta in DEFAULTS.items():
        result[key] = {
            "value": db_settings.get(key, meta["value"]),
            "description": meta["description"],
            "is_default": key not in db_settings,
        }
    return result


class SettingUpdate(BaseModel):
    value: Any


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.patch("/settings/{key}")
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    if key not in DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unknown setting: {key}")

    value = str(body.value)

    # Validate ranges
    if key == "poll_interval_seconds":
        v = int(value)
        if v < 10 or v > 300:
            raise HTTPException(400, "Poll interval must be between 10 and 300 seconds")
    elif key == "signal_threshold_pct":
        v = float(value)
        if v < 0.1 or v > 50:
            raise HTTPException(400, "Signal threshold must be between 0.1% and 50%")
    elif key == "max_trade_size_usd":
        v = float(value)
        if v < 1:
            raise HTTPException(400, "Max trade size must be at least $1")
    elif key == "max_open_positions":
        v = int(value)
        if v < 1 or v > 100:
            raise HTTPException(400, "Max open positions must be between 1 and 100")
    elif key == "cooldown_minutes":
        v = int(value)
        if v < 1 or v > 1440:
            raise HTTPException(400, "Cooldown must be between 1 and 1440 minutes")
    elif key == "markets_limit":
        v = int(value)
        if v < 10 or v > 500:
            raise HTTPException(400, "Markets limit must be between 10 and 500")

    row = db.query(AppSettings).filter(AppSettings.key == key).first()
    if row:
        row.value = value
    else:
        db.add(AppSettings(key=key, value=value, description=DEFAULTS[key]["description"]))
    db.commit()

    print(f"⚙️  Setting updated: {key} = {value}")
    return {"key": key, "value": value, "message": "Setting saved"}


@router.post("/settings/reset")
def reset_settings(db: Session = Depends(get_db)):
    """Reset all settings to defaults."""
    db.query(AppSettings).delete()
    db.commit()
    return {"message": "All settings reset to defaults"}