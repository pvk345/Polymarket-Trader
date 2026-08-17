import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.rules import Base as RulesBase, Rule
from app.models.settings import Base as SettingsBase


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
