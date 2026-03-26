"""Reports API — proxies UV job history from agent to dashboard."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from dashboard.db.database import get_db
from dashboard.db.models import Printer

router = APIRouter(prefix="/api/reports", tags=["reports"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


async def _proxy_agent(printer_id: int, path: str, params: dict, db: Session) -> Any:
    """Forward a report request to the agent."""
    printer = db.query(Printer).filter(Printer.id == printer_id).first()
    if not printer:
        raise HTTPException(404, "Printer not found")

    url = f"{printer.agent_url.rstrip('/')}/reports/{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Agent unreachable: {e}")


@router.get("/summary")
async def reports_summary(
    printer_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await _proxy_agent(printer_id, "summary", {}, db)


@router.get("/recent")
async def reports_recent(
    printer_id: int = Query(...),
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return await _proxy_agent(printer_id, "recent", {"limit": limit}, db)


@router.get("/daily")
async def reports_daily(
    printer_id: int = Query(...),
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return await _proxy_agent(printer_id, "daily", {"days": days}, db)


@router.get("/ink")
async def reports_ink(
    printer_id: int = Query(...),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return await _proxy_agent(printer_id, "ink", {}, db)


@router.get("/page", response_class=HTMLResponse)
async def reports_page_data(
    request: Request,
    printer_id: int = Query(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """HTMX partial — renders full report content for a selected printer."""
    try:
        summary = await _proxy_agent(printer_id, "summary", {}, db)
        recent = await _proxy_agent(printer_id, "recent", {"limit": 15}, db)
        daily = await _proxy_agent(printer_id, "daily", {"days": 14}, db)
        ink = await _proxy_agent(printer_id, "ink", {}, db)
    except HTTPException:
        summary, recent, daily, ink = None, [], [], []

    return _templates.TemplateResponse(
        request=request,
        name="partials/report-content.html",
        context={
            "summary": summary,
            "recent": recent,
            "daily": daily,
            "ink": ink,
        },
    )
