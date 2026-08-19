from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field
from typing import Optional, List
import json
from app.core.database import get_db
from app.models.rules import Rule, TriggerLog
from app.api.auth import get_current_user_id

router = APIRouter()


class MarketRef(BaseModel):
    id: str
    question: Optional[str] = None


class MarketCondition(BaseModel):
    id: str
    question: Optional[str] = None
    condition: str = Field(..., pattern="^(above|below)$")
    threshold: float = Field(..., ge=0, le=100)


class RuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    keyword: Optional[str] = Field(None, max_length=200)
    market_id: Optional[str] = Field(None, max_length=50)
    market_question: Optional[str] = None
    # ALL entries must be simultaneously true for the rule to fire — each carries its own condition+threshold
    market_ids: Optional[List[MarketCondition]] = None
    condition: Optional[str] = Field(None, pattern="^(above|below)$")
    threshold: Optional[float] = Field(None, ge=0, le=100)
    action: str = Field(..., pattern="^(buy|sell)$")
    ticker: str = Field(..., min_length=1, max_length=20)
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = None
    exit_condition: Optional[str] = None
    exit_threshold: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_quantity: Optional[float] = None
    use_dynamic_sizing: bool = False


@router.get("/rules")
def get_rules(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rules = (
        db.query(Rule)
        .filter(or_(Rule.user_id == user_id, Rule.user_id.is_(None)))
        .order_by(Rule.created_at.desc())
        .all()
    )
    return {
        "rules": [
            {
                "id": r.id,
                "owned_by_me": r.user_id == user_id,
                "name": r.name,
                "keyword": r.keyword,
                "market_id": r.market_id,
                "market_question": r.market_question,
                "market_ids": json.loads(r.market_ids) if r.market_ids else None,
                "condition": r.condition,
                "threshold": r.threshold,
                "action": r.action,
                "ticker": r.ticker,
                "quantity": r.quantity,
                "max_quantity": r.max_quantity,
                "use_dynamic_sizing": r.use_dynamic_sizing or False,
                "active": r.active,
                "triggered_count": r.triggered_count or 0,
                "last_triggered": (r.last_triggered.isoformat() + "Z") if r.last_triggered else None,
                "created_at": (r.created_at.isoformat() + "Z") if r.created_at else None,
                "notes": r.notes,
                "exit_condition": r.exit_condition,
                "exit_threshold": r.exit_threshold,
                "take_profit_pct": r.take_profit_pct,
                "stop_loss_pct": r.stop_loss_pct,
                "in_position": r.in_position or False,
                "entry_price": r.entry_price,
                "entry_date": (r.entry_date.isoformat() + "Z") if r.entry_date else None,
                "actual_quantity": r.actual_quantity,
            }
            for r in rules
        ],
        "count": len(rules),
    }


@router.get("/rules/performance")
def get_rule_performance(db: Session = Depends(get_db)):
    """Compute per-rule P&L by matching entry/exit TriggerLog pairs against Alpaca fills."""

    # Fetch all Alpaca orders once
    order_map = {}
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        from app.core.config import settings

        client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=True)
        orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))
        order_map = {str(o.id): o for o in orders}
    except Exception as e:
        print(f"Warning: could not fetch Alpaca orders for performance: {e}")

    # Get all executed logs grouped by rule_id
    logs = (
        db.query(TriggerLog)
        .filter(TriggerLog.executed == True)
        .order_by(TriggerLog.triggered_at.asc())
        .all()
    )

    # Group logs by rule_id
    by_rule: dict[int, list] = {}
    for log in logs:
        by_rule.setdefault(log.rule_id, []).append(log)

    # Get all rules for names/metadata
    rules = {r.id: r for r in db.query(Rule).all()}

    performance = []
    for rule_id, rule_logs in by_rule.items():
        rule = rules.get(rule_id)
        rule_name = rule.name if rule else rule_logs[0].rule_name
        ticker = rule_logs[0].ticker

        entries = [l for l in rule_logs if l.log_type == "entry"]
        exits = [l for l in rule_logs if l.log_type == "exit"]

        total_pnl = 0.0
        wins = 0
        losses = 0
        trade_count = 0
        trades = []

        # Match entries to exits in order
        for i, entry in enumerate(entries):
            entry_order = order_map.get(entry.alpaca_order_id)
            if not entry_order or not entry_order.filled_avg_price:
                continue
            entry_price = float(entry_order.filled_avg_price)
            entry_qty = float(entry_order.filled_qty or entry.sized_quantity or entry.quantity)

            # Find matching exit (same index if available)
            exit_log = exits[i] if i < len(exits) else None
            exit_order = order_map.get(exit_log.alpaca_order_id) if exit_log else None

            if exit_order and exit_order.filled_avg_price:
                exit_price = float(exit_order.filled_avg_price)
                exit_qty = float(exit_order.filled_qty or exit_log.sized_quantity or entry_qty)

                if entry.action == "buy":
                    pnl = (exit_price - entry_price) * min(entry_qty, exit_qty)
                else:
                    pnl = (entry_price - exit_price) * min(entry_qty, exit_qty)

                total_pnl += pnl
                trade_count += 1
                if pnl >= 0:
                    wins += 1
                else:
                    losses += 1

                trades.append({
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "qty": min(entry_qty, exit_qty),
                    "pnl": round(pnl, 2),
                    "entry_time": (entry.triggered_at.isoformat() + "Z") if entry.triggered_at else None,
                    "exit_time": (exit_log.triggered_at.isoformat() + "Z") if exit_log and exit_log.triggered_at else None,
                })
            else:
                # Open position — mark as unrealized
                trades.append({
                    "entry_price": entry_price,
                    "exit_price": None,
                    "qty": entry_qty,
                    "pnl": None,
                    "entry_time": (entry.triggered_at.isoformat() + "Z") if entry.triggered_at else None,
                    "exit_time": None,
                    "open": True,
                })

        performance.append({
            "rule_id": rule_id,
            "rule_name": rule_name,
            "ticker": ticker,
            "active": rule.active if rule else False,
            "in_position": rule.in_position if rule else False,
            "total_pnl": round(total_pnl, 2),
            "trade_count": trade_count,
            "open_trades": len(entries) - len(exits),
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / trade_count * 100) if trade_count > 0 else 0, 1),
            "avg_pnl": round(total_pnl / trade_count if trade_count > 0 else 0, 2),
            "trades": trades,
        })

    # Sort by total P&L descending
    performance.sort(key=lambda x: x["total_pnl"], reverse=True)
    return {"performance": performance}


