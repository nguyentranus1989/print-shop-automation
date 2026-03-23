"""Dashboard entry point — FastAPI app, HTML pages, API routers, agent polling."""

from __future__ import annotations

import argparse
import os
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
from dashboard.db.database import init_db
from dashboard.services.agent_manager import AgentManager

# --- Template setup ---------------------------------------------------
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# --- Lifespan (startup / shutdown) ------------------------------------

def _make_app(agent_urls: list[str]) -> FastAPI:
    """Factory to create the FastAPI app with injected agent list."""

    manager = AgentManager(agent_urls)
    set_agent_manager(manager)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        # Startup
        init_db()
        await manager.start_polling()
        yield
        # Shutdown
        await manager.stop_polling()

    app = FastAPI(title="PrintFlow Dashboard", version="0.1.0", lifespan=lifespan)

    # Static files (CSS overrides, favicon, etc.)
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # API routes
    app.include_router(printers_router)
    app.include_router(jobs_router)
    app.include_router(analytics_router)

    # --- HTML page routes -----------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/jobs", response_class=HTMLResponse)
    def jobs_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("jobs.html", {"request": request})

    @app.get("/printers", response_class=HTMLResponse)
    def printers_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("printers.html", {"request": request})

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics_page(request: Request) -> HTMLResponse:
        return templates.TemplateResponse("analytics.html", {"request": request})

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
    parser.add_argument(
        "--agents",
        default="",
        help="Comma-separated agent URLs, e.g. http://192.168.1.101:8080,http://192.168.1.102:8080",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    # Agent URLs: CLI flag > env var > empty list (mock/dev)
    agent_str = args.agents or os.environ.get("AGENT_URLS", "")
    agent_urls = [u.strip() for u in agent_str.split(",") if u.strip()]

    if not agent_urls:
        print("[dashboard] No agent URLs configured — running without live printer data.", flush=True)

    app = _make_app(agent_urls)

    print(f"[dashboard] Starting on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


# Expose app for tests / uvicorn --factory
def create_app() -> FastAPI:
    agent_str = os.environ.get("AGENT_URLS", "")
    agent_urls = [u.strip() for u in agent_str.split(",") if u.strip()]
    return _make_app(agent_urls)


if __name__ == "__main__":
    main()
