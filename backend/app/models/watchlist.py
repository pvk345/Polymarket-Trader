from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(20), nullable=False)
    label = Column(String(200), nullable=True)
    alert_above = Column(Float, nullable=True)   # alert when price rises above this
    alert_below = Column(Float, nullable=True)   # alert when price drops below this
    active = Column(Boolean, default=True)
    last_price = Column(Float, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    alert_triggered = Column(Boolean, default=False)
    alert_triggered_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)