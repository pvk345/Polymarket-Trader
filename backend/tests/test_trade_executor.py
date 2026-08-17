import pytest
from datetime import datetime, timedelta
from freezegun import freeze_time

from app.models.rules import TriggerLog, TradeGuard
from app.services import trade_executor
from app.services.trade_executor import (
    is_market_open,
    _is_on_cooldown,
    _update_guard,
    execute_trade,
    check_exit_conditions,
)


class TestIsMarketOpen:
    @freeze_time("2024-01-16 15:00:00")  # Tue, 10:00 ET (winter/EST)
    def test_open_during_weekday_trading_hours(self):
        assert is_market_open() is True

    @freeze_time("2024-01-20 15:00:00")  # Saturday
    def test_closed_on_weekend(self):
        assert is_market_open() is False

    @freeze_time("2024-01-16 13:00:00")  # Tue, 08:00 ET — before 9:30 open
    def test_closed_before_open(self):
        assert is_market_open() is False

    @freeze_time("2024-01-16 22:00:00")  # Tue, 17:00 ET — after 16:00 close
    def test_closed_after_close(self):
        assert is_market_open() is False


class TestCooldown:
    def test_no_guard_row_means_not_on_cooldown(self, db_session):
        assert _is_on_cooldown(rule_id=1, ticker="AAPL", db=db_session) is False

    def test_recent_guard_row_means_on_cooldown(self, db_session):
        db_session.add(TradeGuard(rule_id=1, ticker="AAPL", last_executed=datetime.utcnow()))
        db_session.commit()
        assert _is_on_cooldown(rule_id=1, ticker="AAPL", db=db_session) is True

    def test_stale_guard_row_past_default_window_is_not_on_cooldown(self, db_session):
        stale = datetime.utcnow() - timedelta(minutes=120)  # default cooldown is 60 min
        db_session.add(TradeGuard(rule_id=1, ticker="AAPL", last_executed=stale))
        db_session.commit()
        assert _is_on_cooldown(rule_id=1, ticker="AAPL", db=db_session) is False

    def test_guard_is_scoped_to_rule_and_ticker(self, db_session):
        db_session.add(TradeGuard(rule_id=1, ticker="AAPL", last_executed=datetime.utcnow()))
        db_session.commit()
        assert _is_on_cooldown(rule_id=1, ticker="TSLA", db=db_session) is False
        assert _is_on_cooldown(rule_id=2, ticker="AAPL", db=db_session) is False

    def test_update_guard_creates_row_when_missing(self, db_session):
        _update_guard(rule_id=1, ticker="AAPL", db=db_session)
        db_session.commit()
        guard = db_session.query(TradeGuard).filter_by(rule_id=1, ticker="AAPL").first()
        assert guard is not None

    def test_update_guard_refreshes_existing_row(self, db_session):
        old_time = datetime.utcnow() - timedelta(hours=5)
        db_session.add(TradeGuard(rule_id=1, ticker="AAPL", last_executed=old_time))
        db_session.commit()

        _update_guard(rule_id=1, ticker="AAPL", db=db_session)
        db_session.commit()

        guards = db_session.query(TradeGuard).filter_by(rule_id=1, ticker="AAPL").all()
        assert len(guards) == 1  # updated in place, not duplicated
        assert guards[0].last_executed > old_time


