"""Dashboard entry point — FastAPI app, HTML pages, API routers, agent polling."""

from __future__ import annotations

import argparse
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard.api.printers import router as printers_router, set_agent_manager
from dashboard.api.jobs import router as jobs_router
from dashboard.api.analytics import router as analytics_router
from dashboard.db.database import init_db, SessionLocal
from dashboard.services.agent_manager import AgentManager


def _frozen_base() -> Path:
    """Return the base directory for bundled data files.

    When running as a PyInstaller .exe the data files are extracted to
    sys._MEIPASS (the _internal/ folder next to the .exe).  In normal
    Python the package directory is used as usual.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller unpacks datas into sys._MEIPASS
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    # Normal Python: data lives next to this source file
    return Path(__file__).parent


# --- Template setup ---------------------------------------------------
_BASE = _frozen_base()
_TEMPLATES_DIR = _BASE / "dashboard" / "templates" if getattr(sys, "frozen", False) else _BASE / "templates"
_STATIC_DIR = _BASE / "dashboard" / "static" if getattr(sys, "frozen", False) else _BASE / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# --- App factory ------------------------------------------------------


def _make_app() -> FastAPI:
    """Create the FastAPI app. AgentManager loads printers from DB."""

    manager = AgentManager(db_session_factory=SessionLocal)
    set_agent_manager(manager)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup: create tables, then load printers from DB and start polling
        init_db()
        await manager.start_polling()
        yield
        # Shutdown
        await manager.stop_polling()

    app = FastAPI(title="PrintFlow Dashboard", version="0.1.0", lifespan=lifespan)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # API routes
    app.include_router(printers_router)
    app.include_router(jobs_router)
    app.include_router(analytics_router)

    # --- HTML page routes -----------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name="dashboard.html", context={"active_page": "dashboard"}
        )

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name="jobs.html", context={"active_page": "jobs"}
        )

    @app.get("/printers", response_class=HTMLResponse)
    def printers_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name="printers.html", context={"active_page": "printers"}
        )

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="analytics.html",
            context={"active_page": "analytics"},
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "printflow-dashboard"}

    return app


# --- CLI --------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printflow-dashboard",
        description="PrintFlow dashboard — web UI and central API.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    app = _make_app()
    print(f"[dashboard] Starting on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


# Expose app for tests / uvicorn --factory
def create_app() -> FastAPI:
    return _make_app()


if __name__ == "__main__":
    main()
