from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Rule(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)  # NULL = legacy/shared rule, visible to all
    name = Column(String(200), nullable=False)
    keyword = Column(String(200), nullable=True)
    market_id = Column(String(50), nullable=True)      # Polymarket market ID — if set, rule is pinned to this exact market
    market_question = Column(Text, nullable=True)        # snapshot of the question, for display
    market_ids = Column(Text, nullable=True)             # JSON array of {id, question, condition, threshold} — ALL must be true at once to fire
    condition = Column(String(10), nullable=True)         # unused when market_ids is set (each entry carries its own)
    threshold = Column(Float, nullable=True)              # unused when market_ids is set (each entry carries its own)
    action = Column(String(10), nullable=False)
    ticker = Column(String(20), nullable=False)
    active = Column(Boolean, default=True)
    triggered_count = Column(Integer, default=0)
    last_triggered = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)

    # Position sizing
    quantity = Column(Float, nullable=False, default=1.0)   # min shares (or fixed if no sizing)
    max_quantity = Column(Float, nullable=True)              # max shares at 100% confidence
    use_dynamic_sizing = Column(Boolean, default=False)      # enable probability-scaled sizing

    # Exit strategy
    exit_condition = Column(String(20), nullable=True)
    exit_threshold = Column(Float, nullable=True)
    take_profit_pct = Column(Float, nullable=True)
    stop_loss_pct = Column(Float, nullable=True)
    in_position = Column(Boolean, default=False)
    entry_price = Column(Float, nullable=True)
    entry_date = Column(DateTime, nullable=True)
    actual_quantity = Column(Float, nullable=True)  # actual shares bought (after sizing)


class TriggerLog(Base):
    __tablename__ = "trigger_logs"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=False)
    rule_name = Column(String(200))
    market_question = Column(Text)
    market_id = Column(String(200))
    probability = Column(Float)
    shift = Column(Float, nullable=True)
    action = Column(String(10))
    ticker = Column(String(20))
    quantity = Column(Float)
    triggered_at = Column(DateTime, server_default=func.now())
    executed = Column(Boolean, default=False)
    alpaca_order_id = Column(String(100), nullable=True)
    execution_error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    log_type = Column(String(20), default="entry")
    sized_quantity = Column(Float, nullable=True)  # actual quantity after sizing
    confidence_pct = Column(Float, nullable=True)  # probability at time of trade


class TradeGuard(Base):
    __tablename__ = "trade_guards"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, nullable=False)
    ticker = Column(String(20), nullable=False)
    last_executed = Column(DateTime, nullable=False)