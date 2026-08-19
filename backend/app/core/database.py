from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.rules import Base as RulesBase
from app.models.settings import Base as SettingsBase
from app.models.watchlist import Base as WatchlistBase

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    RulesBase.metadata.create_all(bind=engine)
    SettingsBase.metadata.create_all(bind=engine)
    WatchlistBase.metadata.create_all(bind=engine)

    new_columns = [
        ("trigger_logs", "alpaca_order_id", "VARCHAR(100)"),
        ("trigger_logs", "execution_error", "TEXT"),
        ("trigger_logs", "log_type", "VARCHAR(20) DEFAULT 'entry'"),
        ("trigger_logs", "sized_quantity", "FLOAT"),
        ("trigger_logs", "confidence_pct", "FLOAT"),
        ("rules", "exit_condition", "VARCHAR(20)"),
        ("rules", "exit_threshold", "FLOAT"),
        ("rules", "take_profit_pct", "FLOAT"),
        ("rules", "stop_loss_pct", "FLOAT"),
        ("rules", "in_position", "BOOLEAN DEFAULT FALSE"),
        ("rules", "entry_price", "FLOAT"),
        ("rules", "entry_date", "TIMESTAMP"),
        ("rules", "actual_quantity", "FLOAT"),
        ("rules", "max_quantity", "FLOAT"),
        ("rules", "use_dynamic_sizing", "BOOLEAN DEFAULT FALSE"),
        ("rules", "market_id", "VARCHAR(50)"),
        ("rules", "market_question", "TEXT"),
        ("rules", "market_ids", "TEXT"),
        ("rules", "user_id", "INTEGER"),
        ("watchlist", "user_id", "INTEGER"),
    ]

    with engine.connect() as conn:
        for table, col, col_type in new_columns:
            try:
                conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"
                ))
                conn.commit()
            except Exception:
                conn.rollback()

        # keyword used to be required — rules can now be pinned to a market_id instead
        try:
            conn.execute(text("ALTER TABLE rules ALTER COLUMN keyword DROP NOT NULL"))
            conn.commit()
        except Exception:
            conn.rollback()

        # condition/threshold used to be required — multi-market (market_ids) rules carry
        # their own condition+threshold per pinned market instead of one shared pair
        for col in ("condition", "threshold"):
            try:
                conn.execute(text(f"ALTER TABLE rules ALTER COLUMN {col} DROP NOT NULL"))
                conn.commit()
            except Exception:
                conn.rollback()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()