class TestExecuteTrade:
    def _trigger(self, rule, **overrides):
        base = dict(
            rule_id=rule.id,
            rule_name=rule.name,
            ticker=rule.ticker,
            action=rule.action,
            probability=75.0,
            quantity=rule.quantity,
        )
        base.update(overrides)
        return base

    def _log(self, rule):
        return TriggerLog(
            rule_id=rule.id, rule_name=rule.name, ticker=rule.ticker,
            action=rule.action, quantity=rule.quantity,
        )

    @freeze_time("2024-01-20 15:00:00")  # Saturday — market closed
    def test_skips_when_market_closed(self, db_session, make_rule, mocker):
        place_order = mocker.patch.object(trade_executor, "_place_order")
        rule = make_rule()
        result = execute_trade(self._trigger(rule), self._log(rule), db_session)
        assert result is False
        place_order.assert_not_called()

    @freeze_time("2024-01-16 15:00:00")  # weekday, market open
    def test_skips_when_on_cooldown(self, db_session, make_rule, mocker):
        place_order = mocker.patch.object(trade_executor, "_place_order")
        rule = make_rule()
        db_session.add(TradeGuard(rule_id=rule.id, ticker=rule.ticker, last_executed=datetime.utcnow()))
        db_session.commit()

        result = execute_trade(self._trigger(rule), self._log(rule), db_session)
        assert result is False
        place_order.assert_not_called()

    @freeze_time("2024-01-16 15:00:00")
    def test_skips_when_dynamic_sizing_yields_zero_qty(self, db_session, make_rule, mocker):
        place_order = mocker.patch.object(trade_executor, "_place_order")
        rule = make_rule(use_dynamic_sizing=True, threshold=80.0, quantity=1.0, max_quantity=5.0)
        # probability below threshold -> calculate_position_size returns 0.0
        trigger = self._trigger(rule, probability=50.0)

        result = execute_trade(trigger, self._log(rule), db_session)
        assert result is False
        place_order.assert_not_called()

    @freeze_time("2024-01-16 15:00:00")
    def test_successful_order_updates_rule_and_log(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-123", None))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=150.0)
        rule = make_rule()
        log = self._log(rule)

        result = execute_trade(self._trigger(rule), log, db_session)

        assert result is True
        assert log.executed is True
        assert log.alpaca_order_id == "order-123"
        assert rule.in_position is True
        assert rule.entry_price == 150.0
        guard = db_session.query(TradeGuard).filter_by(rule_id=rule.id, ticker=rule.ticker).first()
        assert guard is not None

    @freeze_time("2024-01-16 15:00:00")
    def test_failed_order_records_error_and_leaves_position_untouched(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(False, None, "insufficient buying power"))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=100.0)
        rule = make_rule()
        log = self._log(rule)

        result = execute_trade(self._trigger(rule), log, db_session)

        assert result is False
        assert log.execution_error == "insufficient buying power"
        assert rule.in_position is False

    @freeze_time("2024-01-16 15:00:00")
    def test_trade_value_capped_at_max_trade_size(self, db_session, make_rule, mocker):
        place_order = mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=500.0)
        # default max_trade_size_usd is $1000 -> at $500/share, qty should be capped to 2.0
        rule = make_rule(quantity=10.0)

        execute_trade(self._trigger(rule, quantity=10.0), self._log(rule), db_session)

        _, kwargs_or_args = place_order.call_args, None
        called_qty = place_order.call_args.args[1] if place_order.call_args.args else place_order.call_args.kwargs["qty"]
        assert called_qty == 2.0


class TestCheckExitConditions:
    def test_returns_false_when_not_in_position(self, make_rule):
        rule = make_rule(in_position=False, exit_condition="prob_below", exit_threshold=40.0)
        assert check_exit_conditions(rule, current_prob=10.0, db=None) is False

    def test_returns_false_when_no_exit_condition_configured(self, make_rule):
        rule = make_rule(in_position=True, exit_condition=None)
        assert check_exit_conditions(rule, current_prob=10.0, db=None) is False

    @freeze_time("2024-01-16 15:00:00")
    def test_prob_below_triggers_exit(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        rule = make_rule(in_position=True, exit_condition="prob_below", exit_threshold=40.0, actual_quantity=1.0)
        assert check_exit_conditions(rule, current_prob=35.0, db=db_session) is True
        assert rule.in_position is False

    @freeze_time("2024-01-16 15:00:00")
    def test_prob_below_does_not_trigger_above_threshold(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        rule = make_rule(in_position=True, exit_condition="prob_below", exit_threshold=40.0, actual_quantity=1.0)
        assert check_exit_conditions(rule, current_prob=45.0, db=db_session) is False
        assert rule.in_position is True

    @freeze_time("2024-01-16 15:00:00")
    def test_take_profit_triggers_on_buy_side_gain(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=110.0)
        rule = make_rule(
            action="buy", in_position=True, exit_condition="take_profit",
            take_profit_pct=5.0, entry_price=100.0, actual_quantity=1.0,
        )
        # (110 - 100) / 100 = +10% >= 5% target
        assert check_exit_conditions(rule, current_prob=0, db=db_session) is True

    @freeze_time("2024-01-16 15:00:00")
    def test_stop_loss_triggers_on_buy_side_loss(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=90.0)
        rule = make_rule(
            action="buy", in_position=True, exit_condition="stop_loss",
            stop_loss_pct=5.0, entry_price=100.0, actual_quantity=1.0,
        )
        # (90 - 100) / 100 = -10% <= -5% limit
        assert check_exit_conditions(rule, current_prob=0, db=db_session) is True

    @freeze_time("2024-01-16 15:00:00")
    def test_stop_loss_does_not_trigger_within_limit(self, db_session, make_rule, mocker):
        mocker.patch.object(trade_executor, "_place_order", return_value=(True, "order-1", None))
        mocker.patch.object(trade_executor, "_get_current_price", return_value=98.0)
        rule = make_rule(
            action="buy", in_position=True, exit_condition="stop_loss",
            stop_loss_pct=5.0, entry_price=100.0, actual_quantity=1.0,
        )
        # (98 - 100) / 100 = -2%, within the -5% limit
        assert check_exit_conditions(rule, current_prob=0, db=db_session) is False

    @freeze_time("2024-01-20 15:00:00")  # Saturday — exits are also gated on market hours
    def test_exit_skipped_when_market_closed(self, db_session, make_rule, mocker):
        place_order = mocker.patch.object(trade_executor, "_place_order")
        rule = make_rule(in_position=True, exit_condition="prob_below", exit_threshold=40.0, actual_quantity=1.0)
        assert check_exit_conditions(rule, current_prob=10.0, db=db_session) is False
        place_order.assert_not_called()
