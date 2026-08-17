from datetime import datetime
import json
from sqlalchemy.orm import Session
from models import Rule, TriggerLog
from trade_executor import execute_trade, check_exit_conditions, is_market_open


def _evaluate_multi_market_rule(rule: Rule, market_by_id: dict, db: Session):
    try:
        conditions = json.loads(rule.market_ids)
    except Exception:
        return None
    if not conditions:
        return None

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
            return {"rule_id": rule.id, "rule_name": rule.name, "action": "exit", "ticker": rule.ticker, "probability": prob, "executed": True}
        return None

    evaluations = []
    for c in conditions:
        m = market_by_id.get(str(c["id"]))
        if not m:
            return None
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
        "rule_id": rule.id, "rule_name": rule.name, "market_question": combined_question,
        "market_id": combined_ids, "probability": None, "shift": None,
        "action": rule.action, "ticker": rule.ticker, "quantity": rule.quantity,
    }
    log = TriggerLog(
        rule_id=rule.id, rule_name=rule.name, market_question=combined_question,
        market_id=combined_ids, probability=None, shift=None,
        action=rule.action, ticker=rule.ticker, quantity=rule.quantity,
        executed=False, log_type="entry",
    )
    db.add(log)
    db.flush()

    rule.triggered_count = (rule.triggered_count or 0) + 1
    rule.last_triggered = datetime.utcnow()

    print(f"RULE TRIGGERED (ALL {len(conditions)} conditions met): [{rule.name}] {combined_question[:160]} -> {rule.action.upper()} {rule.quantity}x {rule.ticker}")

    executed = execute_trade(trigger, log, db)
    trigger["executed"] = executed
    return trigger


def evaluate_rules(markets: list, db: Session) -> list:
    active_rules = db.query(Rule).filter(Rule.active == True).all()
    if not active_rules:
        return []

    if not is_market_open():
        print("Market closed — skipping evaluation")
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
            matching_markets = [m for m in markets if str(m.get("id", "")) == str(rule.market_id)]
        else:
            keyword = rule.keyword.lower()
            matching_markets = [m for m in markets if keyword in m.get("question", "").lower()]

        for market in matching_markets:
            prob = market.get("probability", 0)

            if rule.in_position:
                exited = check_exit_conditions(rule, prob, db)
                if exited:
                    triggers.append({"rule_id": rule.id, "rule_name": rule.name, "action": "exit", "ticker": rule.ticker, "probability": prob, "executed": True})
                continue

            condition_met = (
                (rule.condition == "above" and prob >= rule.threshold) or
                (rule.condition == "below" and prob <= rule.threshold)
            )
            if not condition_met:
                continue

            shift = market.get("shift")
            trigger = {
                "rule_id": rule.id, "rule_name": rule.name, "market_question": market.get("question"),
                "market_id": market.get("id"), "probability": prob, "shift": shift,
                "action": rule.action, "ticker": rule.ticker, "quantity": rule.quantity,
            }
            log = TriggerLog(
                rule_id=rule.id, rule_name=rule.name, market_question=market.get("question"),
                market_id=market.get("id"), probability=prob, shift=shift,
                action=rule.action, ticker=rule.ticker, quantity=rule.quantity,
                executed=False, log_type="entry",
            )
            db.add(log)
            db.flush()

            rule.triggered_count = (rule.triggered_count or 0) + 1
            rule.last_triggered = datetime.utcnow()

            print(f"RULE TRIGGERED: [{rule.name}] {str(market.get('question',''))[:80]} prob={prob:.1f}% -> {rule.action.upper()} {rule.quantity}x {rule.ticker}")

            executed = execute_trade(trigger, log, db)
            trigger["executed"] = executed
            triggers.append(trigger)

    if triggers:
        try:
            db.commit()
        except Exception:
            db.rollback()

    return triggers
