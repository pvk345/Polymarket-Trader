from fastapi import APIRouter, HTTPException, Depends
from app.core.config import settings
from app.api.auth import get_current_user, get_alpaca_credentials

router = APIRouter()

@router.get("/portfolio")
async def get_portfolio(current_user: str = Depends(get_current_user)):
    """Get current paper trading portfolio from Alpaca"""
    try:
        from alpaca.trading.client import TradingClient
        api_key, secret_key = get_alpaca_credentials(current_user)
        client = TradingClient(
            api_key,
            secret_key,
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
