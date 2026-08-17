from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.config import settings
from app.models.rules import TriggerLog

router = APIRouter()


@router.get("/history")
def get_history(
    ticker: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    sort: str = Query("desc"),
    limit: int = Query(100),
    db: Session = Depends(get_db),
):
    q = db.query(TriggerLog).filter(TriggerLog.executed == True)

    if ticker:
        q = q.filter(TriggerLog.ticker == ticker.upper())
    if action:
        q = q.filter(TriggerLog.action == action.lower())

    order_col = TriggerLog.triggered_at.desc() if sort == "desc" else TriggerLog.triggered_at.asc()
    logs = q.order_by(order_col).limit(limit).all()

    alpaca_orders = {}
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=True,
        )
        orders = client.get_orders(
            filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=200)
        )
        alpaca_orders = {str(o.id): o for o in orders}
    except Exception as e:
        print(f"Warning: could not fetch Alpaca orders: {e}")

    history = []
    for log in logs:
        order = alpaca_orders.get(log.alpaca_order_id) if log.alpaca_order_id else None

        filled_price = None
        filled_qty = None
        total_value = None
        status = "executed"

        if order:
            try:
                filled_price = float(order.filled_avg_price) if order.filled_avg_price else None
                filled_qty = float(order.filled_qty) if order.filled_qty else float(log.quantity)
                total_value = round(filled_price * filled_qty, 2) if filled_price else None
                status = str(order.status.value) if order.status else "unknown"
            except Exception:
                pass

        history.append({
            "id": log.id,
            "alpaca_order_id": log.alpaca_order_id,
            "ticker": log.ticker,
            "action": log.action,
            "quantity": log.quantity,
            "filled_price": filled_price,
            "filled_qty": filled_qty,
            "total_value": total_value,
            "status": status,
            "rule_name": log.rule_name,
            "market_question": log.market_question,
            "probability": log.probability,
            "shift": log.shift,
            "triggered_at": (log.triggered_at.isoformat() + "Z") if log.triggered_at else None,
            "execution_error": log.execution_error,
        })

    total_value_sum = sum(h["total_value"] for h in history if h["total_value"])

    return {
        "history": history,
        "summary": {
            "total_trades": len(history),
            "total_buys": sum(1 for h in history if h["action"] == "buy"),
            "total_sells": sum(1 for h in history if h["action"] == "sell"),
            "total_value_traded": round(total_value_sum, 2),
        },
    }