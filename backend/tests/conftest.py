import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.rules import Base as RulesBase, Rule
from app.models.settings import Base as SettingsBase


@pytest.fixture(autouse=True)
def _no_real_notifications(mocker):
    """Applies to every test automatically. notify_rule_event is imported
    directly (`from ... import notify_rule_event`) into both trade_executor.py
    and watchlist.py, so each call site needs patching separately — patching
    only app.services.notifications.notify_rule_event would miss both, since
    that kind of import binds a new name in the importing module rather than
    referencing the original one. Without this, tests that reach a successful
    trade/exit/alert path make a real Resend API call and send a real email."""
    mocker.patch("app.services.trade_executor.notify_rule_event")
    mocker.patch("app.api.watchlist.notify_rule_event")


@pytest.fixture
def db_session():
    """In-memory SQLite session with the rules + settings schema, isolated per test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    RulesBase.metadata.create_all(engine)
    SettingsBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_rule(db_session):
    """Factory for a persisted Rule with sane defaults, overridable per test."""

    def _make_rule(**overrides):
        defaults = dict(
            name="Test Rule",
            action="buy",
            ticker="AAPL",
            quantity=1.0,
            active=True,
            in_position=False,
        )
        defaults.update(overrides)
        rule = Rule(**defaults)
        db_session.add(rule)
        db_session.commit()
        db_session.refresh(rule)
        return rule

    return _make_rule
