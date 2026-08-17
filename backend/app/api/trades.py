from fastapi import APIRouter, HTTPException
from app.core.config import settings

router = APIRouter()


@router.get("/trades")
def get_trades():
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=True,
        )

        orders = client.get_orders(filter=GetOrdersRequest(
            status=QueryOrderStatus.ALL, limit=20
        ))

        return {
            "trades": [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "qty": float(o.qty) if o.qty else 0,
                    "side": str(o.side.value) if o.side else "",
                    "status": str(o.status.value) if o.status else "",
                    "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                    "filled_qty": float(o.filled_qty) if o.filled_qty else 0,
                    "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
                    "filled_at": o.filled_at.isoformat() if o.filled_at else None,
                }
                for o in orders
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))