def _validate_rule_payload(rule: RuleCreate):
    if not rule.keyword and not rule.market_id and not rule.market_ids:
        raise HTTPException(status_code=400, detail="Provide a keyword, a market_id, or market_ids")
    if not rule.market_ids and (rule.condition is None or rule.threshold is None):
        raise HTTPException(status_code=400, detail="condition and threshold are required unless using market_ids")
    if rule.market_ids and len(rule.market_ids) < 1:
        raise HTTPException(status_code=400, detail="market_ids must include at least one market")


@router.post("/rules")
def create_rule(rule: RuleCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    _validate_rule_payload(rule)

    # Dynamic sizing scales against a single threshold — meaningless (and unsafe) for
    # an AND-multi-market rule where there isn't one probability to scale against.
    use_dynamic_sizing = rule.use_dynamic_sizing and not rule.market_ids

    db_rule = Rule(
        user_id=user_id,
        name=rule.name,
        keyword=rule.keyword,
        market_id=rule.market_id,
        market_question=rule.market_question,
        market_ids=json.dumps([m.dict() for m in rule.market_ids]) if rule.market_ids else None,
        condition=rule.condition,
        threshold=rule.threshold,
        action=rule.action,
        ticker=rule.ticker.upper(),
        quantity=rule.quantity,
        notes=rule.notes,
        active=True,
        triggered_count=0,
        in_position=False,
        exit_condition=rule.exit_condition,
        exit_threshold=rule.exit_threshold,
        take_profit_pct=rule.take_profit_pct,
        stop_loss_pct=rule.stop_loss_pct,
        max_quantity=rule.max_quantity if use_dynamic_sizing else None,
        use_dynamic_sizing=use_dynamic_sizing,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    print(f"✅ Rule created: [{db_rule.name}] sizing={'dynamic' if rule.use_dynamic_sizing else 'fixed'}")
    return {"message": "Rule created", "id": db_rule.id}


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, rule: RuleCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    db_rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if db_rule.user_id is not None and db_rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this rule")

    _validate_rule_payload(rule)
    use_dynamic_sizing = rule.use_dynamic_sizing and not rule.market_ids

    db_rule.name = rule.name
    db_rule.keyword = rule.keyword
    db_rule.market_id = rule.market_id
    db_rule.market_question = rule.market_question
    db_rule.market_ids = json.dumps([m.dict() for m in rule.market_ids]) if rule.market_ids else None
    db_rule.condition = rule.condition
    db_rule.threshold = rule.threshold
    db_rule.action = rule.action
    db_rule.ticker = rule.ticker.upper()
    db_rule.quantity = rule.quantity
    db_rule.notes = rule.notes
    db_rule.exit_condition = rule.exit_condition
    db_rule.exit_threshold = rule.exit_threshold
    db_rule.take_profit_pct = rule.take_profit_pct
    db_rule.stop_loss_pct = rule.stop_loss_pct
    db_rule.max_quantity = rule.max_quantity if use_dynamic_sizing else None
    db_rule.use_dynamic_sizing = use_dynamic_sizing

    db.commit()
    print(f"✏️  Rule updated: [{db_rule.name}]")
    return {"message": "Rule updated", "id": db_rule.id}


@router.get("/rules/preview-size")
def preview_size(
    probability: float,
    threshold: float,
    min_qty: float,
    max_qty: float,
):
    from app.services.position_sizer import calculate_position_size, confidence_label
    sized = calculate_position_size(probability, threshold, min_qty, max_qty)
    return {
        "probability": probability,
        "threshold": threshold,
        "min_qty": min_qty,
        "max_qty": max_qty,
        "sized_quantity": sized,
        "confidence": confidence_label(probability, threshold),
    }


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.user_id is not None and rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to delete this rule")
    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


@router.patch("/rules/{rule_id}/toggle")
def toggle_rule(rule_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.user_id is not None and rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="You don't have permission to modify this rule")
    rule.active = not rule.active
    db.commit()
    return {"message": f"Rule {'activated' if rule.active else 'paused'}", "active": rule.active}


@router.get("/rules/logs")
def get_trigger_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(TriggerLog).order_by(TriggerLog.triggered_at.desc()).limit(limit).all()
    return {
        "logs": [
            {
                "id": l.id,
                "rule_id": l.rule_id,
                "rule_name": l.rule_name,
                "market_question": l.market_question,
                "probability": l.probability,
                "shift": l.shift,
                "action": l.action,
                "ticker": l.ticker,
                "quantity": l.quantity,
                "sized_quantity": l.sized_quantity,
                "confidence_pct": l.confidence_pct,
                "triggered_at": (l.triggered_at.isoformat() + "Z") if l.triggered_at else None,
                "executed": l.executed,
                "log_type": l.log_type or "entry",
            }
            for l in logs
        ]
    }