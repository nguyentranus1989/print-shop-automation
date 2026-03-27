"""Shared test fixtures for PrintFlow E2E tests."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Agent fixtures
from common.models.printer import PrinterType
from agent.printer.mock import MockBackend
from agent.api import app as agent_app, set_backend, set_printer_info

# Dashboard fixtures
from dashboard.db.database import Base, get_db
from dashboard.db.models import Printer  # noqa: F401 — registers models with Base
from dashboard.api.printers import set_agent_manager
from dashboard.services.agent_manager import AgentManager


# ---------------------------------------------------------------------------
# Thin MockBackend wrapper that accepts the `workstation` kwarg the protocol
# requires (MockBackend.inject_job predates the kwarg — protocol updated first).
# ---------------------------------------------------------------------------

class _FullMockBackend(MockBackend):
    """MockBackend with workstation kwarg support matching PrinterBackend protocol."""

    async def inject_job(  # type: ignore[override]
        self, prn_path: str, job_name: str, workstation: int | None = None
    ) -> bool:
        # Delegate to parent (workstation is ignored in mock — no real hardware)
        return await super().inject_job(prn_path, job_name)


# --- Agent fixtures -------------------------------------------------------

@pytest.fixture
def dtg_backend() -> _FullMockBackend:
    """MockBackend configured as DTG printer (instant, no failures)."""
    return _FullMockBackend(
        printer_type=PrinterType.DTG,
        inject_delay=0.01,
        failure_rate=0.0,
    )


@pytest.fixture
def dtf_backend() -> _FullMockBackend:
    return _FullMockBackend(
        printer_type=PrinterType.DTF,
        inject_delay=0.01,
        failure_rate=0.0,
    )


@pytest.fixture
def uv_backend() -> _FullMockBackend:
    return _FullMockBackend(
        printer_type=PrinterType.UV,
        inject_delay=0.01,
        failure_rate=0.0,
    )


@pytest.fixture
def agent_client_dtg(dtg_backend: _FullMockBackend) -> TestClient:
    """TestClient for Agent API with DTG backend."""
    set_backend(dtg_backend)
    set_printer_info("Test-DTG", "dtg")
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture
def agent_client_dtf(dtf_backend: _FullMockBackend) -> TestClient:
    set_backend(dtf_backend)
    set_printer_info("Test-DTF", "dtf")
    with TestClient(agent_app) as c:
        yield c


@pytest.fixture
def agent_client_uv(uv_backend: _FullMockBackend) -> TestClient:
    set_backend(uv_backend)
    set_printer_info("Test-UV", "uv")
    with TestClient(agent_app) as c:
        yield c


# --- Dashboard fixtures ---------------------------------------------------

@pytest.fixture
def test_db_engine():
    """In-memory SQLite engine for tests.

    Uses StaticPool so ALL connections share the same in-memory database
    (default SQLite :memory: gives each connection a separate empty DB).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """DB session that rolls back after each test."""
    Session = sessionmaker(bind=test_db_engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def dashboard_client(test_db_engine, monkeypatch):
    """TestClient for Dashboard with in-memory DB and mocked AgentManager.

    Monkeypatches the database module so create_app()'s internal init_db()
    and AgentManager both use the test in-memory engine instead of the
    file-based SQLite.  Also patches AgentManager network methods to avoid
    real HTTP calls during tests.
    """
    import dashboard.db.database as db_mod
    from dashboard.main import create_app

    TestSession = sessionmaker(bind=test_db_engine)

    # Monkeypatch the module-level engine and SessionLocal so init_db()
    # and the AgentManager created inside _make_app() use the test DB.
    monkeypatch.setattr(db_mod, "engine", test_db_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", TestSession)

    # Patch AgentManager network methods to avoid real HTTP calls
    monkeypatch.setattr(
        AgentManager, "ping_health",
        AsyncMock(return_value={"status": "ok", "printer_type": "dtg"}),
    )
    monkeypatch.setattr(
        AgentManager, "send_control",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        AgentManager, "send_job",
        AsyncMock(return_value=True),
    )

    # Ensure ALL model tables exist on the test engine
    import dashboard.db.models  # noqa: F401 — register models
    Base.metadata.create_all(bind=test_db_engine)

    app = create_app()

    # Override the FastAPI get_db dependency
    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
