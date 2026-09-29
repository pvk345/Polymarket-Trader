import os
from datetime import datetime, timedelta
import pytz
from sqlalchemy import text
from sqlalchemy.orm import Session
from models import TriggerLog, TradeGuard, Rule
from position_sizer import calculate_position_size, confidence_label
from settings import get_setting
from notifications import notify_rule_event

ALPACA_API_KEY = os.environ["ALPACA_API_KEY"]
ALPACA_SECRET_KEY = os.environ["ALPACA_SECRET_KEY"]
ALPACA_GUEST_API_KEY = os.environ.get("ALPACA_GUEST_API_KEY", "")
ALPACA_GUEST_SECRET_KEY = os.environ.get("ALPACA_GUEST_SECRET_KEY", "")

GUEST_USERNAME = "guest"


def _credentials_for_user(user_id: int | None, db: Session) -> tuple[str, str]:
    """Resolve which Alpaca account a rule's trades execute against — the
    guest account gets its own isolated paper account (when configured) so
    demo trades never land in the primary account."""
    if user_id is not None and ALPACA_GUEST_API_KEY:
        row = db.execute(text("SELECT username FROM users WHERE id = :id"), {"id": user_id}).fetchone()
        if row and row[0] == GUEST_USERNAME:
            return ALPACA_GUEST_API_KEY, ALPACA_GUEST_SECRET_KEY
    return ALPACA_API_KEY, ALPACA_SECRET_KEY


def is_market_open() -> bool:
    """Check if US stock market is currently open (Mon-Fri, 9:30 AM - 4:00 PM ET)."""
    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)

    if now_et.weekday() >= 5:
        return False

    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now_et <= market_close


def _get_cooldown_minutes(db: Session) -> int:
    try:
        return int(get_setting("cooldown_minutes", db))
    except Exception:
        return 60


def _is_on_cooldown(rule_id: int, ticker: str, db: Session) -> bool:
    cooldown = _get_cooldown_minutes(db)
    cutoff = datetime.utcnow() - timedelta(minutes=cooldown)
    guard = (
        db.query(TradeGuard)
        .filter(
            TradeGuard.rule_id == rule_id,
            TradeGuard.ticker == ticker,
            TradeGuard.last_executed >= cutoff,
        )
        .first()
    )
    return guard is not None


def _update_guard(rule_id: int, ticker: str, db: Session):
    guard = (
        db.query(TradeGuard)
        .filter(TradeGuard.rule_id == rule_id, TradeGuard.ticker == ticker)
        .first()
    )
    if guard:
        guard.last_executed = datetime.utcnow()
    else:
        db.add(TradeGuard(rule_id=rule_id, ticker=ticker, last_executed=datetime.utcnow()))


def _get_current_price(ticker: str, api_key: str = ALPACA_API_KEY, secret_key: str = ALPACA_SECRET_KEY):
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(api_key, secret_key, paper=True)
        position = client.get_open_position(ticker)
        return float(position.current_price)
    except Exception:
        return None


def _place_order(ticker: str, qty: float, action: str, api_key: str = ALPACA_API_KEY, secret_key: str = ALPACA_SECRET_KEY):
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = TradingClient(api_key, secret_key, paper=True)
        side = OrderSide.BUY if action == "buy" else OrderSide.SELL
        order = client.submit_order(MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        ))
        return True, str(order.id), None
    except Exception as e:
        return False, None, str(e)


