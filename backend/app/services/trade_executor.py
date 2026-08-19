from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.rules import TriggerLog, TradeGuard, Rule
from app.services.position_sizer import calculate_position_size, confidence_label
from app.services.notifications import notify_rule_event


def is_market_open() -> bool:
    """Check if US stock market is currently open (Mon-Fri, 9:30 AM - 4:00 PM ET)."""
    et = pytz.timezone("America/New_York")
    now_et = datetime.now(et)

    # Weekend check
    if now_et.weekday() >= 5:
        return False

    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now_et <= market_close


def _get_cooldown_minutes(db: Session) -> int:
    try:
        from app.api.settings import get_setting
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
        db.add(TradeGuard(
            rule_id=rule_id,
            ticker=ticker,
            last_executed=datetime.utcnow(),
        ))


def _get_current_price(ticker: str) -> float | None:
    try:
        from alpaca.trading.client import TradingClient
        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=True,
        )
        position = client.get_open_position(ticker)
        return float(position.current_price)
    except Exception:
        return None


def _place_order(ticker: str, qty: float, action: str) -> tuple[bool, str | None, str | None]:
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key,
            paper=True,
        )
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
    probability = trigger.get("probability", 0)

    # ── Market hours check ─────────────────────────────────────────────────────
    if not is_market_open():
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)
        print(
            f"🕐 MARKET CLOSED: Rule [{trigger['rule_name']}] skipped — "
            f"market is closed ({now_et.strftime('%a %I:%M %p ET')}). "
            f"Open Mon-Fri 9:30 AM - 4:00 PM ET.",
            flush=True,
        )
        return False

    # ── Cooldown check ─────────────────────────────────────────────────────────
    if _is_on_cooldown(rule_id, ticker, db):
        cooldown = _get_cooldown_minutes(db)
        print(
            f"⏸  COOLDOWN: Rule [{trigger['rule_name']}] skipped — "
            f"{ticker} already traded within {cooldown} min",
            flush=True,
        )
        return False

    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    # ── Position sizing ────────────────────────────────────────────────────────
    if rule and rule.use_dynamic_sizing and rule.max_quantity:
        sized_qty = calculate_position_size(
            probability=probability,
            threshold=rule.threshold,
            min_qty=rule.quantity,
            max_qty=rule.max_quantity,
        )
        confidence = confidence_label(probability, rule.threshold)
        print(
            f"📐 POSITION SIZING: [{trigger['rule_name']}]\n"
            f"   Probability : {probability:.1f}%\n"
            f"   Confidence  : {confidence}\n"
            f"   Sized qty   : {sized_qty} shares\n",
            flush=True,
        )
    else:
        sized_qty = trigger.get("quantity", rule.quantity if rule else 1.0)

    if sized_qty <= 0:
        print(f"⚠️  Zero qty for {ticker} — skipping", flush=True)
        return False

    # ── Max trade size guard ───────────────────────────────────────────────────
    try:
        from app.api.settings import get_setting
        max_usd = float(get_setting("max_trade_size_usd", db))
        current_price = _get_current_price(ticker)
        if current_price:
            trade_value = sized_qty * current_price
            if trade_value > max_usd:
                new_qty = round(max_usd / current_price, 2)
                print(
                    f"⚠️  Trade capped at ${max_usd}: "
                    f"{sized_qty} → {new_qty} shares of {ticker}",
                    flush=True,
                )
                sized_qty = new_qty
    except Exception:
        pass

    success, order_id, error = _place_order(ticker, sized_qty, action)

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
            current_price = _get_current_price(ticker)
            if current_price:
                rule.entry_price = current_price

        _update_guard(rule_id, ticker, db)
        db.commit()

        print(
            f"\n✅ ENTRY EXECUTED: [{trigger['rule_name']}]\n"
            f"   Order   : {action.upper()} {sized_qty} shares of {ticker}\n"
            f"   Prob    : {probability:.1f}%\n"
            f"   Order ID: {order_id}\n",
            flush=True,
        )
        notify_rule_event(
            rule.user_id if rule else None,
            f"Rule triggered: {trigger['rule_name']}",
            f"{action.upper()} {sized_qty} shares of {ticker} at {probability:.1f}% probability. Order ID: {order_id}",
        )
        return True
    else:
        log.execution_error = error
        db.commit()
        print(f"\n❌ TRADE FAILED: {ticker} — {error}\n", flush=True)
        return False


def execute_exit(rule: Rule, reason: str, db: Session) -> bool:
    ticker = rule.ticker
    quantity = rule.actual_quantity or rule.quantity
    exit_action = "sell" if rule.action == "buy" else "buy"

    # ── Market hours check for exits too ──────────────────────────────────────
    if not is_market_open():
        et = pytz.timezone("America/New_York")
        now_et = datetime.now(et)
        print(
            f"🕐 MARKET CLOSED: Exit for [{rule.name}] skipped — "
            f"market is closed ({now_et.strftime('%a %I:%M %p ET')})",
            flush=True,
        )
        return False

    print(
        f"\n🚨 EXIT TRIGGERED: [{rule.name}]\n"
        f"   Reason  : {reason}\n"
        f"   Action  : {exit_action.upper()} {quantity} shares of {ticker}\n",
        flush=True,
    )

    success, order_id, error = _place_order(ticker, quantity, exit_action)

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
        print(f"✅ EXIT EXECUTED: [{rule.name}] Order ID: {order_id}\n", flush=True)
        notify_rule_event(
            rule.user_id,
            f"Rule exited: {rule.name}",
            f"{exit_action.upper()} {quantity} shares of {ticker}. Reason: {reason}. Order ID: {order_id}",
        )
        return True
    else:
        db.commit()
        print(f"❌ EXIT FAILED: {ticker} — {error}\n", flush=True)
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
        current_price = _get_current_price(rule.ticker)
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