from fastapi import APIRouter, HTTPException
from app.core.config import settings

router = APIRouter()

@router.get("/portfolio")
async def get_portfolio():
    """Get current paper trading portfolio from Alpaca"""
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=settings.alpaca_paper
        )
        account = client.get_account()
        positions = client.get_all_positions()

        return {
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "equity": float(account.equity),
            "cash": float(account.cash),
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                }
                for p in positions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch portfolio: {str(e)}")
