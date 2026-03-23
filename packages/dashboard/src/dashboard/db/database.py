"""SQLAlchemy engine + session factory for the dashboard SQLite database.

Uses sync SQLAlchemy (simpler than async for SQLite at this scale).
WAL mode enabled for better concurrent read performance.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Default DB path — override via DASHBOARD_DB_PATH env var
_DEFAULT_DB = str(Path(__file__).parent.parent.parent.parent / "printflow.db")
_DB_PATH = os.environ.get("DASHBOARD_DB_PATH", _DEFAULT_DB)

DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    # Allow SQLite to be used from multiple threads (FastAPI creates threads per request)
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_conn: object, _connection_record: object) -> None:
    """Enable WAL journal mode on every new connection for better concurrency."""
    cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


# Session factory — use as context manager in routes
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def init_db() -> None:
    """Create all tables that don't exist yet.

    Safe to call on every startup (CREATE TABLE IF NOT EXISTS semantics).
    """
    # Import models so they register with Base.metadata before create_all
    import dashboard.db.models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session and closes it after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
