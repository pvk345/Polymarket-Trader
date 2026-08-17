from datetime import datetime
import json
from sqlalchemy.orm import Session
from app.models.rules import Rule, TriggerLog
from app.services.trade_executor import execute_trade, check_exit_conditions, is_market_open


def _evaluate_multi_market_rule(rule: Rule, market_by_id: dict, db: Session) -> dict | None:
    """AND semantics: every pinned market's own condition+threshold must be true
    at the same time for the rule to fire. One rule, one combined entry/exit."""
    try:
        conditions = json.loads(rule.market_ids)
    except Exception:
        return None
    if not conditions:
        return None

    # ── In position: check exit using whichever pinned market is still visible ──
    if rule.in_position:
        exit_market = None
        for c in conditions:
            m = market_by_id.get(str(c["id"]))
            if m:
                exit_market = m
                break
        prob = exit_market.get("probability", 0) if exit_market else 0
        exited = check_exit_conditions(rule, prob, db)
        if exited:
            return {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "action": "exit",
                "ticker": rule.ticker,
                "probability": prob,
                "executed": True,
            }
        return None

    # ── Entry: every condition must currently be true ───────────────────────────
    evaluations = []
    for c in conditions:
        m = market_by_id.get(str(c["id"]))
        if not m:
            return None  # a pinned market is missing from this poll — can't confirm ALL are true
        prob = m.get("probability", 0)
        met = (
            (c["condition"] == "above" and prob >= c["threshold"]) or
            (c["condition"] == "below" and prob <= c["threshold"])
        )
        if not met:
            return None
        evaluations.append((c, m, prob))

    combined_question = " AND ".join(
        f'"{(c.get("question") or m.get("question"))}" ({prob:.1f}% {c["condition"]} {c["threshold"]}%)'
        for c, m, prob in evaluations
    )
    combined_ids = ",".join(str(c["id"]) for c, m, prob in evaluations)

    trigger = {
        "rule_id": rule.id,
        "rule_name": rule.name,
        "market_question": combined_question,
        "market_id": combined_ids,
        "probability": None,
        "shift": None,
        "action": rule.action,
        "ticker": rule.ticker,
        "quantity": rule.quantity,
    }

    log = TriggerLog(
        rule_id=rule.id,
        rule_name=rule.name,
        market_question=combined_question,
        market_id=combined_ids,
        probability=None,
        shift=None,
        action=rule.action,
        ticker=rule.ticker,
        quantity=rule.quantity,
        executed=False,
        log_type="entry",
    )
    db.add(log)
    db.flush()

    rule.triggered_count = (rule.triggered_count or 0) + 1
    rule.last_triggered = datetime.utcnow()

    print(
        f"\n🚨 RULE TRIGGERED (ALL {len(conditions)} conditions met): [{rule.name}]\n"
        f"   Markets : {combined_question[:160]}\n"
        f"   Action  : {rule.action.upper()} {rule.quantity}x {rule.ticker}\n",
        flush=True,
    )

    executed = execute_trade(trigger, log, db)
    trigger["executed"] = executed
    return trigger


def evaluate_rules(markets: list[dict], db: Session) -> list[dict]:
    active_rules: list[Rule] = db.query(Rule).filter(Rule.active == True).all()

    if not active_rules:
        return []

    # Nothing can execute while the stock market is closed — skip evaluation entirely
    # rather than repeatedly logging blocked attempts on every poll.
    if not is_market_open():
        return []

    triggers = []
    market_by_id = {str(m.get("id", "")): m for m in markets}

    for rule in active_rules:
        if rule.market_ids:
            trigger = _evaluate_multi_market_rule(rule, market_by_id, db)
            if trigger:
                triggers.append(trigger)
            continue

        if rule.market_id:
            matching_markets = [
                m for m in markets
                if str(m.get("id", "")) == str(rule.market_id)
            ]
        else:
            keyword = rule.keyword.lower()
            matching_markets = [
                m for m in markets
                if keyword in m.get("question", "").lower()
            ]

        for market in matching_markets:
            prob = market.get("probability", 0)

            # ── Check exit conditions first if in position ──────────────────
            if rule.in_position:
                exited = check_exit_conditions(rule, prob, db)
                if exited:
                    triggers.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "action": "exit",
                        "ticker": rule.ticker,
                        "probability": prob,
                        "executed": True,
                    })
                continue  # Don't re-enter while in position

            # ── Check entry conditions ──────────────────────────────────────
            condition_met = (
                (rule.condition == "above" and prob >= rule.threshold) or
                (rule.condition == "below" and prob <= rule.threshold)
            )

            if not condition_met:
                continue

            shift = market.get("shift")
            trigger = {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "market_question": market.get("question"),
                "market_id": market.get("id"),
                "probability": prob,
                "shift": shift,
                "action": rule.action,
                "ticker": rule.ticker,
                "quantity": rule.quantity,
            }

            log = TriggerLog(
                rule_id=rule.id,
                rule_name=rule.name,
                market_question=market.get("question"),
                market_id=market.get("id"),
                probability=prob,
                shift=shift,
                action=rule.action,
                ticker=rule.ticker,
                quantity=rule.quantity,
                executed=False,
                log_type="entry",
            )
            db.add(log)
            db.flush()

            rule.triggered_count = (rule.triggered_count or 0) + 1
            rule.last_triggered = datetime.utcnow()

            direction = "▲" if (shift and shift > 0) else "▼" if (shift and shift < 0) else "•"
            print(
                f"\n🚨 RULE TRIGGERED: [{rule.name}]\n"
                f"   Market  : {str(market.get('question', ''))[:80]}\n"
                f"   Prob    : {prob:.1f}% {direction}\n"
                f"   Action  : {rule.action.upper()} {rule.quantity}x {rule.ticker}\n",
                flush=True,
            )

            executed = execute_trade(trigger, log, db)
            trigger["executed"] = executed
            triggers.append(trigger)

    if triggers:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return triggers