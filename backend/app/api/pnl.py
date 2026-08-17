from fastapi import APIRouter, HTTPException
from app.core.config import settings

router = APIRouter()


@router.get("/pnl")
def get_pnl():
    """
    Calculate overall P&L from Alpaca paper trading account.
    Combines realized P&L from closed orders + unrealized P&L from open positions.
    """
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=True,
        )

        # ── Account snapshot ──────────────────────────────────────────────────
        account = client.get_account()
        portfolio_value = float(account.portfolio_value)
        last_equity = float(account.last_equity)
        equity = float(account.equity)
        cash = float(account.cash)

        # Today's P&L
        today_pnl = round(equity - last_equity, 2)
        today_pnl_pct = round((today_pnl / last_equity) * 100, 3) if last_equity else 0

        # ── Open positions ────────────────────────────────────────────────────
        positions = client.get_all_positions()
        unrealized_pnl = sum(float(p.unrealized_pl) for p in positions)
        unrealized_pnl = round(unrealized_pnl, 2)

        position_details = [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": round(float(p.unrealized_pl), 2),
                "unrealized_plpc": round(float(p.unrealized_plpc) * 100, 2),
                "side": str(p.side.value) if p.side else "long",
            }
            for p in positions
        ]

        # ── Closed orders — realized P&L ──────────────────────────────────────
        filled_orders = client.get_orders(
            filter=GetOrdersRequest(
                status=QueryOrderStatus.CLOSED,
                limit=200,
            )
        )

        realized_pnl = 0.0
        trade_count = 0
        wins = 0
        losses = 0
        best_trade = 0.0
        worst_trade = 0.0
        trade_pnls = []

        # Track buys to match against sells
        # Simple approach: pair fills by symbol chronologically
        holdings: dict[str, list] = {}

        for order in sorted(filled_orders, key=lambda o: o.filled_at or o.submitted_at):
            if not order.filled_avg_price or not order.filled_qty:
                continue
            symbol = order.symbol
            fill_price = float(order.filled_avg_price)
            qty = float(order.filled_qty)
            side = str(order.side.value) if order.side else ""

            if symbol not in holdings:
                holdings[symbol] = []

            if side == "buy":
                holdings[symbol].append({"price": fill_price, "qty": qty})
            elif side == "sell":
                # Match against existing buys FIFO
                remaining_sell = qty
                while remaining_sell > 0 and holdings.get(symbol):
                    buy = holdings[symbol][0]
                    matched = min(buy["qty"], remaining_sell)
                    pnl = (fill_price - buy["price"]) * matched
                    realized_pnl += pnl
                    trade_pnls.append(pnl)
                    trade_count += 1

                    if pnl > 0:
                        wins += 1
                        best_trade = max(best_trade, pnl)
                    else:
                        losses += 1
                        worst_trade = min(worst_trade, pnl)

                    buy["qty"] -= matched
                    remaining_sell -= matched
                    if buy["qty"] <= 0:
                        holdings[symbol].pop(0)

        realized_pnl = round(realized_pnl, 2)
        total_pnl = round(realized_pnl + unrealized_pnl, 2)
        win_rate = round(wins / trade_count * 100, 1) if trade_count > 0 else 0
        avg_trade = round(sum(trade_pnls) / len(trade_pnls), 2) if trade_pnls else 0

        # Starting capital = current equity - total pnl
        starting_capital = 100_000.0  # Alpaca paper default
        total_return_pct = round((total_pnl / starting_capital) * 100, 3)

        return {
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "today_pnl": today_pnl,
            "today_pnl_pct": today_pnl_pct,
            "portfolio_value": portfolio_value,
            "cash": cash,
            "trade_count": trade_count,
            "win_rate": win_rate,
            "wins": wins,
            "losses": losses,
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "avg_trade": avg_trade,
            "positions": position_details,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate P&L: {str(e)}")