def execute_trade(trigger: dict, log: TriggerLog, db: Session) -> bool:
    rule_id = trigger["rule_id"]
    ticker = trigger["ticker"]
    action = trigger["action"]
    probability = trigger.get("probability") or 0

    if _is_on_cooldown(rule_id, ticker, db):
        cooldown = _get_cooldown_minutes(db)
        print(f"COOLDOWN: Rule [{trigger['rule_name']}] skipped — {ticker} already traded within {cooldown} min")
        return False

    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    api_key, secret_key = _credentials_for_user(rule.user_id if rule else None, db)

    if rule and rule.use_dynamic_sizing and rule.max_quantity:
        sized_qty = calculate_position_size(
            probability=probability,
            threshold=rule.threshold,
            min_qty=rule.quantity,
            max_qty=rule.max_quantity,
        )
        confidence = confidence_label(probability, rule.threshold)
        print(f"POSITION SIZING: [{trigger['rule_name']}] prob={probability:.1f}% confidence={confidence} sized_qty={sized_qty}")
    else:
        sized_qty = trigger.get("quantity", rule.quantity if rule else 1.0)

    if sized_qty <= 0:
        print(f"Zero qty for {ticker} — skipping")
        return False

    try:
        max_usd = float(get_setting("max_trade_size_usd", db))
        current_price = _get_current_price(ticker, api_key, secret_key)
        if current_price:
            trade_value = sized_qty * current_price
            if trade_value > max_usd:
                new_qty = round(max_usd / current_price, 2)
                print(f"Trade capped at ${max_usd}: {sized_qty} -> {new_qty} shares of {ticker}")
                sized_qty = new_qty
    except Exception:
        pass

    success, order_id, error = _place_order(ticker, sized_qty, action, api_key, secret_key)

    if success:
        log.executed = True
        log.alpaca_order_id = order_id
        log.log_type = "entry"
        log.sized_quantity = sized_qty
        log.confidence_pct = probability

        if rule:
            rule.in_position = True
            rule.entry_date = datetime.utcnow()
            rule.actual_quantity = sized_qty
            current_price = _get_current_price(ticker, api_key, secret_key)
            if current_price:
                rule.entry_price = current_price

        _update_guard(rule_id, ticker, db)
        db.commit()

        print(f"ENTRY EXECUTED: [{trigger['rule_name']}] {action.upper()} {sized_qty} shares of {ticker} @ order {order_id}")
        notify_rule_event(
            rule.user_id if rule else None,
            f"Rule triggered: {trigger['rule_name']}",
            f"{action.upper()} {sized_qty} shares of {ticker} at {probability:.1f}% probability. Order ID: {order_id}",
            db,
        )
        return True
    else:
        log.execution_error = error
        db.commit()
        print(f"TRADE FAILED: {ticker} — {error}")
        return False


def execute_exit(rule: Rule, reason: str, db: Session) -> bool:
    ticker = rule.ticker
    quantity = rule.actual_quantity or rule.quantity
    exit_action = "sell" if rule.action == "buy" else "buy"
    api_key, secret_key = _credentials_for_user(rule.user_id, db)

    print(f"EXIT TRIGGERED: [{rule.name}] reason={reason} action={exit_action.upper()} {quantity} shares of {ticker}")

    success, order_id, error = _place_order(ticker, quantity, exit_action, api_key, secret_key)

    log = TriggerLog(
        rule_id=rule.id,
        rule_name=rule.name,
        market_question=f"EXIT: {reason}",
        action=exit_action,
        ticker=ticker,
        quantity=quantity,
        sized_quantity=quantity,
        executed=success,
        alpaca_order_id=order_id,
        execution_error=error,
        log_type="exit",
    )
    db.add(log)

    if success:
        rule.in_position = False
        rule.entry_price = None
        rule.entry_date = None
        rule.actual_quantity = None
        _update_guard(rule.id, ticker, db)
        db.commit()
        print(f"EXIT EXECUTED: [{rule.name}] order {order_id}")
        notify_rule_event(
            rule.user_id,
            f"Rule exited: {rule.name}",
            f"{exit_action.upper()} {quantity} shares of {ticker}. Reason: {reason}. Order ID: {order_id}",
            db,
        )
        return True
    else:
        db.commit()
        print(f"EXIT FAILED: {ticker} — {error}")
        return False


def check_exit_conditions(rule: Rule, current_prob: float, db: Session) -> bool:
    if not rule.in_position:
        return False
    if not rule.exit_condition:
        return False

    reason = None

    if rule.exit_condition == "prob_below" and rule.exit_threshold is not None:
        if current_prob <= rule.exit_threshold:
            reason = f"Probability dropped to {current_prob:.1f}% (below {rule.exit_threshold}%)"

    elif rule.exit_condition == "prob_above" and rule.exit_threshold is not None:
        if current_prob >= rule.exit_threshold:
            reason = f"Probability rose to {current_prob:.1f}% (above {rule.exit_threshold}%)"

    elif rule.exit_condition in ("take_profit", "stop_loss"):
        api_key, secret_key = _credentials_for_user(rule.user_id, db)
        current_price = _get_current_price(rule.ticker, api_key, secret_key)
        if current_price and rule.entry_price:
            if rule.action == "buy":
                pnl_pct = ((current_price - rule.entry_price) / rule.entry_price) * 100
            else:
                pnl_pct = ((rule.entry_price - current_price) / rule.entry_price) * 100

            if rule.exit_condition == "take_profit" and rule.take_profit_pct:
                if pnl_pct >= rule.take_profit_pct:
                    reason = f"Take profit hit: +{pnl_pct:.1f}% (target: +{rule.take_profit_pct}%)"

            elif rule.exit_condition == "stop_loss" and rule.stop_loss_pct:
                if pnl_pct <= -rule.stop_loss_pct:
                    reason = f"Stop loss hit: {pnl_pct:.1f}% (limit: -{rule.stop_loss_pct}%)"

    if reason:
        return execute_exit(rule, reason, db)
    return False
